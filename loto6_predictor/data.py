"""ロト6当選データの読み込み・リアルタイム更新"""

from __future__ import annotations

import csv
import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cloud import is_cloud_hosted

CSV_URL = "https://loto6.thekyo.jp/data/loto6.csv"
DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "loto6.csv"
WATCH_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "watch_state.json"

JST = timezone(timedelta(hours=9))

# リアルタイム監視間隔（秒）
POLL_DRAW_WINDOW = 30   # 抽選日 19〜22時: FX並みに30秒
POLL_DRAW_DAY = 60      # 抽選日のその他時間
POLL_NORMAL = 120       # 通常日


@dataclass(frozen=True)
class Draw:
    round_num: int
    date: str
    numbers: tuple[int, int, int, int, int, int]
    bonus: int


@dataclass
class WatchResult:
    checked_at: str
    updated: bool
    latest_round: int | None
    previous_round: int | None
    latest_date: str | None
    interval_seconds: int
    monitoring: bool
    error: str | None = None


def _now_jst() -> datetime:
    return datetime.now(JST)


def _is_draw_day() -> bool:
    return _now_jst().weekday() in (0, 3)


def realtime_poll_interval_seconds() -> int:
    """FX風リアルタイム監視のチェック間隔"""
    now = _now_jst()
    if _is_draw_day() and 19 <= now.hour < 22:
        return POLL_DRAW_WINDOW
    if _is_draw_day():
        return POLL_DRAW_DAY
    return POLL_NORMAL


def download_csv(dest: Path = DEFAULT_DATA_PATH) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Loto6Predictor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    return dest


