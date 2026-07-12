#!/usr/bin/env python3
"""同一Wi-Fi内の端末からアクセスできるLANサーバーを起動"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.realtime_monitor import start_background_monitor
from tools.security_monitor import start_security_monitor

PORT = 8501


def get_local_ips() -> list[str]:
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass

    return list(dict.fromkeys(ips))


def print_banner(ips: list[str]) -> None:
    print()
    print("=" * 56)
    print("  ロト6予想 - ローカルネットワーク公開モード")
    print("=" * 56)
    print()
    print(f"  このPCから:     http://localhost:{PORT}")
    if ips:
        print()
        print("  スマホ・タブレット・他のPCから:")
        for ip in ips:
            print(f"    → http://{ip}:{PORT}")
    else:
        print()
        print("  ※ IPアドレスを取得できませんでした")
        print("    ipconfig で IPv4 アドレスを確認してください")
    print()
    print("  条件: 同じWi-Fi / 同じLANに接続していること")
    print("  停止: 「接続停止.bat」をダブルクリック（または Ctrl+C）")
    print()
    print("  ※ 初回はWindowsファイアウォールの許可を求められる場合があります")
    print("  ※ 攻撃を検知した場合、サーバーは自動で停止します")
    print("=" * 56)
    print()


def main() -> int:
    start_background_monitor()
    start_security_monitor()
    print("リアルタイム監視を開始しました（バックグラウンド）")
    print("セキュリティ監視を開始しました（攻撃検知時に自動停止）")
    ips = get_local_ips()
    print_banner(ips)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "streamlit_app.py"),
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(PORT),
        "--browser.gatherUsageStats",
        "false",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
        "--server.enableWebsocketCompression",
        "false",
    ]
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
