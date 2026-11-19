#!/usr/bin/env python3
"""
aicp_credentials.py — AICP 平台凭据管理脚本（xiaomali 增强版）

子命令：
  read                 读凭据文件 → JSON 字符串输出到 stdout；文件不存在输出空
  write '<json>'       写入凭据（拒绝 password 字段，ptKey 必须以 pt- 开头）
  delete               删除凭据文件
  set-password '<pwd>' 登录密码存入系统密钥链（不落明文），并更新 aicp.json hasPassword=true
  clear-password       清除密钥链中的密码，并更新 aicp.json hasPassword=false
  get-jwt              用 mobile + 密码自动调 login.vm 换会话 JWT → stdout 仅输出 JWT
                       （密码全程不出现在输出；JWT 仅供本次调用方使用，勿落盘）

密码存储（按平台，明文永不落盘）：
  Windows → DPAPI (crypt32.CryptProtectData) 加密后存 aicp_password.bin（绑定当前 Windows 账户）
  macOS   → Keychain (security 命令, service=workbuddy-aicp)
  Linux   → secretstorage (org.freedesktop.secrets)，不可用时报错退出

退出码：
  0 = 成功
  1 = 错误（stderr 输出原因）

示例：
  python3 scripts/aicp_credentials.py read
  python3 scripts/aicp_credentials.py write '{"ptKey":"pt-xxx","mobile":"138xxxxxxxx","hasPassword":false,"updatedAt":"..."}'
  python3 scripts/aicp_credentials.py set-password 'MyP@ss'
  python3 scripts/aicp_credentials.py get-jwt
  python3 scripts/aicp_credentials.py clear-password
"""

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

CRED_FILE = Path.home() / ".workbuddy" / "credentials" / "aicp.json"
PWD_FILE = Path.home() / ".workbuddy" / "credentials" / "aicp_password.bin"
ALLOWED_FIELDS = {"ptKey", "accountId", "mobile", "hasPassword", "updatedAt"}
REQUIRED_FIELDS = {"ptKey", "updatedAt"}
KEYCHAIN_SERVICE = "workbuddy-aicp"
LOGIN_URL = "https://codetg.com/com/codetg/aa/login/api/auth/login.vm"
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


# ---------------------------------------------------------------- 基础工具

def _ensure_parent() -> None:
    CRED_FILE.parent.mkdir(parents=True, exist_ok=True)


def _tighten_perms(path: Path) -> None:
    """按平台收紧文件权限：Linux/macOS chmod 600；Windows icacls。"""
    system = platform.system().lower()
    try:
        if system in ("linux", "darwin"):
            os.chmod(path, 0o600)
        elif system == "windows":
            username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if not username:
                return  # 无法获取用户名时跳过，避免 icacls 报错卡死
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:RW"],
                check=False, capture_output=True, text=True,
                encoding="oem", errors="ignore",
            )
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 收紧权限失败（不影响数据写入）: {e}", file=sys.stderr)


def _loosen_perms(path: Path) -> None:
    """写文件前确保 owner 可写。"""
    system = platform.system().lower()
    try:
        if system in ("linux", "darwin"):
            if path.exists():
                os.chmod(path, 0o600)
        elif system == "windows":
            username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            if not username:
                return
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:RW"],
                check=False, capture_output=True, text=True,
                encoding="oem", errors="ignore",
            )
    except Exception:  # noqa: BLE001
        pass


