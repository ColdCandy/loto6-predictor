#!/usr/bin/env python3
"""単体HTMLファイルを生成（Python不要・どこでも使える版）"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loto6_predictor.data import auto_update_if_needed, load_draws

WEB_DIR = ROOT / "web"
DIST_DIR = ROOT / "dist"
TEMPLATE = WEB_DIR / "template.html"
APP_JS = WEB_DIR / "app.js"
APPLE_CSS = WEB_DIR / "apple_theme.css"
ULTRA_CSS = WEB_DIR / "ultra_smooth.css"
ULTRA_JS = WEB_DIR / "ultra_smooth.js"
OUTPUT = DIST_DIR / "ロト6予想.html"
TIP_PATH = ROOT / "data" / "ai_next_tip.json"
STATUS_PATH = ROOT / "data" / "cloud_auto_status.json"


def draws_to_json(draws) -> dict:
    tip = None
    if TIP_PATH.exists():
        try:
            tip = json.loads(TIP_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            tip = None
    status = None
    if STATUS_PATH.exists():
        try:
            status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            status = None

    latest = draws[-1]
    return {
        "updated": date.today().isoformat(),
        "source": "https://loto6.thekyo.jp/data/loto6.csv",
        "rounds": len(draws),
        "draws": [
            {"r": d.round_num, "d": d.date, "n": list(d.numbers), "b": d.bonus}
            for d in draws
        ],
        "ai_tip": tip,
        "auto_status": status,
        "latest": {
            "r": latest.round_num,
            "d": latest.date,
            "n": list(latest.numbers),
            "b": latest.bonus,
        },
    }


def build(update: bool = False) -> Path:
    if update:
        auto_update_if_needed(force=True)
    else:
        auto_update_if_needed()

    draws = load_draws(auto_refresh=False)
    if not draws:
        raise RuntimeError("当選データを読み込めませんでした")

    data = draws_to_json(draws)
    template = TEMPLATE.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")
    ultra_js = ULTRA_JS.read_text(encoding="utf-8") if ULTRA_JS.exists() else ""
    apple_css = APPLE_CSS.read_text(encoding="utf-8")
    if ULTRA_CSS.exists():
        apple_css += "\n" + ULTRA_CSS.read_text(encoding="utf-8")

    data_script = (
        f"<script>const LOTODATA = {json.dumps(data, ensure_ascii=False, separators=(',', ':'))};</script>"
    )
    app_script = f"<script>\n{app_js}\n</script>"
    ultra_script = f"<script>\n{ultra_js}\n</script>" if ultra_js else ""
    css_block = f"<style>\n{apple_css}\n</style>"

    html = template.replace("<!--APPLE_CSS_PLACEHOLDER-->", css_block)
    html = html.replace("<!--LOTODATA_PLACEHOLDER-->", data_script)
    html = html.replace("<!--APPJS_PLACEHOLDER-->", app_script + ultra_script)
    tip_note = ""
    if data.get("ai_tip"):
        tip_note = f"｜AI本命更新 {data['ai_tip'].get('generated_at', '')}"
    html = html.replace(
        "<!--DATA_SOURCE-->",
        f"第1回〜第{draws[-1].round_num}回 ({len(draws)}回分){tip_note}",
    )

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"生成完了: {OUTPUT}")
    print(f"  サイズ: {size_kb:.0f} KB")
    print(f"  データ: 第1回 〜 第{draws[-1].round_num}回")
    if data.get("ai_tip"):
        print(f"  AI本命: {data['ai_tip'].get('formatted')}")
    return OUTPUT


if __name__ == "__main__":
    update = "--update" in sys.argv
    build(update=update)
