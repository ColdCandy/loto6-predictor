"""ロト7当選データの読み込み"""

from __future__ import annotations

import csv
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .cloud import is_cloud_hosted

CSV_URL = "https://loto7.thekyo.jp/data/loto7.csv"
DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "loto7.csv"


@dataclass(frozen=True)
class Loto7Draw:
    round_num: int
    date: str
    numbers: tuple[int, int, int, int, int, int, int]
    bonus: tuple[int, int]


def download_csv(dest: Path = DEFAULT_DATA_PATH) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Loto6Predictor/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    return dest


def _parse_csv(path: Path) -> list[Loto7Draw]:
    draws: list[Loto7Draw] = []
    with path.open(encoding="cp932", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 11:
                continue
            nums = tuple(int(row[i]) for i in range(2, 9))
            bonus = (int(row[9]), int(row[10]))
            draws.append(
                Loto7Draw(
                    round_num=int(row[0]),
                    date=row[1],
                    numbers=nums,
                    bonus=bonus,
                )
            )
    return draws


def load_draws(path: Path = DEFAULT_DATA_PATH, auto_refresh: bool = True) -> list[Loto7Draw]:
    if is_cloud_hosted():
        auto_refresh = False
    if auto_refresh or not path.exists():
        try:
            download_csv(path)
        except Exception:
            if not path.exists():
                return []
    if not path.exists():
        return []
    return _parse_csv(path)


def get_data_status(path: Path = DEFAULT_DATA_PATH) -> dict:
    if not path.exists():
        return {"exists": False}

    draws = _parse_csv(path)
    latest = draws[-1] if draws else None
    from datetime import datetime, timedelta, timezone

    jst = timezone(timedelta(hours=9))
    mtime = datetime.fromtimestamp(path.stat().st_mtime, jst)

    return {
        "exists": True,
        "rounds": len(draws),
        "latest_round": latest.round_num if latest else None,
        "latest_date": latest.date if latest else None,
        "updated_at": mtime.strftime("%Y/%m/%d %H:%M"),
    }