def _load_cred() -> dict:
    if not CRED_FILE.exists():
        return {}
    try:
        return json.loads(CRED_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[error] 凭据文件 JSON 损坏: {e}", file=sys.stderr)
        return {}


def _save_flag(flag: str, value: bool) -> None:
    """更新 aicp.json 中的布尔标记字段，保留其余字段。"""
    cred = _load_cred()
    if not cred:
        print("[warn] 凭据文件不存在/损坏，仅更新密钥链，未写 aicp.json", file=sys.stderr)
        return
    cred[flag] = value
    _ensure_parent()
    _loosen_perms(CRED_FILE)
    CRED_FILE.write_text(json.dumps(cred, ensure_ascii=False, indent=2), encoding="utf-8")
    _tighten_perms(CRED_FILE)


# ---------------------------------------------------------------- 密码密钥链

def _win_dpapi(data: bytes, encrypt: bool) -> bytes:
    """Windows DPAPI 加解密（crypt32），绑定当前 Windows 用户。"""
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
            ctypes.byref(blob_in), "workbuddy-aicp", None, None, None, 0, ctypes.byref(blob_out))
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
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
        _ensure_parent()
        PWD_FILE.write_bytes(blob)
        _tighten_perms(PWD_FILE)
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
        old = col.search_items(attrs)
        for it in old:
            it.delete()
        col.create_item("workbuddy-aicp-login", attrs, pwd, replace=True)
    else:
        raise OSError(f"不支持的平台: {system}")


def password_load() -> str | None:
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


# ---------------------------------------------------------------- 子命令

def cmd_read() -> int:
    if not CRED_FILE.exists():
        return 0
    try:
        data = json.loads(CRED_FILE.read_text(encoding="utf-8"))
        print(json.dumps(data, ensure_ascii=False))
    except json.JSONDecodeError as e:
        print(f"[error] 凭据文件 JSON 损坏: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_write(payload: str) -> int:
    if not payload:
        print("[error] write 子命令需要 JSON 字符串参数", file=sys.stderr)
        return 1
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"[error] JSON 解析失败: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("[error] 写入内容必须是 object（{}）", file=sys.stderr)
        return 1

    forbidden = set(data.keys()) - ALLOWED_FIELDS
    if forbidden:
        print(
            f"[error] 拒绝写入字段: {sorted(forbidden)}。仅允许: {sorted(ALLOWED_FIELDS)}",
            file=sys.stderr,
        )
        return 1

    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        print(f"[error] 缺少必填字段: {sorted(missing)}", file=sys.stderr)
        return 1

    pt_key = data.get("ptKey", "")
    if not isinstance(pt_key, str) or not pt_key.startswith("pt-"):
        print("[error] ptKey 必须是非空字符串且以 'pt-' 开头", file=sys.stderr)
        return 1

    _ensure_parent()
    if CRED_FILE.exists():
        _loosen_perms(CRED_FILE)
    CRED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _tighten_perms(CRED_FILE)
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
        print("[error] set-password 需要密码参数", file=sys.stderr)
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
    _save_flag("hasPassword", False)
    print("[ok] 密码已从密钥链清除，aicp.json hasPassword=false")
    return 0


def cmd_get_jwt() -> int:
    cred = _load_cred()
    mobile = cred.get("mobile")
    if not mobile:
        print("PASSWORD_NOT_SET: 凭据缺失 mobile，先完成开户流程", file=sys.stderr)
        return 1
    pwd = password_load()
    if not pwd:
        print("PASSWORD_NOT_SET: 未设置密码，先执行 set-password '<密码>'", file=sys.stderr)
        return 1

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
        return 1

    m = JWT_RE.search(body + " " + cookies)
    if not m:
        print(f"LOGIN_FAILED: 响应中未找到 JWT（密码可能错误）。响应片段: {body[:200]}",
              file=sys.stderr)
        return 1
    print(m.group(0))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "用法: aicp_credentials.py read | write '<json>' | delete | "
            "set-password '<pwd>' | clear-password | get-jwt",
            file=sys.stderr,
        )
        return 1
    sub = sys.argv[1].lower()
    if sub == "read":
        return cmd_read()
    if sub == "write":
        return cmd_write(sys.argv[2] if len(sys.argv) > 2 else "")
    if sub == "delete":
        return cmd_delete()
    if sub == "set-password":
        return cmd_set_password(sys.argv[2] if len(sys.argv) > 2 else "")
    if sub == "clear-password":
        return cmd_clear_password()
    if sub == "get-jwt":
        return cmd_get_jwt()
    print(f"[error] 未知子命令: {sub}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
