#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aicp_credentials.py — codetg.com 凭据管理

凭据读写、自动登录换 JWT、短信注册与 pt-key 换取均在本脚本内完成。
口令只进系统密钥链，明文不落盘。

子命令：
  read                       读环境或本地凭据并输出 JSON；未配置时输出空
  write --stdin              从标准输入读取 JSON（仍接受位置参数形式）
  delete                     删除凭据文件
  set-password [--stdin]     隐藏输入或从标准输入读取密码并存入系统密钥链
  clear-password             清除密钥链中的密码和本地 JWT 缓存
  get-jwt [--json] [--refresh] [--no-cache]
                             用 mobile + 密码自动调 login.vm 换会话 JWT
                             --json     输出结构化信息（含来源与过期时间）
                             --refresh  忽略缓存，强制重新登录
                             --no-cache 本次不读也不写缓存
  get-pt-key [--json] [--refresh] [--no-cache]
                             先用上面同一条路径拿 JWT，再调 view_private_token.jss
                             换 pt-key 并写回 aicp.json 的 ptKey 字段
  set-account '<手机号>'      只写手机号，作为开户第一步（不需要 pt-key）
  send-code [<手机号>] [--json]
                             新用户注册第 1 步：调 send_sms_register.vm 下发短信验证码
                             手机号省略时取 aicp.json 里的 mobile
                             ⚠️ 会真实下发短信并计费，不要重复调用
  register --code '<验证码>' [--name '<昵称>'] [--password '<密码>']
           [--invitation-code '6666'] [--json]
                             新用户注册第 2 步：调 register.vm 建号，成功后自动
                             登录换 JWT → 换 pt-key → 写回 aicp.json（一步到位）
                             密码优先取系统密钥链，其次 --password，都没有则报错
  mask [token]               输出脱敏值（日志/播报用）
  status                     打印凭据与缓存的状态摘要（不含任何明文口令或 token）
  paths                      输出凭据目录和缓存文件路径（不含凭据）

密码存储（明文永不落盘）：
  Windows → DPAPI (crypt32.CryptProtectData) → aicp_password.bin（绑当前 Windows 账户）
  macOS   → Keychain (security)
  Linux   → secretstorage (org.freedesktop.secrets)

本地凭据默认存于 ~/.xiaomali/credentials/，兼容已有 WorkBuddy 凭据。
配置 AICP_PT_KEY 时使用环境凭据，跳过本地读写和 JWT 缓存。

退出码：0 = 成功；1 = 错误（stderr 输出原因，前缀为错误码）
错误码：PASSWORD_NOT_SET / LOGIN_FAILED / CRED_MISSING / PT_KEY_FAILED / BAD_ARGS
        / SMS_FAILED / REGISTER_FAILED / CODE_INVALID / MOBILE_EXISTS
