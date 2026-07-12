#!/usr/bin/env python3
"""完全自動化インストール（起動時・定期・抽選日すべて自動）"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
SYNC_SCRIPT = ROOT / "tools" / "auto_sync_cloud.py"
MARKER = ROOT / "data" / ".full_auto_installed"
LOG_FILE = ROOT / "data" / "auto_sync.log"

TASKS = [
    ("Loto6Cloud_LogOn", ["ONLOGON"]),
    ("Loto6Cloud_Daily", ["DAILY", "09:00"]),
    ("Loto6Cloud_DrawMon", ["WEEKLY", "MON", "21:45"]),
    ("Loto6Cloud_DrawThu", ["WEEKLY", "THU", "21:45"]),
    ("Loto6Cloud_DrawMon2", ["WEEKLY", "MON", "22:30"]),
    ("Loto6Cloud_DrawThu2", ["WEEKLY", "THU", "22:30"]),
]


def run_schtasks(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        encoding="cp932",
        errors="replace",
    )


def delete_task(name: str) -> None:
    run_schtasks(["/Delete", "/TN", name, "/F"])


def create_task(name: str, schedule: list[str]) -> bool:
    tr = f'"{PYTHON}" "{SYNC_SCRIPT}" --quiet --auto'
    args = ["/Create", "/TN", name, "/TR", tr, "/F"]
    if schedule[0] == "ONLOGON":
        args.extend(["/SC", "ONLOGON", "/DELAY", "0001:00"])
    elif schedule[0] == "DAILY":
        args.extend(["/SC", "DAILY", "/ST", schedule[1]])
    elif schedule[0] == "WEEKLY":
        args.extend(["/SC", "WEEKLY", "/D", schedule[1], "/ST", schedule[2]])
    r = run_schtasks(args)
    return r.returncode == 0


def install_startup_shortcut() -> bool:
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs" / "Startup"
    if not startup.exists():
        return False

    runner = ROOT / "tools" / "_auto_sync_silent.vbs"
    shortcut_marker = startup / "Loto6CloudAutoSync.vbs"
    content = (
        f'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run """{PYTHON}"" ""{SYNC_SCRIPT}"" --quiet --auto --startup", 0, False\n'
    )
    shortcut_marker.write_text(content, encoding="utf-8")
    runner.write_text(content, encoding="utf-8")
    return True


def ensure_cloud_repo() -> bool:
    if (ROOT / ".git").exists():
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if remote.returncode == 0:
            return True

    setup = ROOT / "tools" / "setup_cloud_deploy.py"
    if not setup.exists():
        return False
    print("初回: クラウドリポジトリを自動セットアップ中...")
    r = subprocess.run([PYTHON, str(setup)], cwd=ROOT)
    return r.returncode == 0


def run_immediate_sync() -> None:
    subprocess.run([PYTHON, str(SYNC_SCRIPT), "--quiet", "--auto"], cwd=ROOT)


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 55)
    print("  ロト6予想 - 完全自動化セットアップ")
    print("=" * 55)
    print()

    if not ensure_cloud_repo():
        print("クラウド準備に失敗しました。gh auth login を確認してください。")
        return 1

    print("スケジュールタスクを登録中...")
    for name, schedule in TASKS:
        delete_task(name)
        ok = create_task(name, schedule)
        status = "OK" if ok else "失敗"
        print(f"  [{status}] {name}")

    print()
    print("Windows起動時の自動実行を登録中...")
    if install_startup_shortcut():
        print("  [OK] スタートアップに登録しました")
    else:
        print("  [スキップ] スタートアップフォルダが見つかりません")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")

    print()
    print("初回同期を実行中...")
    run_immediate_sync()

    print()
    print("=" * 55)
    print("  完全自動化 設定完了！")
    print("=" * 55)
    print()
    print("これ以降、何もしなくてOKです:")
    print("  ・PC起動時 → 自動同期")
    print("  ・毎日9:00 → 自動同期")
    print("  ・月・木 21:45/22:30 → 抽選後に自動同期")
    print("  ・PCオフでも GitHub が毎日更新")
    print()
    print("常時アクセスURL:")
    print("  https://coldcandy.github.io/loto6-predictor/")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
