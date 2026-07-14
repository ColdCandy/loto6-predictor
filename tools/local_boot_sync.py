#!/usr/bin/env python3
"""PCでロト6を動かしたときのローカル起動同期:

方針: クラウド（GitHub Actions）が正本。
PCはクラウドに合わせて取り込む。

1. クラウドから最新の当選・学習・AI本命を取得（git pull）
2. オフラインHTMLを再生成（取り込まれたデータで）
3. （任意）手元でも公式CSVを軽く確認更新 ※通常はクラウドへは戻さない
4. （任意）--train で手元学習 / --push でクラウドへ書き戻し

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
    dirty = run(["git", "status", "--porcelain"])
    stashed = False
    if dirty.stdout.strip():
        run(["git", "stash", "push", "-u", "-m", "boot-sync-temp"])
        stashed = True
    try:
        r = run(["git", "pull", "--ff-only", "origin", "main"], timeout=120)
        if r.returncode != 0:
            r = run(["git", "pull", "origin", "main"], timeout=120)
        ok = r.returncode == 0
        detail = (r.stdout or r.stderr or "").strip().splitlines()
        msg = detail[-1] if detail else ("ok" if ok else "pull失敗")
        return ok, msg
    finally:
        if stashed:
            run(["git", "stash", "pop"], timeout=60)


def refresh_csv_local() -> tuple[bool, str]:
    """手元の確認用。結果は通常クラウドへ上げない。"""
    try:
        from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv, load_draws

        before = DEFAULT_DATA_PATH.stat().st_mtime if DEFAULT_DATA_PATH.exists() else 0
        download_csv(DEFAULT_DATA_PATH)
        after = DEFAULT_DATA_PATH.stat().st_mtime if DEFAULT_DATA_PATH.exists() else 0
        draws = load_draws(auto_refresh=False)
        latest = draws[-1].round_num if draws else "?"
        if after != before:
            return True, f"手元CSV更新（第{latest}回）"
        return True, f"手元CSVは最新（第{latest}回）"
    except Exception as e:
        return False, f"手元CSV確認スキップ: {e}"


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
    ]
    run(["git", "add", *paths])
    status = run(["git", "diff", "--cached", "--quiet"])
    if status.returncode == 0:
        return False, "戻す変更なし"
    round_num = "?"
    try:
        from loto6_predictor.data import load_draws

        draws = load_draws(auto_refresh=False)
        if draws:
            round_num = str(draws[-1].round_num)
    except Exception:
        pass
    msg = f"local-boot: 第{round_num}回 手元更新を同期"
    c = run(["git", "commit", "-m", msg])
    if c.returncode != 0:
        return False, "commitスキップ"
    p = run(["git", "push", "origin", "HEAD:main"], timeout=120)
    if p.returncode != 0:
        return False, (p.stderr or "push失敗")[-300:]
    return True, "GitHubへ書き戻し完了"


def rebuild_html() -> tuple[bool, str]:
    script = ROOT / "tools" / "build_standalone.py"
    if not script.exists():
        return False, "build無し"
    r = run([sys.executable, str(script)], timeout=180)
    return r.returncode == 0, "HTML更新" if r.returncode == 0 else "HTML更新失敗"


def sync_on_boot(*, train: bool = False, push: bool = False, refresh_csv: bool = True) -> dict:
    """起動時同期。既定はクラウド合わせ（pull）のみ。"""
    result = {
        "ok": False,
        "mode": "cloud-first",
        "started_at": _now().strftime("%Y/%m/%d %H:%M:%S"),
        "pull": None,
        "csv": None,
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
        log("PC起動同期: クラウドに合わせて取り込む")
        log("=" * 56)

        ok_pull, pull_msg = git_pull()
        result["pull"] = {"ok": ok_pull, "detail": pull_msg}
        log(f"クラウド取得: {pull_msg}")

        if refresh_csv:
            ok_csv, csv_msg = refresh_csv_local()
            result["csv"] = {"ok": ok_csv, "detail": csv_msg}
            log(f"手元確認: {csv_msg}")

        if train:
            ok_imp, imp_msg = run_improve(light=True)
            result["improve"] = {"ok": ok_imp, "detail": imp_msg}
            log(f"手元学習: {imp_msg}")
        else:
            result["improve"] = {
                "ok": True,
                "detail": "クラウドの学習結果を使用（手元再学習なし）",
            }
            log(result["improve"]["detail"])

        if push:
            ok_push, push_msg = push_data_updates()
            result["push"] = {"ok": ok_push, "detail": push_msg}
            log(f"クラウドへ書き戻し: {push_msg}")
        else:
            result["push"] = {
                "ok": True,
                "detail": "書き戻しなし（クラウド正本のまま）",
            }
            log(result["push"]["detail"])

        ok_html, html_msg = rebuild_html()
        result["html"] = {"ok": ok_html, "detail": html_msg}
        log(f"サイトHTML: {html_msg}")

        result["ok"] = bool(ok_pull or (result.get("csv") or {}).get("ok"))
        result["message"] = (
            "起動同期完了（パソコンをクラウドに合わせました）"
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
    train = "--train" in sys.argv or "--full" in sys.argv
    push = "--push" in sys.argv
    no_csv = "--no-csv" in sys.argv
    result = sync_on_boot(train=train, push=push, refresh_csv=not no_csv)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
