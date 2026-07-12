"""お気に入り番号の保存"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FAVORITES_PATH = Path(__file__).resolve().parent.parent / "data" / "favorites.json"
JST = timezone(timedelta(hours=9))


def load_favorites() -> list[dict]:
    if not FAVORITES_PATH.exists():
        return []
    try:
        data = json.loads(FAVORITES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_favorite(numbers: list[int], label: str = "", method: str = "") -> dict:
    favs = load_favorites()
    entry = {
        "numbers": sorted(numbers),
        "formatted": " ".join(f"{n:02d}" for n in sorted(numbers)),
        "label": label or f"保存 {len(favs) + 1}",
        "method": method,
        "saved_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
    }
    favs.insert(0, entry)
    favs = favs[:30]
    FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAVORITES_PATH.write_text(json.dumps(favs, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def delete_favorite(index: int) -> bool:
    favs = load_favorites()
    if 0 <= index < len(favs):
        favs.pop(index)
        FAVORITES_PATH.write_text(json.dumps(favs, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    return False
