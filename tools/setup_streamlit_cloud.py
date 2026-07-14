#!/usr/bin/env python3
"""Streamlit Cloud 用の半自動セットアップ

- Redeploy: GitHub に push すれば Cloud が自動再デプロイ（通常は手動不要）
- Secrets: パスワードを Git に置けないため完全自動不可
  → クリップボードへコピー＋管理画面を開く（貼るだけ）
"""

from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / ".streamlit" / "secrets.toml"
EXAMPLE = ROOT / ".streamlit" / "secrets.toml.example"
STREAMLIT_APP = "https://loto6-predictor-nmrmsaoqhebs2wxvbs6oin.streamlit.app/"
STREAMLIT_HOME = "https://share.streamlit.io/"
STREAMLIT_SECRETS_HINT = "https://share.streamlit.io/"


def ensure_secrets() -> Path:
    SECRETS.parent.mkdir(parents=True, exist_ok=True)
    if not SECRETS.exists():
        if not EXAMPLE.exists():
            raise FileNotFoundError("secrets.toml.example がありません")
        SECRETS.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"作成しました: {SECRETS}")
        print("先にパスワードを書き換えてから、もう一度このツールを実行してください。")
        subprocess.Popen(["notepad", str(SECRETS)])
        return SECRETS
    return SECRETS


def secrets_body_for_cloud(text: str) -> str:
    """コメント行を除いた TOML（Cloud に貼りやすい）"""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def copy_to_clipboard(text: str) -> bool:
    try:
        # PowerShell なら日本語も安定
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        if completed.returncode == 0:
            return True
    except Exception:
        pass
    try:
        import tkinter as tk

        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception as e:
        print(f"クリップボードコピー失敗: {e}")
        return False


def looks_like_default_password(text: str) -> bool:
    return "必ず変更してください" in text


def main() -> int:
    print("=" * 56)
    print("  Streamlit Cloud 半自動セットアップ")
    print("=" * 56)
    print()
    print("【自動でできること】")
    print("  ・GitHub へ push → Cloud が自動 Redeploy")
    print("  ・今回の修正も push 済みなので、再起動待ちでOKなことが多い")
    print()
    print("【自動にできないこと】")
    print("  ・Secrets（招待パスワード）の登録")
    print("    → パスワードを Git に置けないため、Cloud画面への1回貼り付けが必要")
    print()

    path = ensure_secrets()
    raw = path.read_text(encoding="utf-8")
    if looks_like_default_password(raw):
        print("⚠ secrets.toml が初期パスワードのままです。")
        print("  メモ帳で家族用パスワードに変更して保存してください。")
        subprocess.Popen(["notepad", str(path)])
        input("保存したら Enter...")
        raw = path.read_text(encoding="utf-8")
        if looks_like_default_password(raw):
            print("まだ初期パスワードのようです。変更後に再実行してください。")
            return 1

    body = secrets_body_for_cloud(raw)
    if copy_to_clipboard(body):
        print("✓ Secrets の内容をクリップボードにコピーしました")
    else:
        print("コピーに失敗したので内容を表示します:")
        print("-" * 40)
        print(body)
        print("-" * 40)

    print()
    print("次の手順（貼るだけ・約30秒）:")
    print("  1. 開いたページでアプリを選ぶ")
    print("  2. 右上 ⋮ → Settings → Secrets")
    print("  3. Ctrl+V で貼り付け → Save")
    print("  4. Reboot app（または数分待つと自動再デプロイ）")
    print()

    webbrowser.open(STREAMLIT_HOME)
    webbrowser.open(STREAMLIT_APP)

    print(f"アプリURL: {STREAMLIT_APP}")
    print("完了後、招待IDとパスワードでログインできます。")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
