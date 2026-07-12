"""バックグラウンドでリアルタイムデータ監視"""

from __future__ import annotations

import threading
import time

from loto6_predictor.data import realtime_poll_interval_seconds, realtime_watch_update

_monitor_thread: threading.Thread | None = None


def _monitor_loop() -> None:
    while True:
        try:
            realtime_watch_update(force=True)
        except Exception:
            pass
        time.sleep(realtime_poll_interval_seconds())


def start_background_monitor() -> threading.Thread:
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return _monitor_thread

    realtime_watch_update(force=True)
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True, name="loto6-realtime")
    _monitor_thread.start()
    return _monitor_thread
