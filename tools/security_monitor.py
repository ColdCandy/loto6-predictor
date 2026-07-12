#!/usr/bin/env python3
"""接続監視・攻撃検知時の自動サーバー停止"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "security_events.jsonl"
SHUTDOWN_FLAG = ROOT / "data" / "emergency_shutdown.flag"

PORT = 8501
CHECK_INTERVAL = 10
WARMUP_SECONDS = 60

# 外部（インターネット）からの攻撃検知用 ※127.0.0.1はStreamlit正常動作なので除外
MAX_EXTERNAL_TOTAL = 30
MAX_EXTERNAL_PER_IP = 20
MAX_EXTERNAL_UNIQUE_IPS = 15
MAX_EXTERNAL_SURGE = 40
STRIKES_BEFORE_SHUTDOWN = 5

JST = timezone(timedelta(hours=9))
_monitor_thread: threading.Thread | None = None
_shutdown_triggered = False
_monitor_started_at: float | None = None


@dataclass
class ConnectionSnapshot:
    total: int
    local_loopback: int
    lan_connections: int
    external_total: int
    by_ip: dict[str, int]
    external_by_ip: dict[str, int]
    unique_external_ips: int


@dataclass
class SecurityCheck:
    safe: bool
    reason: str | None
    snapshot: ConnectionSnapshot


def _run_netstat() -> str:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="cp932",
        errors="replace",
    )
    return result.stdout


def _parse_ip(addr: str) -> str:
    if addr.startswith("[") and "]:" in addr:
        return addr.split("]:")[0] + "]"
    if addr.count(":") == 1:
        return addr.rsplit(":", 1)[0]
    return addr


def _is_loopback(ip: str) -> bool:
    return ip in ("127.0.0.1", "::1")


def _is_private_lan(ip: str) -> bool:
    if ip.startswith("192.168.") or ip.startswith("10."):
        return True
    if ip.startswith("172."):
        parts = ip.split(".")
        if len(parts) >= 2:
            try:
                return 16 <= int(parts[1]) <= 31
            except ValueError:
                pass
    return False


def _is_external_ip(ip: str) -> bool:
    return not _is_loopback(ip) and not _is_private_lan(ip)


def get_connection_snapshot(port: int = PORT) -> ConnectionSnapshot:
    token = f":{port}"
    established: list[str] = []

    for line in _run_netstat().splitlines():
        upper = line.upper()
        if token not in line or "ESTABLISHED" not in upper:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr, remote_addr = parts[1], parts[2]
        if token in local_addr:
            remote_ip = _parse_ip(remote_addr)
        elif token in remote_addr:
            remote_ip = _parse_ip(local_addr)
        else:
            continue
        established.append(remote_ip)

    counter = Counter(established)
    loopback = sum(n for ip, n in counter.items() if _is_loopback(ip))
    lan = sum(n for ip, n in counter.items() if _is_private_lan(ip))
    external = {ip: n for ip, n in counter.items() if _is_external_ip(ip)}

    return ConnectionSnapshot(
        total=len(established),
        local_loopback=loopback,
        lan_connections=lan,
        external_total=sum(external.values()),
        by_ip=dict(counter),
        external_by_ip=external,
        unique_external_ips=len(external),
    )


def evaluate_threat(
    snapshot: ConnectionSnapshot,
    external_history: deque[int],
) -> SecurityCheck:
    # Streamlit・Cloudflareトンネルは127.0.0.1接続が増えるのが正常 → 外部IPのみ監視

    if snapshot.external_total > MAX_EXTERNAL_TOTAL:
        return SecurityCheck(
            False,
            f"外部接続数異常: {snapshot.external_total}件（上限{MAX_EXTERNAL_TOTAL}）",
            snapshot,
        )

    if snapshot.unique_external_ips > MAX_EXTERNAL_UNIQUE_IPS:
        return SecurityCheck(
            False,
            f"外部IP过多: {snapshot.unique_external_ips}件（上限{MAX_EXTERNAL_UNIQUE_IPS}）",
            snapshot,
        )

    for ip, count in snapshot.external_by_ip.items():
        if count > MAX_EXTERNAL_PER_IP:
            return SecurityCheck(
                False,
                f"外部IPからの集中アクセス: {ip} ({count}件)",
                snapshot,
            )

    if len(external_history) >= 6:
        surge = external_history[-1] - external_history[0]
        if surge >= MAX_EXTERNAL_SURGE:
            return SecurityCheck(
                False,
                f"外部接続の急増: +{surge}件/分",
                snapshot,
            )

    return SecurityCheck(True, None, snapshot)


def _log_event(event: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def emergency_shutdown(reason: str) -> None:
    global _shutdown_triggered
    if _shutdown_triggered:
        return
    _shutdown_triggered = True

    now = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")
    event = {"time": now, "action": "emergency_shutdown", "reason": reason}
    _log_event(event)

    SHUTDOWN_FLAG.write_text(
        json.dumps(event, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("  !!! 攻撃の可能性を検知 - サーバーを自動停止します !!!")
    print("=" * 60)
    print(f"  理由: {reason}")
    print(f"  時刻: {now}")
    print("  接続停止を実行しています...")
    print("=" * 60)
    print()

    from tools.stop_server import stop_all

    stop_all()
    os._exit(2)


def _monitor_loop() -> None:
    global _monitor_started_at
    external_history: deque[int] = deque(maxlen=6)
    strikes = 0

    while not _shutdown_triggered:
        try:
            if _monitor_started_at and time.time() - _monitor_started_at < WARMUP_SECONDS:
                time.sleep(CHECK_INTERVAL)
                continue

            snapshot = get_connection_snapshot()
            external_history.append(snapshot.external_total)
            check = evaluate_threat(snapshot, external_history)

            if check.safe:
                strikes = 0
            else:
                strikes += 1
                _log_event(
                    {
                        "time": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
                        "action": "threat_detected",
                        "reason": check.reason,
                        "total_connections": snapshot.total,
                        "local_loopback": snapshot.local_loopback,
                        "external_connections": snapshot.external_total,
                        "strike": strikes,
                    }
                )
                print(f"[セキュリティ警告] {check.reason} ({strikes}/{STRIKES_BEFORE_SHUTDOWN})")

                if strikes >= STRIKES_BEFORE_SHUTDOWN:
                    emergency_shutdown(check.reason or "不明な攻撃パターン")

        except Exception as e:
            _log_event(
                {
                    "time": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
                    "action": "monitor_error",
                    "error": str(e),
                }
            )

        time.sleep(CHECK_INTERVAL)


def start_security_monitor() -> threading.Thread:
    global _monitor_thread, _monitor_started_at
    if _monitor_thread and _monitor_thread.is_alive():
        return _monitor_thread

    if SHUTDOWN_FLAG.exists():
        SHUTDOWN_FLAG.unlink(missing_ok=True)

    _monitor_started_at = time.time()

    _log_event(
        {
            "time": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
            "action": "monitor_started",
            "port": PORT,
            "note": "127.0.0.1接続は正常動作として除外",
        }
    )

    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        daemon=True,
        name="loto6-security",
    )
    _monitor_thread.start()
    return _monitor_thread


def get_security_status() -> dict:
    snapshot = get_connection_snapshot()
    return {
        "active": _monitor_thread is not None and _monitor_thread.is_alive(),
        "connections": snapshot.total,
        "local_connections": snapshot.local_loopback,
        "external_connections": snapshot.external_total,
        "unique_ips": snapshot.unique_external_ips,
        "max_external": MAX_EXTERNAL_TOTAL,
        "check_interval": CHECK_INTERVAL,
        "shutdown_flag": SHUTDOWN_FLAG.exists(),
    }
