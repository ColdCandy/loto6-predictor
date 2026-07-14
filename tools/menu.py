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
  [2] 高機能GUI版 - このPCのみ（招待ログイン）
  [3] LAN公開版 - 同じWi-Fi内の端末から
  [4] 外からアクセス版 - 遠隔（PC起動中・招待ログイン）
  [5] 招待パスワード設定 - 家族用ID/パス発行
  [6] Streamlitクラウド設定 - Secrets貼り付け半自動
  [7] 常時アクセス設定 - PCオフでも使える（クラウド）
  [8] 自動で常時公開 - 今すぐクラウドへ同期
  [9] コマンドライン版
  [A] 接続を完全停止
  [0] 終了

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
        print("HTMLを生成中...")
        subprocess.call([sys.executable, str(ROOT / "tools" / "build_standalone.py")], cwd=ROOT)
    html = ROOT / "dist" / "ロト6予想.html"
    if html.exists():
        subprocess.Popen(["cmd", "/c", "start", "", str(html)], cwd=ROOT)
    else:
        print("HTMLの生成に失敗しました。")


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
        "5": lambda: run_bat("招待パスワード設定.bat"),
        "6": lambda: run_bat("Streamlitクラウド設定.bat"),
        "7": lambda: run_bat("常時アクセス設定.bat"),
        "8": lambda: run_bat("自動で常時公開.bat"),
        "9": lambda: run_bat("予想.bat"),
        "A": lambda: run_bat("接続停止.bat"),
        "a": lambda: run_bat("接続停止.bat"),
        "0": lambda: 0,
    }

    action = actions.get(choice)
    if action is None:
        print("無効な選択です。")
        return 1

    result = action()
    return 0 if result is None or result == 0 else int(result)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
