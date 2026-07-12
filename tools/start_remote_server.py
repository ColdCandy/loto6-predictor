#!/usr/bin/env python3
"""インターネット経由でアクセスできる公開URLを発行してサーバーを起動"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.realtime_monitor import start_background_monitor
from tools.security_monitor import start_security_monitor

TOOLS = Path(__file__).resolve().parent
PORT = 8501
CLOUDFLARED_EXE = TOOLS / "cloudflared.exe"
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
)


def ensure_cloudflared() -> Path:
    found = shutil.which("cloudflared")
    if found:
        return Path(found)
    if CLOUDFLARED_EXE.exists():
        return CLOUDFLARED_EXE

    print("cloudflared を初回ダウンロード中（約30MB）...")
    req = urllib.request.Request(CLOUDFLARED_URL, headers={"User-Agent": "Loto6Predictor/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        CLOUDFLARED_EXE.write_bytes(resp.read())
    print(f"保存完了: {CLOUDFLARED_EXE}\n")
    return CLOUDFLARED_EXE


STREAMLIT_ARGS = [
    "--server.address",
    "127.0.0.1",
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


def start_streamlit() -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "streamlit_app.py"),
            *STREAMLIT_ARGS,
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def print_banner(public_url: str | None = None) -> None:
    print()
    print("=" * 60, flush=True)
    print("  ロト6予想 - 外からアクセス版", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    print(f"  このPC（ローカル）: http://localhost:{PORT}", flush=True)
    if public_url:
        print(flush=True)
        print("  ★ おばあちゃん家・外からアクセス用URL ★", flush=True)
        print(f"  {public_url}", flush=True)
        print(flush=True)
        print("  上のURLをLINEやメールで送れば、どこからでも使えます！", flush=True)
        print("  スマホのブラウザ（Safari / Chrome）で開いてください。", flush=True)
    print(flush=True)
    print("  【注意】", flush=True)
    print("  ・URLを知っている人なら誰でもアクセスできます", flush=True)
    print("  ・使い終わったら「接続停止.bat」をダブルクリックで完全停止", flush=True)
    print("  ・（またはこのウィンドウで Ctrl+C でも停止できます）", flush=True)
    print("  ・停止するとURLは無効になります（次回起動でURLは変わります）", flush=True)
    print("  ・攻撃を検知した場合、サーバーは自動で停止します", flush=True)
    print(flush=True)
    print("  終了: このウィンドウで Ctrl+C", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)


def run_tunnel(cloudflared: Path) -> None:
    proc = subprocess.Popen(
        [str(cloudflared), "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_url: str | None = None
    url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

    assert proc.stdout is not None
    for line in proc.stdout:
        match = url_pattern.search(line)
        if match and not public_url:
            public_url = match.group(0)
            print_banner(public_url)
        elif not public_url:
            # 接続中のログは簡潔に
            if "trycloudflare" in line.lower() or "tunnel" in line.lower():
                print(".", end="", flush=True)

    proc.wait()


def main() -> int:
    try:
        cloudflared = ensure_cloudflared()
    except Exception as e:
        print(f"エラー: cloudflared の準備に失敗しました: {e}", file=sys.stderr)
        return 1

    print("Streamlit サーバーを起動中...", flush=True)
    start_background_monitor()
    start_security_monitor()
    print("リアルタイム監視を開始しました（バックグラウンド）", flush=True)
    print("セキュリティ監視を開始しました（攻撃検知時に自動停止）", flush=True)
    streamlit_proc = start_streamlit()
    time.sleep(3)

    if streamlit_proc.poll() is not None:
        print("エラー: Streamlit の起動に失敗しました。", file=sys.stderr)
        print("pip install -r requirements.txt を実行してください。")
        return 1

    print("公開URLを作成中...（10〜30秒ほどかかります）", flush=True)

    try:
        run_tunnel(cloudflared)
    except KeyboardInterrupt:
        print("\n停止中...")
    finally:
        streamlit_proc.terminate()
        streamlit_proc.wait(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
