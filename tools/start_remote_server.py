#!/usr/bin/env python3
"""インターネット経由でアクセスできる公開URLを発行してサーバーを起動"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOOLS = Path(__file__).resolve().parent
PORT = 8501
CLOUDFLARED_EXE = TOOLS / "cloudflared.exe"
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
)
PUBLIC_URL_FILE = ROOT / "data" / "public_tunnel_url.txt"
STABLE_ONLINE = "https://coldcandy.github.io/loto6-predictor/"


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


def stop_existing() -> None:
    try:
        from tools.stop_server import stop_all

        stopped, _ = stop_all()
        if stopped:
            print("既存の接続を停止しました: " + ", ".join(stopped), flush=True)
            time.sleep(1.5)
    except Exception as e:
        print(f"（既存停止スキップ: {e}）", flush=True)


STREAMLIT_ARGS = [
    "--server.address",
    "127.0.0.1",
    "--server.port",
    str(PORT),
    "--browser.gatherUsageStats",
    "false",
    "--server.headless",
    "true",
    "--server.enableCORS",
    "false",
    "--server.enableXsrfProtection",
    "false",
    "--server.enableWebsocketCompression",
    "false",
]


def start_streamlit() -> tuple[subprocess.Popen, Path]:
    log_path = ROOT / "data" / "streamlit_remote.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = log_path.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "streamlit_app.py"),
            *STREAMLIT_ARGS,
        ],
        cwd=ROOT,
        stdout=log_f,
        stderr=subprocess.STDOUT,
    )
    return proc, log_path


def wait_streamlit_ready(proc: subprocess.Popen, log_path: Path, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{PORT}/_stcore/health"
    while time.time() < deadline:
        if proc.poll() is not None:
            print("エラー: Streamlit が起動直後に終了しました。", file=sys.stderr)
            try:
                print(log_path.read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
            except OSError:
                pass
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.8)
    print("エラー: Streamlit の起動がタイムアウトしました。", file=sys.stderr)
    try:
        print(log_path.read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
    except OSError:
        pass
    return False


def print_banner(public_url: str | None = None) -> None:
    print()
    print("=" * 60, flush=True)
    print("  ロト6予想 - 外からアクセス版", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    print(f"  このPC（ローカル）: http://localhost:{PORT}", flush=True)
    if public_url:
        print(flush=True)
        print("  ★ 今このPC経由で外から使うURL ★", flush=True)
        print(f"  {public_url}", flush=True)
        print(flush=True)
        print("  上のURLをLINEやメールで送れば、どこからでも使えます！", flush=True)
        PUBLIC_URL_FILE.write_text(public_url + "\n", encoding="utf-8")
    print(flush=True)
    print("  ★ PCの電源OFFでも使える安定URL ★", flush=True)
    print(f"  {STABLE_ONLINE}", flush=True)
    print(flush=True)
    print("  【注意】", flush=True)
    print("  ・トンネルURLはPC起動中のみ有効（次回起動で変わります）", flush=True)
    print("  ・安定して使うなら上記の GitHub Pages URL をブックマーク", flush=True)
    print("  ・停止 → 「接続停止.bat」または Ctrl+C", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)


def run_tunnel(cloudflared: Path) -> int:
    proc = subprocess.Popen(
        [
            str(cloudflared),
            "tunnel",
            "--no-autoupdate",
            "--url",
            f"http://127.0.0.1:{PORT}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    public_url: str | None = None
    url_pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    deadline = time.time() + 90
    assert proc.stdout is not None

    while True:
        if proc.poll() is not None and public_url is None:
            print("エラー: Cloudflare Tunnel がURL発行前に終了しました。", file=sys.stderr)
            return 1

        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            if time.time() > deadline and public_url is None:
                print("エラー: 公開URLの取得がタイムアウトしました。", file=sys.stderr)
                print(f"代替: {STABLE_ONLINE}", file=sys.stderr)
                proc.terminate()
                return 1
            time.sleep(0.2)
            continue

        match = url_pattern.search(line)
        if match and not public_url:
            public_url = match.group(0)
            print_banner(public_url)
        elif not public_url and ("error" in line.lower() or "failed" in line.lower()):
            print(line.rstrip(), flush=True)
        elif not public_url and ("trycloudflare" in line.lower() or "Registered" in line):
            print(".", end="", flush=True)

    return proc.wait() or 0


def main() -> int:
    print("前提確認中...", flush=True)
    try:
        import streamlit  # noqa: F401
        import pandas  # noqa: F401
    except ImportError:
        print("依存パッケージをインストールします...", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
        )

    try:
        cloudflared = ensure_cloudflared()
    except Exception as e:
        print(f"エラー: cloudflared の準備に失敗しました: {e}", file=sys.stderr)
        print(f"代わりに安定URLを使ってください: {STABLE_ONLINE}", file=sys.stderr)
        return 1

    stop_existing()

    print("Streamlit サーバーを起動中...", flush=True)
    try:
        from tools.realtime_monitor import start_background_monitor
        from tools.security_monitor import start_security_monitor

        start_background_monitor()
        start_security_monitor()
        print("リアルタイム監視・セキュリティ監視を開始しました", flush=True)
    except Exception as e:
        print(f"監視の開始に失敗（サーバーは続行）: {e}", flush=True)

    streamlit_proc, log_path = start_streamlit()
    if not wait_streamlit_ready(streamlit_proc, log_path):
        streamlit_proc.terminate()
        return 1

    print("公開URLを作成中...（最大90秒）", flush=True)
    print(f"（待てない場合は安定URL: {STABLE_ONLINE}）", flush=True)

    code = 0
    try:
        code = run_tunnel(cloudflared)
    except KeyboardInterrupt:
        print("\n停止中...")
        code = 0
    finally:
        if streamlit_proc.poll() is None:
            streamlit_proc.terminate()
            try:
                streamlit_proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                streamlit_proc.kill()
        PUBLIC_URL_FILE.unlink(missing_ok=True)

    return code


if __name__ == "__main__":
    sys.exit(main())
