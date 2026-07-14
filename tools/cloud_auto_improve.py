#!/usr/bin/env python3
"""PCオフでも動くクラウド自動更新:

1. サイト（公式CSV）から最新当選を取得して保存
2. 新しい回が入ったら精度学習を回してモデル更新
3. 次回用のAI本命ヒントを生成して保存

GitHub Actions から呼ばれる想定。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loto6_predictor.analyzer import Loto6Analyzer
from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv, load_draws
from loto6_predictor.walkforward_trainer import (
    MODEL_PATH,
    generate_verified_prediction,
    iterative_train,
    load_model,
)

JST = timezone(timedelta(hours=9))
TIP_PATH = ROOT / "data" / "ai_next_tip.json"
STATUS_PATH = ROOT / "data" / "cloud_auto_status.json"


def _now() -> datetime:
    return datetime.now(JST)


def _save_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_csv() -> tuple[bool, int | None, int | None]:
    """最新CSVを取得。返り値: (更新したか, 旧回, 新回)"""
    old_round = None
    if DEFAULT_DATA_PATH.exists():
        old = load_draws(auto_refresh=False)
        old_round = old[-1].round_num if old else None

    download_csv(DEFAULT_DATA_PATH)
    draws = load_draws(auto_refresh=False)
    new_round = draws[-1].round_num if draws else None
    updated = old_round is None or (new_round is not None and new_round != old_round)
    return updated, old_round, new_round


def refresh_loto7() -> bool:
    try:
        from loto6_predictor.loto7_data import DEFAULT_DATA_PATH as L7
        from loto6_predictor.loto7_data import download_csv as dl7

        before = L7.stat().st_mtime if L7.exists() else 0
        dl7()
        after = L7.stat().st_mtime if L7.exists() else 0
        return after != before
    except Exception as e:
        print(f"ロト7更新スキップ: {e}")
        return False


def should_retrain(data_updated: bool, force: bool = False) -> bool:
    if force or data_updated:
        return True
    model = load_model()
    if not model:
        return True
    trained_at = model.get("trained_at")
    if not trained_at:
        return True
    try:
        # "2026/07/14 20:48"
        dt = datetime.strptime(trained_at, "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        # 3日以上古い、または毎週月曜の定時で再学習
        if (_now() - dt).total_seconds() > 3 * 24 * 3600:
            return True
        if _now().weekday() == 0 and _now().hour < 1:
            return True
    except ValueError:
        return True
    return False


def train_accuracy(draws, generations: int = 10, test_rounds: int = 80) -> dict:
    print(f"精度学習開始: {len(draws)}回分 / gen={generations} / test={test_rounds}")
    payload = iterative_train(
        draws,
        test_rounds=test_rounds,
        generations=generations,
        target_exact=1,
    )
    r = payload.get("result") or {}
    print(
        f"学習完了: pool_exact={r.get('pool_exact')} "
        f"cover={r.get('cover_mean_in_topk')} mean={r.get('main_mean')}"
    )
    return payload


def write_next_tip(draws) -> dict:
    analyzer = Loto6Analyzer(draws)
    tip = generate_verified_prediction(analyzer, seed=int(_now().timestamp()) % 100000, include_pool=True)
    model = load_model() or {}
    payload = {
        "generated_at": _now().strftime("%Y/%m/%d %H:%M"),
        "based_on_round": draws[-1].round_num if draws else None,
        "based_on_date": draws[-1].date if draws else None,
        "latest_numbers": list(draws[-1].numbers) if draws else [],
        "latest_bonus": draws[-1].bonus if draws else None,
        "name": tip.get("name"),
        "numbers": tip.get("numbers"),
        "formatted": tip.get("formatted"),
        "confidence": tip.get("confidence"),
        "confidence_label": tip.get("confidence_label"),
        "pool": tip.get("pool", [])[:12],
        "train_info": tip.get("train_info") or {},
        "model_trained_at": model.get("trained_at"),
        "disclaimer": tip.get("disclaimer"),
    }
    TIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AI本命ヒント保存: {payload['formatted']} (第{payload['based_on_round']}回時点)")
    return payload


def main() -> int:
    force = "--force" in sys.argv
    light = "--light" in sys.argv  # 抽選直後の短時間学習

    print("=" * 56)
    print("  クラウド自動更新（当選保存＋精度改善）")
    print("=" * 56)

    data_updated, old_r, new_r = refresh_csv()
    l7_updated = refresh_loto7()
    print(f"ロト6: {'更新' if data_updated else '変更なし'} ({old_r} → {new_r})")
    print(f"ロト7: {'更新' if l7_updated else '変更なし'}")

    draws = load_draws(auto_refresh=False)
    if not draws:
        print("エラー: 当選データを読めません", file=sys.stderr)
        return 1

    trained = False
    train_payload = None
    if should_retrain(data_updated, force=force):
        gens = 6 if light else 10
        tests = 60 if light else 80
        train_payload = train_accuracy(draws, generations=gens, test_rounds=tests)
        trained = True
    else:
        print("精度学習スキップ（モデルは新しい）")

    tip = write_next_tip(draws)

    pool_exact = None
    if train_payload:
        pool_exact = (train_payload.get("result") or {}).get("pool_exact")
    else:
        m = load_model() or {}
        pool_exact = (m.get("result") or {}).get("pool_exact")

    status = {
        "checked_at": _now().strftime("%Y/%m/%d %H:%M:%S"),
        "data_updated": data_updated,
        "loto7_updated": l7_updated,
        "trained": trained,
        "old_round": old_r,
        "new_round": new_r,
        "tip_formatted": tip.get("formatted"),
        "model_path": str(MODEL_PATH.relative_to(ROOT)) if MODEL_PATH.exists() else None,
        "pool_exact": pool_exact,
    }
    _save_status(status)
    print("ステータス保存:", STATUS_PATH)
    print("完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
