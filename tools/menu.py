#!/usr/bin/env python3
"""起動メニュー（日本語表示の文字化け・バグを防ぐ）"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MENU = """
========================================
  ロト6予想 - 起動メニュー
========================================

  [1] どこでも使える版 - HTML・Python不要
  [2] 高機能GUI版 - このPCのみ
  [3] LAN公開版 - 同じWi-Fi内の端末から
  [4] 外からアクセス版 - おばあちゃん家など遠隔（PC起動中のみ）
  [5] 常時アクセス設定 - PCオフでも使える（クラウド）
  [6] 自動で常時公開 - 今すぐクラウドへ同期
  [7] コマンドライン版
  [8] 接続を完全停止
  [9] 終了

"""


def run_bat(name: str) -> int:
    bat = ROOT / name
    if not bat.exists():
        print(f"エラー: {name} が見つかりません。")
        return 1
    return subprocess.call(["cmd", "/c", str(bat)], cwd=ROOT)


def open_html() -> None:
    html = ROOT / "dist" / "ロト6予想.html"
    if not html.exists():
        print("HTMLファイルを作成中...")
        subprocess.check_call([sys.executable, str(ROOT / "tools" / "build_standalone.py")], cwd=ROOT)
    subprocess.Popen(["cmd", "/c", "start", "", str(html)], cwd=ROOT)


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")

    print(MENU, end="")
    choice = input("番号を選んで Enter: ").strip()

    actions = {
        "1": open_html,
        "2": lambda: run_bat("予想GUI.bat"),
        "3": lambda: run_bat("LAN起動.bat"),
        "4": lambda: run_bat("外から起動.bat"),
        "5": lambda: run_bat("常時アクセス設定.bat"),
        "6": lambda: run_bat("自動で常時公開.bat"),
        "7": lambda: run_bat("予想.bat"),
        "8": lambda: run_bat("接続停止.bat"),
        "9": lambda: 0,
    }

    action = actions.get(choice)
    if action is None:
        print("無効な選択です。")
        return 1

    result = action()
    return 0 if result is None or result == 0 else result


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
