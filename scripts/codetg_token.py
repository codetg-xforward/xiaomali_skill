#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codetg_token.py — API Key 格式校验与脱敏

设计原则：不联网、不读写任何文件、不接收也不处理登录凭据。

子命令：
  check [token]   校验是否为合法形态的 API Key（pt- 前缀 + 足够长度）
  mask  [token]   输出脱敏后的值（用于日志与交付文案）

token 来源优先级：显式参数（`-` 表示 stdin）> AICP_PT_KEY > CODETG_PT_KEY

退出码：0 = 通过 / 1 = 不通过或用法错误
"""

import os
import sys

PREFIX = "pt-"
MIN_LEN = 20
DOC = __doc__


def token_from(argv):
    """仅在显式传 `-` 时读取 stdin，避免在非交互环境下阻塞。"""
    if len(argv) > 2 and argv[2].strip():
        value = argv[2].strip()
        return sys.stdin.read().strip() if value == "-" else value
    return (os.environ.get("AICP_PT_KEY", "").strip()
            or os.environ.get("CODETG_PT_KEY", "").strip())


def mask(token):
    if not token:
        return ""
    return PREFIX + "*" * 8 if token.startswith(PREFIX) else "*" * 8


def main():
    if len(sys.argv) < 2:
        print(DOC)
        return 1
    cmd = sys.argv[1].lower()
    token = token_from(sys.argv)

    if cmd == "check":
        ok = token.startswith(PREFIX) and len(token) >= MIN_LEN and " " not in token
        if ok:
            print("OK")
            return 0
        print("INVALID: 需要提供以 pt- 开头、长度不少于 %d 的 API Key" % MIN_LEN)
        return 1
    if cmd == "mask":
        print(mask(token))
        return 0

    print("未知子命令: %s" % cmd)
    print(DOC)
    return 1


if __name__ == "__main__":
    sys.exit(main())