"""

import base64
import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".xiaomali"
LEGACY_ROOT = Path.home() / ".workbuddy"


def _credentials_dir() -> Path:
    configured = os.environ.get("XIAOMALI_CREDENTIALS_DIR")
    if configured:
        return Path(configured).expanduser()
    default = DEFAULT_ROOT / "credentials"
    legacy = LEGACY_ROOT / "credentials"
    if not default.exists() and any((legacy / name).is_file()
                                    for name in ("aicp.json", "aicp_password.bin")):
        return legacy
    return default


HOSTED_KEY = os.environ.get("AICP_PT_KEY", "").strip()
CRED_DIR = DEFAULT_ROOT / "credentials" if HOSTED_KEY else _credentials_dir()
IS_LEGACY_DIR = CRED_DIR == LEGACY_ROOT / "credentials" or (
    CRED_DIR.is_absolute() and CRED_DIR.resolve() == (LEGACY_ROOT / "credentials").resolve())
CRED_FILE = CRED_DIR / "aicp.json"
PWD_FILE = CRED_DIR / "aicp_password.bin"
CACHE_DIR = CRED_DIR.parent / "cache" if CRED_DIR.name == "credentials" else CRED_DIR / "cache"
if not HOSTED_KEY and os.environ.get("XIAOMALI_CACHE_DIR"):
    CACHE_DIR = Path(os.environ["XIAOMALI_CACHE_DIR"]).expanduser()
JWT_CACHE = CACHE_DIR / "xiaomali_jwt.json"
APPID_CACHE = CACHE_DIR / "xiaomali_appid.json"

ALLOWED_FIELDS = {"ptKey", "accountId", "mobile", "hasPassword", "updatedAt"}
REQUIRED_FIELDS = {"ptKey", "updatedAt"}
KEYCHAIN_SERVICE = "workbuddy-aicp" if IS_LEGACY_DIR else "xiaomali-aicp"
LOGIN_URL = "https://codetg.com/com/codetg/aa/login/api/auth/login.vm"
VIEW_TOKEN_URL = ("https://codetg.com/com/codetg/user/basic/information"
                  "/maintenance/api/profile/view_private_token.jss")
SMS_REG_URL = ("https://codetg.com/com/codetg/aa/login/api/auth"
               "/mobile/send_sms_register.vm")
REGISTER_URL = ("https://codetg.com/com/codetg/aa/login/api/auth"
                "/mobile/register.vm")
# 旧版 1.0.4 硬编码的邀请码，服务端目前接受
INVITATION_CODE = "6666"
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# JWT 实测有效期约 100 小时，留 10 小时余量
JWT_TTL_SECONDS = 90 * 3600


# ---------------------------------------------------------------- 基础工具

def _tighten_perms(path: Path) -> None:
    """按平台收紧文件权限：Linux/macOS chmod 600；Windows icacls 仅当前用户可读写。"""
    system = platform.system().lower()
    try:
        if system in ("linux", "darwin"):
            os.chmod(path, 0o600)
        elif system == "windows":
            username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if not username:
                return
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:F"],
                check=False, capture_output=True, text=True,
                encoding="oem", errors="ignore",
            )
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 收紧权限失败（不影响数据写入）: {e}", file=sys.stderr)


def _write_private_file(path: Path, contents: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary_path = Path(stream.name)
    try:
        _tighten_perms(temporary_path)
        temporary_path.write_bytes(contents)
        if os.name == "nt" and path.exists():
            _tighten_perms(path)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_private(path: Path, text: str) -> None:
    _write_private_file(path, text.encode("utf-8"))


def _environment_key() -> str:
    key = HOSTED_KEY or os.environ.get("CODETG_PT_KEY", "").strip()
    if key and (not key.startswith("pt-") or len(key) <= 3):
        source = "AICP_PT_KEY" if HOSTED_KEY else "CODETG_PT_KEY"
        raise ValueError(f"{source} 必须是以 pt- 开头的 API Key")
    return key


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def mask_token(token: str) -> str:
    """脱敏：保留前 4 位，其余用 * 代替。"""
    if not token:
        return ""
    keep = 4 if len(token) > 12 else 2
    return token[:keep] + "*" * 8


def _mobile_hash(mobile: str) -> str:
    return hashlib.sha256(mobile.encode("utf-8")).hexdigest()[:16]


def _load_cred() -> dict:
    if HOSTED_KEY:
        return {
            "ptKey": _environment_key(),
            "mobile": os.environ.get("AICP_MOBILE", "").strip(),
            "hasPassword": bool(os.environ.get("AICP_LOGIN_PASSWORD")),
        }
    if not CRED_FILE.exists():
        return {}
    data = json.loads(CRED_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("凭据文件必须包含一个 JSON 对象")
    return data


def _save_flag(flag: str, value: bool) -> None:
    cred = _load_cred()
    if not cred:
        print("[warn] 凭据文件不存在/损坏，仅更新密钥链，未写 aicp.json", file=sys.stderr)
        return
    cred[flag] = value
    cred["updatedAt"] = _now_iso()
    _write_private(CRED_FILE, json.dumps(cred, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 密码密钥链

def _win_dpapi(data: bytes, encrypt: bool) -> bytes:
    """Windows DPAPI 加解密（crypt32），绑定当前 Windows 登录用户。"""
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if encrypt:
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in), KEYCHAIN_SERVICE, None, None, None, 0,
            ctypes.byref(blob_out))
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0,
            ctypes.byref(blob_out))
    if not ok:
        raise OSError("DPAPI 调用失败")
    out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return out


def _keychain_account() -> str:
    cred = _load_cred()
    return cred.get("mobile") or cred.get("accountId") or "default"


def password_store(pwd: str) -> None:
    system = platform.system().lower()
    if system == "windows":
        blob = _win_dpapi(pwd.encode("utf-8"), encrypt=True)
        _write_private_file(PWD_FILE, blob)
    elif system == "darwin":
        subprocess.run(
            ["security", "add-generic-password", "-U",
             "-s", KEYCHAIN_SERVICE, "-a", _keychain_account(), "-w", pwd],
            check=True, capture_output=True, text=True)
    elif system == "linux":
        try:
            import secretstorage  # type: ignore
        except ImportError:
            raise OSError("Linux 需要 python3-secretstorage 才能存密码到系统密钥链")
        bus = secretstorage.dbus_init()
        col = secretstorage.get_default_collection(bus)
        if col.is_locked():
            col.unlock()
        attrs = {"service": KEYCHAIN_SERVICE, "account": _keychain_account()}
        col.create_item(f"{KEYCHAIN_SERVICE}-login", attrs, pwd.encode("utf-8"), replace=True)
    else:
        raise OSError(f"不支持的平台: {system}")


def password_load():
    system = platform.system().lower()
    try:
        if system == "windows":
            if not PWD_FILE.exists():
                return None
            return _win_dpapi(PWD_FILE.read_bytes(), encrypt=False).decode("utf-8")
        if system == "darwin":
            r = subprocess.run(
                ["security", "find-generic-password",
                 "-s", KEYCHAIN_SERVICE, "-a", _keychain_account(), "-w"],
                capture_output=True, text=True)
            return r.stdout.strip() if r.returncode == 0 else None
        if system == "linux":
            import secretstorage  # type: ignore
            bus = secretstorage.dbus_init()
            col = secretstorage.get_default_collection(bus)
            if col.is_locked():
                col.unlock()
            items = list(col.search_items(
                {"service": KEYCHAIN_SERVICE, "account": _keychain_account()}))
            return items[0].get_secret().decode("utf-8") if items else None
    except Exception as e:  # noqa: BLE001
        print(f"[error] 读取密码失败: {e}", file=sys.stderr)
        return None
    return None


def password_clear() -> None:
    system = platform.system().lower()
    if system == "windows":
        if PWD_FILE.exists():
            PWD_FILE.unlink()
    elif system == "darwin":
        subprocess.run(
            ["security", "delete-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", _keychain_account()],
            capture_output=True, text=True)
    elif system == "linux":
        try:
            import secretstorage  # type: ignore
            bus = secretstorage.dbus_init()
            col = secretstorage.get_default_collection(bus)
            if col.is_locked():
                col.unlock()
            for it in col.search_items(
                    {"service": KEYCHAIN_SERVICE, "account": _keychain_account()}):
                it.delete()
        except ImportError:
            pass


# ---------------------------------------------------------------- JWT 缓存

def cache_load(mobile: str):
    """返回 (jwt, obtained_at_dt, age_seconds)；不可用则 None。"""
    if not mobile or not JWT_CACHE.exists():
        return None
    try:
        data = json.loads(JWT_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    jwt = data.get("jwt")
    if not isinstance(jwt, str) or not JWT_RE.fullmatch(jwt):
        return None
    if data.get("mobileHash") != _mobile_hash(mobile):
        return None
    try:
        obtained = datetime.fromisoformat(data["obtainedAt"])
    except (KeyError, TypeError, ValueError):
        return None
    age = (datetime.now(timezone.utc) - obtained.astimezone(timezone.utc)).total_seconds()
    if age < 0 or age >= JWT_TTL_SECONDS:
        return None
    return jwt, obtained, int(age)


def cache_save(jwt: str, mobile: str) -> None:
    payload = {
        "jwt": jwt,
        "obtainedAt": _now_iso(),
        "mobileHash": _mobile_hash(mobile) if mobile else "",
        "jwtMasked": mask_token(jwt),
    }
    _write_private(JWT_CACHE, json.dumps(payload, ensure_ascii=False, indent=2))


def cache_clear() -> None:
    JWT_CACHE.unlink(missing_ok=True)


# ---------------------------------------------------------------- 登录

def _login(mobile: str, pwd: str):
    """调 login.vm 换 JWT；成功返回 jwt 字符串，失败返回 None（已打 stderr）。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        LOGIN_URL,
        data=json.dumps({"login_id": mobile, "password": pwd}).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "workbuddy-skill/1.0"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read().decode("utf-8", "ignore")
        cookies = " ".join(resp.headers.get_all("Set-Cookie") or [])
    except Exception as e:  # noqa: BLE001
        print(f"LOGIN_FAILED: 请求异常 {e}", file=sys.stderr)
        return None

    m = JWT_RE.search(body + " " + cookies)
    if not m:
        print("LOGIN_FAILED: 响应中未找到 JWT，请核对账号和密码", file=sys.stderr)
        return None
    return m.group(0)


