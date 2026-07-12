#!/usr/bin/env python3
"""ロト6予想サーバー（Streamlit / Cloudflare Tunnel）を完全停止"""

from __future__ import annotations

import subprocess
import sys


PORT = 8501
PROCESS_NAMES = ["cloudflared.exe"]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="cp932", errors="replace")


def get_pids_on_port(port: int) -> list[int]:
    result = _run(["netstat", "-ano"])
    pids: list[int] = []
    token = f":{port}"
    for line in result.stdout.splitlines():
        upper = line.upper()
        if token in line and "LISTENING" in upper:
            parts = line.split()
            if not parts:
                continue
            try:
                pids.append(int(parts[-1]))
            except ValueError:
                continue
    return list(dict.fromkeys(pids))


def kill_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    result = _run(["taskkill", "/F", "/PID", str(pid)])
    return result.returncode == 0


def kill_by_name(name: str) -> bool:
    result = _run(["taskkill", "/F", "/IM", name])
    return result.returncode == 0


def stop_all() -> tuple[list[str], list[int]]:
    stopped: list[str] = []

    for name in PROCESS_NAMES:
        if kill_by_name(name):
            stopped.append(name)

    for pid in get_pids_on_port(PORT):
        if kill_pid(pid):
            stopped.append(f"ポート{PORT} (PID {pid})")

    # 念のため cloudflared / streamlit 関連を再確認
    for name in PROCESS_NAMES:
        check = _run(["tasklist", "/FI", f"IMAGENAME eq {name}"])
        if name.lower() not in check.stdout.lower():
            continue
        if kill_by_name(name) and name not in stopped:
            stopped.append(name)

    remaining = get_pids_on_port(PORT)
    return stopped, remaining


def main() -> int:
    print()
    print("=" * 50)
    print("  ロト6予想 - 接続停止")
    print("=" * 50)
    print()
    print("  サーバーと外部公開トンネルを停止しています...")
    print()

    stopped, remaining = stop_all()

    if stopped:
        print("  停止しました:")
        for item in stopped:
            print(f"    [OK] {item}")
    else:
        print("  実行中のサーバーは見つかりませんでした。")
        print("  （すでに停止している可能性があります）")

    if remaining:
        print()
        print("  警告: まだポート8501を使用中のプロセスがあります。")
        for pid in remaining:
            print(f"    PID {pid}")
        print("  もう一度 接続停止.bat を実行してください。")
        return 1

    print()
    print("  外部からのURLアクセスも無効になりました。")
    print("=" * 50)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
