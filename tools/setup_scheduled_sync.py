#!/usr/bin/env python3
"""Windowsのタスクスケジューラに自動同期を登録"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_NAME = "Loto6CloudAutoSync"
PYTHON = sys.executable
SYNC_SCRIPT = ROOT / "tools" / "auto_sync_cloud.py"


def run_schtasks(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        encoding="cp932",
        errors="replace",
    )


def task_exists() -> bool:
    r = run_schtasks(["/Query", "/TN", TASK_NAME])
    return r.returncode == 0


def delete_task() -> None:
    if task_exists():
        run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])


def create_task() -> bool:
    tr = f'"{PYTHON}" "{SYNC_SCRIPT}" --quiet'
    r = run_schtasks([
        "/Create",
        "/TN", TASK_NAME,
        "/TR", tr,
        "/SC", "DAILY",
        "/ST", "09:00",
        "/F",
    ])
    if r.returncode != 0:
        print(f"タスク登録失敗: {r.stderr or r.stdout}")
        return False
    return True


def main() -> int:
    if sys.platform != "win32":
        print("Windows専用です")
        return 1

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 50)
    print("  自動同期スケジュール登録")
    print("=" * 50)
    print()
    print("毎日 9:00 に自動で:")
    print("  1. 最新当選データを取得")
    print("  2. GitHubへアップロード")
    print("  3. クラウドURLを自動更新")
    print()

    delete_task()
    if create_task():
        print(f"登録完了: タスク名「{TASK_NAME}」")
        print("PCが起動していれば毎日自動同期されます。")
        print("（PCがオフの日は、GitHub側の定期更新が動きます）")
        return 0

    print()
    print("手動で同期する場合 → 「自動で常時公開.bat」")
    return 1


if __name__ == "__main__":
    sys.exit(main())
