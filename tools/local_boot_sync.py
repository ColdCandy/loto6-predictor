#!/usr/bin/env python3
"""PCでロト6を動かしたときのローカル起動同期:

1. クラウド（GitHub）から最新の保存・学習結果を取得（git pull）
2. 最新当選を取得して保存
3. 必要なら学習・AI本命を更新
4. 変更があれば GitHub へ戻してクラウドと揃える
5. オフラインHTMLも再生成

Streamlit / 予想GUI.bat から呼ばれる。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))
LOG_FILE = ROOT / "data" / "local_boot_sync.log"
LOCK_FILE = ROOT / "data" / ".boot_sync_lock"
STATUS_FILE = ROOT / "data" / "local_boot_status.json"


def _now() -> datetime:
    return datetime.now(JST)


def log(msg: str) -> None:
    line = f"[{_now().strftime('%Y/%m/%d %H:%M:%S')}] {msg}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(msg, flush=True)


def run(cmd: list[str], *, check: bool = False, timeout: int | None = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            if time.time() - LOCK_FILE.stat().st_mtime < 600:
                return False
        except OSError:
            pass
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(time.time()), encoding="utf-8")
    return True


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


def save_status(payload: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def git_pull() -> tuple[bool, str]:
    if not (ROOT / ".git").exists():
        return False, "Git未初期化"
    # 作業ツリーの汚れで pull が止まらないよう stash
    dirty = run(["git", "status", "--porcelain"])
    stashed = False
    if dirty.stdout.strip():
        run(["git", "stash", "push", "-u", "-m", "boot-sync-temp"])
        stashed = True
    try:
        r = run(["git", "pull", "--ff-only", "origin", "main"], timeout=120)
        if r.returncode != 0:
            # リベース無しの通常 pull を再試行
            r = run(["git", "pull", "origin", "main"], timeout=120)
        ok = r.returncode == 0
        detail = (r.stdout or r.stderr or "").strip().splitlines()
        msg = detail[-1] if detail else ("ok" if ok else "pull失敗")
        return ok, msg
    finally:
        if stashed:
            run(["git", "stash", "pop"], timeout=60)


def run_improve(light: bool = True) -> tuple[bool, str]:
    cmd = [sys.executable, str(ROOT / "tools" / "cloud_auto_improve.py")]
    if light:
        cmd.append("--light")
    r = run(cmd, timeout=900)
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    tip = ""
    for line in out.splitlines():
        if "AI本命ヒント保存:" in line or "ロト6:" in line or "学習" in line:
            tip = line
    if r.returncode != 0:
        return False, out[-500:] or "学習・保存失敗"
    return True, tip or "学習・保存完了"


def push_data_updates() -> tuple[bool, str]:
    if not (ROOT / ".git").exists():
        return False, "Git未初期化"
    paths = [
        "data/loto6.csv",
        "data/loto7.csv",
        "data/ai_trained_model.json",
        "data/ai_next_tip.json",
        "data/cloud_auto_status.json",
        "data/walkforward_verify.json",
        "data/local_boot_status.json",
    ]
    run(["git", "add", *paths])
    status = run(["git", "diff", "--cached", "--quiet"])
    if status.returncode == 0:
        return False, "クラウドへ戻す変更なし"
    round_num = "?"
    try:
        from loto6_predictor.data import load_draws

        draws = load_draws(auto_refresh=False)
        if draws:
            round_num = str(draws[-1].round_num)
    except Exception:
        pass
    msg = f"local-boot: 第{round_num}回 保存・学習同期"
    c = run(["git", "commit", "-m", msg])
    if c.returncode != 0:
        return False, "commitスキップ"
    p = run(["git", "push", "origin", "HEAD:main"], timeout=120)
    if p.returncode != 0:
        return False, (p.stderr or "push失敗")[-300:]
    return True, "GitHubへ同期完了"


def rebuild_html() -> tuple[bool, str]:
    script = ROOT / "tools" / "build_standalone.py"
    if not script.exists():
        return False, "build無し"
    r = run([sys.executable, str(script)], timeout=180)
    return r.returncode == 0, "HTML更新" if r.returncode == 0 else "HTML更新失敗"


def sync_on_boot(*, light: bool = True) -> dict:
    """起動時同期の本体。結果dictを返す。"""
    result = {
        "ok": False,
        "started_at": _now().strftime("%Y/%m/%d %H:%M:%S"),
        "pull": None,
        "improve": None,
        "push": None,
        "html": None,
        "finished_at": None,
        "message": "",
    }
    if not acquire_lock():
        result["message"] = "別の起動同期が実行中です"
        save_status(result)
        return result

    try:
        log("=" * 56)
        log("PC起動同期: クラウド取得 → 保存 → 学習 → 予想更新")
        log("=" * 56)

        ok_pull, pull_msg = git_pull()
        result["pull"] = {"ok": ok_pull, "detail": pull_msg}
        log(f"クラウド取得: {pull_msg}")

        ok_imp, imp_msg = run_improve(light=light)
        result["improve"] = {"ok": ok_imp, "detail": imp_msg}
        log(f"保存・学習: {imp_msg}")

        ok_push, push_msg = push_data_updates()
        result["push"] = {"ok": ok_push, "detail": push_msg}
        log(f"クラウドへ戻す: {push_msg}")

        ok_html, html_msg = rebuild_html()
        result["html"] = {"ok": ok_html, "detail": html_msg}
        log(f"サイトHTML: {html_msg}")

        result["ok"] = bool(ok_imp)
        result["message"] = (
            "起動同期完了（データ保存・学習・予想更新）"
            if result["ok"]
            else "起動同期は一部失敗しました（アプリは続行可）"
        )
        result["finished_at"] = _now().strftime("%Y/%m/%d %H:%M:%S")
        save_status(result)
        log(result["message"])
        return result
    except Exception as e:
        result["message"] = f"起動同期エラー: {e}"
        result["finished_at"] = _now().strftime("%Y/%m/%d %H:%M:%S")
        save_status(result)
        log(result["message"])
        return result
    finally:
        release_lock()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    light = "--full" not in sys.argv
    result = sync_on_boot(light=light)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