# ---------------------------------------------------------------- 子命令

def cmd_read() -> int:
    key = _environment_key()
    data = _load_cred()
    if key:
        data["ptKey"] = key
    if data:
        print(json.dumps(data, ensure_ascii=False))
    return 0


def cmd_write(payload: str) -> int:
    if not payload:
        print("BAD_ARGS: write --stdin 需要 JSON 输入", file=sys.stderr)
        return 1
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"BAD_ARGS: JSON 解析失败: {e}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("BAD_ARGS: 写入内容必须是 object", file=sys.stderr)
        return 1

    forbidden = set(data.keys()) - ALLOWED_FIELDS
    if forbidden:
        print(f"BAD_ARGS: 拒绝写入字段 {sorted(forbidden)}。仅允许 {sorted(ALLOWED_FIELDS)}",
              file=sys.stderr)
        return 1
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        print(f"BAD_ARGS: 缺少必填字段 {sorted(missing)}", file=sys.stderr)
        return 1

    pt_key = data.get("ptKey", "")
    if not isinstance(pt_key, str) or not pt_key.startswith("pt-") or len(pt_key) <= 3:
        print("BAD_ARGS: ptKey 必须是非空字符串且以 'pt-' 开头", file=sys.stderr)
        return 1

    previous_mobile = _load_cred().get("mobile")
    if previous_mobile and previous_mobile != data.get("mobile"):
        password_clear()
        cache_clear()
        data["hasPassword"] = False
    _write_private(CRED_FILE, json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[ok] 已写入 {CRED_FILE}")
    return 0


def cmd_delete() -> int:
    if not CRED_FILE.exists():
        print("[ok] 凭据文件不存在，无需删除")
        return 0
    try:
        CRED_FILE.unlink()
        print(f"[ok] 已删除 {CRED_FILE}")
    except OSError as e:
        print(f"[error] 删除失败: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_set_password(pwd: str) -> int:
    if not pwd:
        print("BAD_ARGS: 请在终端隐藏输入密码，或使用 set-password --stdin", file=sys.stderr)
        return 1
    try:
        password_store(pwd)
    except Exception as e:  # noqa: BLE001
        print(f"[error] 密码写入密钥链失败: {e}", file=sys.stderr)
        return 1
    _save_flag("hasPassword", True)
    print("[ok] 密码已存入系统密钥链（明文不落盘），aicp.json hasPassword=true")
    return 0


def cmd_clear_password() -> int:
    password_clear()
    cache_clear()
    _save_flag("hasPassword", False)
    print("[ok] 密码已从密钥链清除，aicp.json hasPassword=false")
    return 0


def _obtain_jwt(refresh: bool, use_cache: bool):
    """取会话 JWT。成功返回 (jwt, source, obtained_dt)；失败返回 (None, None, None)。"""
    cred = _load_cred()
    mobile = cred.get("mobile") or ""
    if not mobile:
        hint = "配置 AICP_MOBILE" if HOSTED_KEY else "先执行 set-account '<手机号>'"
        print(f"CRED_MISSING: 缺少手机号，请{hint}", file=sys.stderr)
        return None, None, None

    use_cache = use_cache and not HOSTED_KEY
    if use_cache and not refresh:
        hit = cache_load(mobile)
        if hit:
            jwt, obtained, _age = hit
            return jwt, "cache", obtained

    pwd = os.environ.get("AICP_LOGIN_PASSWORD") if HOSTED_KEY else password_load()
    if not pwd:
        hint = "配置 AICP_LOGIN_PASSWORD" if HOSTED_KEY else "在终端执行 set-password"
        print(f"PASSWORD_NOT_SET: 未设置密码，请{hint}", file=sys.stderr)
        return None, None, None

    jwt = _login(mobile, pwd)
    if not jwt:
        return None, None, None

    if use_cache:
        try:
            cache_save(jwt, mobile)
        except OSError as e:
            print(f"[warn] JWT 缓存写入失败（不影响使用）: {e}", file=sys.stderr)
    return jwt, "login", datetime.now(timezone.utc).astimezone()


def cmd_get_jwt(args) -> int:
    as_json = "--json" in args
    jwt, source, obtained = _obtain_jwt(
        refresh="--refresh" in args, use_cache="--no-cache" not in args)
    if not jwt:
        return 1

    age = (datetime.now(timezone.utc) - obtained.astimezone(timezone.utc)).total_seconds()
    if as_json:
        expires = obtained + timedelta(seconds=JWT_TTL_SECONDS)
        print(json.dumps({
            "jwt": jwt,
            "source": source,
            "obtainedAt": obtained.isoformat(timespec="seconds"),
            "expiresAt": expires.isoformat(timespec="seconds"),
            "ageSeconds": max(int(age), 0),
            "jwtMasked": mask_token(jwt),
        }, ensure_ascii=False))
    else:
        print(jwt)
    return 0


def _fetch_pt_key(jwt: str):
    """用 JWT 调 view_private_token.jss 换 pt-key。成功返回 (token, "")，失败 (None, 原因)。"""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        VIEW_TOKEN_URL,
        data=b"{}",
        headers={"Authorization": f"Bearer {jwt}",
                 "Content-Type": "application/json",
                 "User-Agent": "workbuddy-skill/1.0"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, f"请求异常 {e}"

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None, "响应不是 JSON"

    code = str(data.get("code", ""))
    if code == "jwt_token_invalid":
        return None, "登录态无效（jwt_token_invalid：JWT 过期或被服务端拒绝）"
    if code != "success":
        msg = data.get("msg") or ""
        return None, f"{code}: {msg}".rstrip(": ")

    token = str(((data.get("data") or {}).get("token_value")) or "").strip()
    if not token.startswith("pt-"):
        return None, f"返回的 token_value 不是 pt- 开头（{mask_token(token) or '空'}）"
    return token, ""


def cmd_get_pt_key(args) -> int:
    as_json = "--json" in args
    key = _environment_key()
    if key:
        print(json.dumps({"ptKey": key, "ptKeyMasked": mask_token(key),
                          "jwtSource": "environment", "writtenTo": ""}) if as_json else key)
        return 0
    use_cache = "--no-cache" not in args

    jwt, source, _obtained = _obtain_jwt(
        refresh="--refresh" in args, use_cache=use_cache)
    if not jwt:
        return 1

    token, err = _fetch_pt_key(jwt)
    if token is None and source == "cache":
        low = err.lower()
        if any(k in low for k in ("jwt", "token", "authoriz", "401", "登录")):
            print("[info] 缓存 JWT 可能已失效，强制重新登录后重试一次", file=sys.stderr)
            jwt, source, _obtained = _obtain_jwt(refresh=True, use_cache=use_cache)
            if not jwt:
                return 1
            token, err = _fetch_pt_key(jwt)

    if token is None:
        print(f"PT_KEY_FAILED: {err}", file=sys.stderr)
        return 1

    cred = _load_cred()
    if cred:
        cred["ptKey"] = token
        cred["updatedAt"] = _now_iso()
        _write_private(CRED_FILE, json.dumps(cred, ensure_ascii=False, indent=2))
    else:
        print("[warn] aicp.json 不存在或损坏，pt-key 未写入文件（仅本次输出）",
              file=sys.stderr)

    if as_json:
        print(json.dumps({
            "ptKey": token,
            "ptKeyMasked": mask_token(token),
            "jwtSource": source,
            "writtenTo": str(CRED_FILE) if cred else "",
            "updatedAt": _now_iso(),
        }, ensure_ascii=False))
    else:
        print(token)
    return 0


def cmd_set_account(mobile: str) -> int:
    mobile = (mobile or "").strip()
    if not mobile.isdigit() or len(mobile) < 6:
        print("BAD_ARGS: set-account 需要手机号（纯数字）", file=sys.stderr)
        return 1
    cred = _load_cred()
    previous_mobile = cred.get("mobile")
    if previous_mobile and previous_mobile != mobile:
        password_clear()
        cache_clear()
        cred = {}
    cred["mobile"] = mobile
    cred.setdefault("ptKey", "")
    cred.setdefault("hasPassword", False)
    cred["updatedAt"] = _now_iso()
    _write_private(CRED_FILE, json.dumps(cred, ensure_ascii=False, indent=2))
    print(f"[ok] 已写入 mobile={mobile} → {CRED_FILE}")
    return 0


def _post_json(url: str, body: dict, jwt: str = "", timeout: int = 30):
    """POST JSON。返回 (data_dict, err)；网络/解析失败时 data 为 None。"""
    import urllib.error
    import urllib.request

    headers = {"Content-Type": "application/json",
               "User-Agent": "workbuddy-skill/1.0"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, f"请求异常 {e}"
    try:
        return json.loads(raw), ""
    except json.JSONDecodeError:
        return None, "响应不是 JSON"


def _parse_opts(args, value_opts):
    """['--code','123','--json'] → ({'--code':'123','--json':True}, ['位置参数'])"""
    opts, pos = {}, []
    i = 0
    while i < len(args):
        a = args[i]
        if a in value_opts:
            opts[a] = args[i + 1] if i + 1 < len(args) else ""
            i += 2
            continue
        if a.startswith("--"):
            opts[a] = True
            i += 1
            continue
        pos.append(a)
        i += 1
    return opts, pos


def cmd_send_code(args) -> int:
    """新用户注册第 1 步：下发短信验证码。

    成功判定必须看 data.success，不能只看外层 code —— 服务端在号码非法时
    外层仍返回 code="success"，真实结果在 data.success / send_status_list[0].code。
    """
    as_json = "--json" in args
    opts, pos = _parse_opts(args, {"--mobile"})
    mobile = str(opts.get("--mobile") or (pos[0] if pos else "")).strip()
    if not mobile:
        mobile = (_load_cred().get("mobile") or "").strip()
    if not mobile.isdigit() or len(mobile) < 6:
        print("BAD_ARGS: send-code 需要手机号（纯数字），或先跑 set-account", file=sys.stderr)
        return 1

    data, err = _post_json(SMS_REG_URL, {"mobile": mobile})
    if data is None:
        print(f"SMS_FAILED: {err}", file=sys.stderr)
        return 1

    outer = str(data.get("code", ""))
    payload = data.get("data") or {}
    items = payload.get("send_status_list") or []
    item = items[0] if items else {}
    detail_code = str(item.get("code", ""))
    detail_msg = str(item.get("message", ""))

    if outer != "success" or payload.get("success") is not True:
        blob = f"{detail_code} {detail_msg}".strip() or f"{outer} {data.get('msg') or ''}".strip()
        print(f"SMS_FAILED: {blob}", file=sys.stderr)
        low = blob.lower()
        if "already" in low or "exist" in low or "已注册" in blob:
            print("MOBILE_EXISTS: 该手机号可能已注册，改走 get-pt-key", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps({
            "sent": True,
            "mobile": mobile,
            "phoneNumber": item.get("phone_number", ""),
            "fee": item.get("fee", 0),
            "requestId": payload.get("request_id", ""),
            "serialNo": item.get("serial_no", ""),
        }, ensure_ascii=False))
    else:
        print(f"[ok] 验证码已下发至 {item.get('phone_number') or mobile}"
              f"（计费 {item.get('fee', 0)} 条）；收到后执行 register --code '<验证码>'")
    return 0


def cmd_register(args) -> int:
    """新用户注册第 2 步：验证码建号，成功后自动 登录 → 换 pt-key → 落盘。"""
    as_json = "--json" in args
    opts, _pos = _parse_opts(args, {"--code", "--name", "--password",
                                    "--invitation-code", "--mobile"})

    code = str(opts.get("--code") or "").strip()
    if not code:
        print("BAD_ARGS: register 需要 --code '<短信验证码>'", file=sys.stderr)
        return 1

    cred = _load_cred()
    mobile = str(opts.get("--mobile") or cred.get("mobile") or "").strip()
    if not mobile.isdigit() or len(mobile) < 6:
        print("CRED_MISSING: 缺手机号，先跑 set-account '<手机号>' 或加 --mobile",
              file=sys.stderr)
        return 1
    if cred.get("mobile") and cred["mobile"] != mobile:
        print("BAD_ARGS: 手机号与当前账号不同，请先运行 set-account", file=sys.stderr)
        return 1

    pwd = str(opts.get("--password") or "").strip()
    if not pwd:
        pwd = password_load() or ""
    if not pwd:
        print("PASSWORD_NOT_SET: 未设置密码，请在终端执行 set-password", file=sys.stderr)
        return 1

    name = str(opts.get("--name") or "").strip() or f"用户{mobile[-4:]}"
    inv = str(opts.get("--invitation-code") or INVITATION_CODE).strip()

    # 密码只存在于本次请求体中，不落盘、不回显
    body = {"name": name, "company": "", "mobile": mobile,
            "invitation_code": inv, "code": code, "password": pwd}
    data, err = _post_json(REGISTER_URL, body)
    if data is None:
        print(f"REGISTER_FAILED: {err}", file=sys.stderr)
        return 1

    rcode = str(data.get("code", ""))
    rmsg = str(data.get("msg") or "")
    if rcode != "success":
        low = (rcode + rmsg).lower()
        if "code_is_invalid" in low:
            print("CODE_INVALID: 验证码错误或已过期 —— 重新 send-code 后立刻填新码",
                  file=sys.stderr)
        elif "exist" in low or "已注册" in rmsg:
            print(f"MOBILE_EXISTS: {rcode} {rmsg}".rstrip(), file=sys.stderr)
            print("该手机号已注册，直接走 get-pt-key", file=sys.stderr)
        else:
            print(f"REGISTER_FAILED: {rcode} {rmsg}".rstrip(), file=sys.stderr)
        return 1

    jwt = _login(mobile, pwd)
    token, perr = "", ""
    if jwt:
        try:
            cache_save(jwt, mobile)
        except OSError as e:
            print(f"[warn] JWT 缓存写入失败（不影响使用）: {e}", file=sys.stderr)
        token, perr = _fetch_pt_key(jwt)

    cred = _load_cred()
    cred["mobile"] = mobile
    cred["hasPassword"] = bool(password_load())
    if token:
        cred["ptKey"] = token
    cred["updatedAt"] = _now_iso()
    _write_private(CRED_FILE, json.dumps(cred, ensure_ascii=False, indent=2))

    if as_json:
        out = {"registered": True, "mobile": mobile,
               "ptKeyMasked": mask_token(token), "writtenTo": str(CRED_FILE),
               "updatedAt": _now_iso()}
        if not token:
            out["ptKeyFailed"] = perr or "登录失败，pt-key 未取到"
        print(json.dumps(out, ensure_ascii=False))
    else:
        if token:
            print(f"[ok] 注册成功，pt-key 已写入 {CRED_FILE}")
        else:
            print(f"[warn] 注册成功，但 pt-key 未取到：{perr or '登录失败'}；"
                  f"稍后跑 get-pt-key 补取", file=sys.stderr)
    return 0


def cmd_mask(token: str) -> int:
    print(mask_token(token.strip()) if token else "")
    return 0


def cmd_status() -> int:
    cred = _load_cred()
    key = _environment_key()
    if HOSTED_KEY:
        print("凭据来源: 环境变量\n"
              f"  ptKey       : {mask_token(key)}\n"
              f"  mobile      : {'已配置' if cred.get('mobile') else '未配置'}\n"
              f"  hasPassword : {cred['hasPassword']}")
        return 0
    lines = []
    lines.append(f"凭据文件: {CRED_FILE}  ({'存在' if CRED_FILE.exists() else '不存在'})")
    if cred or key:
        lines.append(f"  mobile      : {cred.get('mobile') or '(未设置)'}")
        lines.append(f"  accountId   : {cred.get('accountId') or '(未设置)'}")
        lines.append(f"  ptKey       : {mask_token(key or cred.get('ptKey', '')) or '(未设置)'}")
        lines.append(f"  hasPassword : {cred.get('hasPassword')}")
        lines.append(f"  updatedAt   : {cred.get('updatedAt') or '(未设置)'}")
    lines.append(f"密码密文: {PWD_FILE}  ({'存在' if PWD_FILE.exists() else '不存在'})")
    lines.append(f"JWT 缓存: {JWT_CACHE}  ({'存在' if JWT_CACHE.exists() else '不存在'})")
    if JWT_CACHE.exists():
        hit = cache_load(cred.get("mobile") or "")
        if hit:
            _, _, age = hit
            lines.append(f"  可用，已 {age // 3600}h{(age % 3600) // 60}m，"
                         f"{JWT_TTL_SECONDS // 3600}h 后需重登")
        else:
            lines.append("  已失效或不匹配当前账号，下次 get-jwt 会重新登录")
    print("\n".join(lines))
    return 0


def cmd_paths() -> int:
    print(json.dumps({
        "mode": "environment" if HOSTED_KEY else "local",
        "credentialsDir": None if HOSTED_KEY else str(CRED_DIR),
        "jwtCache": None if HOSTED_KEY else str(JWT_CACHE),
        "appidCache": None if HOSTED_KEY else str(APPID_CACHE),
    }, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    sub = sys.argv[1].lower()
    rest = sys.argv[2:]
    if not CRED_DIR.is_absolute():
        raise ValueError("XIAOMALI_CREDENTIALS_DIR 必须是绝对路径")
    if not CACHE_DIR.is_absolute():
        raise ValueError("XIAOMALI_CACHE_DIR 必须是绝对路径")
    if HOSTED_KEY and sub in {
        "write", "delete", "set-password", "clear-password", "set-account",
        "send-code", "send-sms", "sms", "register", "signup", "create-account",
    }:
        print("BAD_ARGS: 当前使用环境凭据，请在运行环境的密钥配置中更新", file=sys.stderr)
        return 1

    argument = rest[0] if rest else ""
    if sub in {"write", "set-password"} and argument == "--stdin":
        argument = sys.stdin.read()
        if sub == "set-password":
            argument = argument.rstrip("\r\n")

    if sub == "read":
        return cmd_read()
    if sub == "write":
        return cmd_write(argument)
    if sub == "delete":
        return cmd_delete()
    if sub == "set-password":
        if not rest and sys.stdin.isatty():
            argument = getpass.getpass("AICP 登录密码: ")
        return cmd_set_password(argument)
    if sub == "clear-password":
        return cmd_clear_password()
    if sub == "get-jwt":
        return cmd_get_jwt(rest)
    if sub in ("get-pt-key", "get-ptkey", "get-key"):
        return cmd_get_pt_key(rest)
    if sub == "set-account":
        return cmd_set_account(rest[0] if rest else "")
    if sub in ("send-code", "send-sms", "sms"):
        return cmd_send_code(rest)
    if sub in ("register", "signup", "create-account"):
        return cmd_register(rest)
    if sub == "mask":
        return cmd_mask(rest[0] if rest else "")
    if sub == "status":
        return cmd_status()
    if sub == "paths":
        return cmd_paths()

    print(f"BAD_ARGS: 未知子命令 {sub}", file=sys.stderr)
    print(__doc__.strip(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"[error] {error}", file=sys.stderr)
        sys.exit(1)
