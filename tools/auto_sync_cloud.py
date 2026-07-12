#!/usr/bin/env python3
"""変更をGitHubへ自動同期 → クラウドURLを自動更新"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
REPO_NAME = "loto6-predictor"


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


def refresh_local_data() -> list[str]:
    """最新の当選データを取得"""
    updated: list[str] = []
    sys.path.insert(0, str(ROOT))

    try:
        from loto6_predictor.data import download_csv, DEFAULT_DATA_PATH

        before = DEFAULT_DATA_PATH.stat().st_mtime if DEFAULT_DATA_PATH.exists() else 0
        download_csv()
        if DEFAULT_DATA_PATH.stat().st_mtime != before:
            updated.append("loto6.csv")
    except Exception as e:
        print(f"ロト6データ更新スキップ: {e}")

    try:
        from loto6_predictor.loto7_data import download_csv as dl7, DEFAULT_DATA_PATH as L7

        before = L7.stat().st_mtime if L7.exists() else 0
        dl7()
        if L7.stat().st_mtime != before:
            updated.append("loto7.csv")
    except Exception as e:
        print(f"ロト7データ更新スキップ: {e}")

    return updated


def get_owner() -> str | None:
    if not have_cmd("gh"):
        return None
    r = gh("api", "user", "--jq", ".login", check=False, capture=True)
    return r.stdout.strip() if r.returncode == 0 else None


def sync_to_github(message: str | None = None) -> bool:
    """コミット＆プッシュ。変更がなければ False"""
    if not (ROOT / ".git").exists():
        print("Git未初期化です。先に「常時アクセス設定.bat」を実行してください。")
        return False

    git("add", "-A")
    status = git("status", "--porcelain", capture=True)
    if not status.stdout.strip():
        print("変更なし（クラウドは最新です）")
        return False

    now = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
    msg = message or f"自動同期 {now}"
    git("commit", "-m", msg)
    git("push", "origin", "main")
    print("GitHubへプッシュしました → 数分後にクラウドURLが更新されます")
    return True


def print_url() -> None:
    owner = get_owner()
    if owner:
        url = f"https://{owner.lower()}.github.io/{REPO_NAME}/"
        print(f"常時アクセスURL: {url}")


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    quiet = "--quiet" in sys.argv
    if not quiet:
        print("クラウド自動同期を開始...")

    if not have_cmd("git"):
        print("エラー: Git が必要です")
        return 1

    if have_cmd("gh"):
        auth = gh("auth", "status", check=False, capture=True)
        if auth.returncode != 0:
            print("GitHub未ログイン。gh auth login を実行してください。")
            return 1

    try:
        data_updated = refresh_local_data()
        if data_updated and not quiet:
            print(f"データ更新: {', '.join(data_updated)}")

        pushed = sync_to_github()
        if pushed or data_updated:
            print_url()
        return 0
    except subprocess.CalledProcessError as e:
        print(f"同期エラー: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
