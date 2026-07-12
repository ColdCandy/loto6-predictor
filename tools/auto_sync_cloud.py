#!/usr/bin/env python3
"""変更をGitHubへ自動同期 → クラウドURLを自動更新"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
REPO_NAME = "loto6-predictor"
LOG_FILE = ROOT / "data" / "auto_sync.log"
LOCK_FILE = ROOT / "data" / ".sync_lock"


def log(msg: str, quiet: bool = False) -> None:
    line = f"[{datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')}] {msg}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    if not quiet:
        print(msg)


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def have_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def git(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["git", *args], check=check, capture=capture)


def gh(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["gh", *args], check=check, capture=capture)


def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < 300:
                return False
        except OSError:
            pass
    LOCK_FILE.write_text(str(time.time()), encoding="utf-8")
    return True


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def auto_setup_if_needed(quiet: bool) -> bool:
    if (ROOT / ".git").exists():
        remote = git("remote", "get-url", "origin", check=False, capture=True)
        if remote.returncode == 0:
            return True
    if "--auto" not in sys.argv:
        return False
    setup = ROOT / "tools" / "setup_cloud_deploy.py"
    if not setup.exists():
        return False
    log("クラウド未設定 → 自動セットアップ開始", quiet)
    r = subprocess.run([sys.executable, str(setup)], cwd=ROOT, capture_output=quiet)
    return r.returncode == 0


def refresh_local_data() -> list[str]:
    updated: list[str] = []
    sys.path.insert(0, str(ROOT))

    try:
        from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv

        before = DEFAULT_DATA_PATH.stat().st_mtime if DEFAULT_DATA_PATH.exists() else 0
        download_csv()
        if DEFAULT_DATA_PATH.stat().st_mtime != before:
            updated.append("loto6.csv")
    except Exception as e:
        log(f"ロト6データ更新スキップ: {e}", quiet=True)

    try:
        from loto6_predictor.loto7_data import DEFAULT_DATA_PATH as L7
        from loto6_predictor.loto7_data import download_csv as dl7

        before = L7.stat().st_mtime if L7.exists() else 0
        dl7()
        if L7.stat().st_mtime != before:
            updated.append("loto7.csv")
    except Exception as e:
        log(f"ロト7データ更新スキップ: {e}", quiet=True)

    return updated


def get_owner() -> str | None:
    if not have_cmd("gh"):
        return None
    r = gh("api", "user", "--jq", ".login", check=False, capture=True)
    return r.stdout.strip() if r.returncode == 0 else None


def sync_to_github(message: str | None = None, quiet: bool = False) -> bool:
    if not (ROOT / ".git").exists():
        log("Git未初期化", quiet)
        return False

    git("add", "-A")
    status = git("status", "--porcelain", capture=True)
    if not status.stdout.strip():
        log("変更なし", quiet)
        return False

    now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    msg = message or f"自動同期 {now}"
    git("commit", "-m", msg)
    git("push", "origin", "main")
    log("GitHubへプッシュ完了", quiet)
    return True


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    quiet = "--quiet" in sys.argv

    if "--startup" in sys.argv:
        time.sleep(45)

    if not acquire_lock():
        log("同期スキップ（実行中）", quiet)
        return 0

    try:
        if not have_cmd("git"):
            log("エラー: Git が必要です", quiet)
            return 1

        if have_cmd("gh"):
            auth = gh("auth", "status", check=False, capture=True)
            if auth.returncode != 0 and "--auto" not in sys.argv:
                log("GitHub未ログイン", quiet)
                return 1

        auto_setup_if_needed(quiet)

        if not quiet:
            print("クラウド自動同期を開始...")

        data_updated = refresh_local_data()
        if data_updated:
            log(f"データ更新: {', '.join(data_updated)}", quiet)

        pushed = sync_to_github(quiet=quiet)
        owner = get_owner()
        if owner and (pushed or data_updated):
            url = f"https://{owner.lower()}.github.io/{REPO_NAME}/"
            log(f"URL: {url}", quiet)

        return 0
    except subprocess.CalledProcessError as e:
        log(f"同期エラー: {e}", quiet)
        return 1
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