def _parse_csv(path: Path) -> list[Draw]:
    draws: list[Draw] = []
    with path.open(encoding="cp932", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 9:
                continue
            nums = tuple(int(row[i]) for i in range(2, 8))
            draws.append(
                Draw(
                    round_num=int(row[0]),
                    date=row[1],
                    numbers=nums,  # type: ignore[arg-type]
                    bonus=int(row[8]),
                )
            )
    return draws


def _latest_draw(path: Path) -> Draw | None:
    draws = _parse_csv(path)
    return draws[-1] if draws else None


def _save_watch_state(result: WatchResult) -> None:
    if is_cloud_hosted():
        return
    try:
        WATCH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        WATCH_STATE_PATH.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_watch_state() -> WatchResult | None:
    if not WATCH_STATE_PATH.exists():
        return None
    try:
        data = json.loads(WATCH_STATE_PATH.read_text(encoding="utf-8"))
        return WatchResult(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def realtime_watch_update(force: bool = False) -> WatchResult:
    """常に最新データを確認し、変化があれば即反映（FX風リアルタイム監視）"""
    if is_cloud_hosted():
        return _cloud_watch_status()

    path = DEFAULT_DATA_PATH
    interval = realtime_poll_interval_seconds()
    now_str = _now_jst().strftime("%Y/%m/%d %H:%M:%S")
    prev_state = load_watch_state()

    if not force and prev_state and prev_state.checked_at:
        try:
            last_check = datetime.strptime(prev_state.checked_at, "%Y/%m/%d %H:%M:%S").replace(tzinfo=JST)
            if (_now_jst() - last_check).total_seconds() < interval:
                return prev_state
        except ValueError:
            pass

    old_round = _latest_draw(path).round_num if path.exists() else None
    temp = path.with_suffix(".tmp")

    try:
        download_csv(temp)
        new_draw = _latest_draw(temp)
        if new_draw is None:
            temp.unlink(missing_ok=True)
            result = WatchResult(
                checked_at=now_str,
                updated=False,
                latest_round=old_round,
                previous_round=old_round,
                latest_date=None,
                interval_seconds=interval,
                monitoring=True,
                error="データが空です",
            )
            _save_watch_state(result)
            return result

        changed = False
        if not path.exists():
            temp.replace(path)
            changed = True
        else:
            old_bytes = path.read_bytes()
            new_bytes = temp.read_bytes()
            if new_bytes != old_bytes:
                temp.replace(path)
                changed = True
            else:
                temp.unlink(missing_ok=True)

        result = WatchResult(
            checked_at=now_str,
            updated=changed,
            latest_round=new_draw.round_num,
            previous_round=old_round,
            latest_date=new_draw.date,
            interval_seconds=interval,
            monitoring=True,
        )
        _save_watch_state(result)
        return result

    except Exception as e:
        temp.unlink(missing_ok=True)
        result = WatchResult(
            checked_at=now_str,
            updated=False,
            latest_round=old_round,
            previous_round=old_round,
            latest_date=None,
            interval_seconds=interval,
            monitoring=True,
            error=str(e),
        )
        _save_watch_state(result)
        return result


def _cloud_watch_status() -> WatchResult:
    """クラウド環境: ファイル書き込みなしでステータスのみ返す"""
    path = DEFAULT_DATA_PATH
    interval = realtime_poll_interval_seconds()
    now_str = _now_jst().strftime("%Y/%m/%d %H:%M:%S")
    latest = _latest_draw(path) if path.exists() else None
    return WatchResult(
        checked_at=now_str,
        updated=False,
        latest_round=latest.round_num if latest else None,
        previous_round=latest.round_num if latest else None,
        latest_date=latest.date if latest else None,
        interval_seconds=interval,
        monitoring=True,
    )


def auto_update_if_needed(force: bool = False) -> bool:
    result = realtime_watch_update(force=force)
    return result.updated


def load_draws(path: Path = DEFAULT_DATA_PATH, auto_refresh: bool = True) -> list[Draw]:
    """当選データを読み込む。クラウドでは起動時に必ず最新CSVを取得する。"""
    if is_cloud_hosted():
        # Streamlit Cloud はローカル監視不要。毎回ネットから最新を取りに行く。
        try:
            download_csv(path)
        except Exception:
            # ネット不可時は同梱CSVにフォールバック
            pass
        if path.exists():
            return _parse_csv(path)
        return []

    if auto_refresh:
        realtime_watch_update()
    if not path.exists():
        try:
            download_csv(path)
        except OSError:
            pass
    if not path.exists():
        return []
    return _parse_csv(path)


def get_data_status() -> dict:
    path = DEFAULT_DATA_PATH
    watch = load_watch_state()
    interval = realtime_poll_interval_seconds()

    if not path.exists():
        return {
            "exists": False,
            "monitoring": True,
            "poll_seconds": interval,
        }

    latest = _latest_draw(path)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, JST)

    return {
        "exists": True,
        "rounds": len(_parse_csv(path)),
        "latest_round": latest.round_num if latest else None,
        "latest_date": latest.date if latest else None,
        "updated_at": mtime.strftime("%Y/%m/%d %H:%M"),
        "poll_seconds": interval,
        "draw_window": _is_draw_day() and 19 <= _now_jst().hour < 22,
        "monitoring": True,
        "last_check": watch.checked_at if watch else None,
        "watch_updated": watch.updated if watch else False,
        "watch_error": watch.error if watch else None,
    }


def get_monitor_live_status() -> dict:
    """UI用: 1秒ごとに更新する監視ステータス"""
    watch = load_watch_state()
    interval = realtime_poll_interval_seconds()
    now = _now_jst()
    elapsed = float(interval)

    if watch and watch.checked_at:
        try:
            last = datetime.strptime(watch.checked_at, "%Y/%m/%d %H:%M:%S").replace(tzinfo=JST)
            elapsed = (now - last).total_seconds()
        except ValueError:
            pass

    draw_window = _is_draw_day() and 19 <= now.hour < 22
    return {
        "now": now.strftime("%H:%M:%S"),
        "last_check": watch.checked_at.split(" ")[-1] if watch and watch.checked_at else "--:--:--",
        "last_check_full": watch.checked_at if watch else None,
        "poll_seconds": interval,
        "remaining": max(0, int(interval - elapsed)),
        "elapsed": int(elapsed),
        "due": elapsed >= interval,
        "draw_window": draw_window,
        "mode": "抽選時間帯" if draw_window else "通常",
        "error": watch.error if watch else None,
        "latest_round": watch.latest_round if watch else None,
        "monitoring": True,
    }


__all__ = [
    "Draw",
    "WatchResult",
    "CSV_URL",
    "DEFAULT_DATA_PATH",
    "download_csv",
    "load_draws",
    "auto_update_if_needed",
    "realtime_watch_update",
    "realtime_poll_interval_seconds",
    "load_watch_state",
    "get_data_status",
    "get_monitor_live_status",
]
