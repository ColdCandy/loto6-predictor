#!/usr/bin/env python3
"""PCの電源が切れていてもアクセスできるようクラウドに自動デプロイ"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "loto6-predictor"
URL_FILE = ROOT / "data" / "cloud_url.txt"
STREAMLIT_DEPLOY = "https://share.streamlit.io/"


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


def gh(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["gh", *args], check=check, capture=capture)


def git(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["git", *args], check=check, capture=capture)


def ensure_git_identity() -> None:
    name = gh("api", "user", "--jq", ".login", capture=True).stdout.strip()
    email = f"{name}@users.noreply.github.com"
    git("config", "user.name", name)
    git("config", "user.email", email)


def ensure_git_repo() -> None:
    if (ROOT / ".git").exists():
        ensure_git_identity()
        return
    print("Git リポジトリを初期化中...")
    git("init")
    git("branch", "-M", "main")
    ensure_git_identity()


def ensure_commit() -> None:
    git("add", "-A")
    status = git("status", "--porcelain", capture=True)
    if status.stdout.strip():
        git("commit", "-m", "ロト6予想 - クラウド常時アクセス版")
        print("変更をコミットしました。")
    else:
        print("コミット済みの状態です。")


def get_github_user() -> str:
    result = gh("api", "user", "--jq", ".login", capture=True)
    return result.stdout.strip()


def repo_exists(owner: str, name: str) -> bool:
    result = gh("repo", "view", f"{owner}/{name}", check=False, capture=True)
    return result.returncode == 0


def create_or_push_repo(owner: str) -> str:
    full = f"{owner}/{REPO_NAME}"
    remote = git("remote", "get-url", "origin", check=False, capture=True)
    if remote.returncode != 0:
        if repo_exists(owner, REPO_NAME):
            print(f"既存リポジトリ {full} に接続します...")
            git("remote", "add", "origin", f"https://github.com/{full}.git")
        else:
            print(f"GitHub リポジトリ {full} を作成中...")
            gh(
                "repo",
                "create",
                REPO_NAME,
                "--public",
                "--source=.",
                "--remote=origin",
                "--push",
                "--description=ロト6予想番号 - PCオフでも使える常時アクセス版",
            )
            return full

    print("GitHub にプッシュ中...")
    git("push", "-u", "origin", "main", check=False)
    git("push", "-u", "origin", "main")
    return full


def enable_github_pages(owner: str) -> str | None:
    full = f"{owner}/{REPO_NAME}"
    pages_url = f"https://{owner.lower()}.github.io/{REPO_NAME}/"

    result = gh(
        "api",
        f"repos/{full}/pages",
        "-X",
        "POST",
        "-f",
        "build_type=workflow",
        check=False,
        capture=True,
    )
    if result.returncode != 0 and "already exists" not in (result.stderr + result.stdout).lower():
        # 既に有効な場合など
        view = gh("api", f"repos/{full}/pages", check=False, capture=True)
        if view.returncode != 0:
            print("GitHub Pages の有効化をスキップ（後で Actions から自動公開されます）")
            return pages_url

    print(f"GitHub Pages を有効化しました: {pages_url}")
    return pages_url


def trigger_pages_workflow(owner: str) -> None:
    full = f"{owner}/{REPO_NAME}"
    print("初回デプロイ（GitHub Actions）を開始...")
    gh(
        "workflow",
        "run",
        "deploy-pages.yml",
        "--repo",
        full,
        check=False,
    )


def save_urls(pages_url: str | None, streamlit_url: str, repo: str) -> None:
    URL_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "========================================",
        "  ロト6予想 - 常時アクセス URL",
        "  ※ PCの電源が切れていても使えます",
        "========================================",
        "",
        "【推奨・すぐ使える（ログイン不要）】",
        f"  {pages_url or '(デプロイ中...数分後に有効)'}",
        "",
        "【高機能版 Streamlit】",
        f"  1. ブラウザで {STREAMLIT_DEPLOY} を開く",
        "  2. Sharing を Public にする（重要）",
        f"  3. リポジトリ: {repo} / メインファイル: streamlit_app.py",
        "  4. Deploy / Reboot",
        "",
        "非公開のままだと「sign in」画面になり外から使えません。",
        "PCオフでも使うなら上の GitHub Pages URL をブックマークしてください。",
        "========================================",
    ]
    URL_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print()
    print("\n".join(lines))


def open_results(pages_url: str | None) -> None:
    if pages_url:
        webbrowser.open(pages_url)
    webbrowser.open(STREAMLIT_DEPLOY)
    url_txt = URL_FILE.resolve()
    if sys.platform == "win32":
        subprocess.Popen(["notepad.exe", str(url_txt)])


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("  ロト6予想 - 常時アクセス自動設定")
    print("  PCの電源が切れていてもスマホから使えます")
    print("=" * 60)
    print()

    if not have_cmd("git"):
        print("エラー: Git がインストールされていません。")
        print("https://git-scm.com/download/win からインストールしてください。")
        return 1

    if not have_cmd("gh"):
        print("エラー: GitHub CLI (gh) が必要です。")
        print("https://cli.github.com/ からインストール後、gh auth login を実行してください。")
        return 1

    auth = gh("auth", "status", check=False, capture=True)
    if auth.returncode != 0:
        print("GitHub にログインしていません。次を実行してください:")
        print("  gh auth login")
        return 1

    try:
        owner = get_github_user()
        print(f"GitHub アカウント: {owner}")
        print()

        ensure_git_repo()
        ensure_commit()
        repo = create_or_push_repo(owner)
        pages_url = enable_github_pages(owner)
        trigger_pages_workflow(owner)

        save_urls(pages_url, STREAMLIT_DEPLOY, repo)

        print()
        print("完全自動化をインストール中...")
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "install_full_automation.py")],
                cwd=ROOT,
                check=False,
            )
        except Exception:
            pass

        print()
        print("設定完了！ 以降は完全自動です（何もしなくてOK）。")
        print(f"URL一覧: {URL_FILE}")
        open_results(pages_url)
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\nエラー: コマンド失敗 ({e.cmd})")
        if e.stderr:
            print(e.stderr)
        if e.stdout:
            print(e.stdout)
        return 1
    except Exception as e:
        print(f"\nエラー: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
