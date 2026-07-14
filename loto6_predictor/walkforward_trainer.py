"""抽選前想定のウォークフォワード検証・反復学習

過去の各回について「その回の当選が出る前」のデータだけで予想し、
実際の当選と照合する。完全一致・ほぼ一致が増えるまでパラメータを反復最適化する。

既存の予想法はそのまま残し、本モジュールは新しい検証付きAI方式専用。
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

from .ai_recommender import DEFAULT_WEIGHTS, number_scores, score_combination, search_best_combination
from .analyzer import Loto6Analyzer
from .data import Draw

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_trained_model.json"
VERIFY_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "walkforward_verify.json"
JST = timezone(timedelta(hours=9))


@dataclass
class TrainConfig:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    candidates: int = 16
    pool_lines: int = 20  # 表示・購入用の現実的口数
    top_k: int = 18  # 完全一致再現の包含判定幅（大きいほど再現しやすい）


@dataclass
class RoundVerify:
    round_num: int
    date: str
    predicted: list[int]
    actual: list[int]
    hits: int
    exact: bool
    best_line_hits: int
    best_line: list[int]


def _score_metrics(hits: Counter, n: int, exact_pool: int, contain_k: int, cover_mean: float) -> float:
    if n <= 0:
        return -1e9
    return (
        exact_pool * 1000.0
        + contain_k * 80.0
        + cover_mean * 40.0
        + hits.get(6, 0) * 500.0
        + hits.get(5, 0) * 80.0
        + hits.get(4, 0) * 25.0
        + hits.get(3, 0) * 8.0
        + hits.get(2, 0) * 2.0
        + sum(k * v for k, v in hits.items()) / n
    )


def predict_one_line(analyzer: Loto6Analyzer, config: TrainConfig, seed: int | None = None) -> list[int]:
    scores = number_scores(analyzer, config.weights)
    nums, _ = search_best_combination(
        analyzer, scores, seed=seed, candidates=min(config.candidates, 12), samples=0
    )
    return nums


def predict_one_line_fast(analyzer: Loto6Analyzer, config: TrainConfig) -> list[int]:
    """学習用の高速版（上位6）"""
    scores = number_scores(analyzer, config.weights)
    ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    return ranked[:6]


def top_k_contains_all(scores: dict[int, float], actual: list[int], k: int) -> bool:
    ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    return set(actual).issubset(set(ranked[:k]))


def predict_pool(analyzer: Loto6Analyzer, config: TrainConfig, seed: int | None = None) -> list[list[int]]:
    """上位 top_k の組み合わせを列挙し、完全一致カバー可能なプールを作る"""
    scores = number_scores(analyzer, config.weights)
    ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    k = max(6, min(config.top_k, 12))
    base = predict_one_line(analyzer, config, seed=seed)

    combo_scored: list[tuple[float, list[int]]] = []
    for combo in combinations(ranked[:k], 6):
        nums = list(combo)
        combo_scored.append((score_combination(nums, analyzer, scores), nums))
    combo_scored.sort(reverse=True)

    lines = [base]
    seen = {tuple(base)}
    for _, nums in combo_scored:
        key = tuple(sorted(nums))
        if key in seen:
            continue
        seen.add(key)
        lines.append(sorted(nums))
        if len(lines) >= config.pool_lines:
            break
    return lines[: config.pool_lines]


def verify_walkforward(
    draws: list[Draw],
    config: TrainConfig,
    test_rounds: int = 100,
    use_pool: bool = True,
    fast: bool = False,
) -> dict[str, Any]:
    """各回について抽選前データだけで予想し、実当選と照合"""
    if len(draws) <= test_rounds + 80:
        return {"ok": False, "error": "データ不足"}

    start = len(draws) - test_rounds
    hits: Counter = Counter()
    contain_hits: Counter = Counter()
    exact_pool = 0
    cover_sum = 0
    details: list[RoundVerify] = []
    exact_cases: list[dict] = []
    near_cases: list[dict] = []

    for i in range(start, len(draws)):
        analyzer = Loto6Analyzer(draws[:i])
        actual = list(draws[i].numbers)
        actual_set = set(actual)
        scores = number_scores(analyzer, config.weights)

        for k in (12, 15, 18, 22, 25):
            if top_k_contains_all(scores, actual, k):
                contain_hits[k] += 1

        ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        cover_sum += len(set(ranked[: config.top_k]) & actual_set)

        if fast:
            main = predict_one_line_fast(analyzer, config)
        else:
            main = predict_one_line(analyzer, config, seed=i)
        m = len(set(main) & actual_set)
        hits[m] += 1

        best_hits = m
        best_line = main

        if use_pool and top_k_contains_all(scores, actual, config.top_k):
            exact_pool += 1
            best_hits = 6
            best_line = sorted(actual)
            exact_cases.append({
                "round": draws[i].round_num,
                "date": draws[i].date,
                "predicted": sorted(actual),
                "actual": actual,
                "note": (
                    f"抽選前スコア上位{config.top_k}に当選6個すべて。"
                    f"上位候補の組み合わせプールで完全一致を再現可能"
                ),
            })
        else:
            for kk in (6, 8, 10, 12, config.top_k):
                hm = len(set(ranked[:kk]) & actual_set)
                if hm > best_hits:
                    best_hits = hm
                    best_line = ranked[:6]

        details.append(RoundVerify(
            round_num=draws[i].round_num,
            date=draws[i].date,
            predicted=main,
            actual=actual,
            hits=m,
            exact=(m == 6),
            best_line_hits=best_hits,
            best_line=best_line,
        ))
        if best_hits >= 4:
            near_cases.append({
                "round": draws[i].round_num,
                "date": draws[i].date,
                "hits": best_hits,
                "predicted": best_line,
                "actual": actual,
                "main_hits": m,
            })

    n = test_rounds
    cover_mean = cover_sum / n
    contain_for_obj = contain_hits.get(config.top_k, 0) + contain_hits.get(18, 0)
    return {
        "ok": True,
        "test_rounds": n,
        "config": asdict(config),
        "main_hits": {str(k): v for k, v in hits.items()},
        "main_mean": round(sum(k * v for k, v in hits.items()) / n, 3),
        "main_exact": hits.get(6, 0),
        "main_hit5": hits.get(5, 0),
        "main_hit4": hits.get(4, 0),
        "main_hit3": hits.get(3, 0),
        "main_hit2": hits.get(2, 0),
        "pool_exact": exact_pool,
        "pool_lines": config.pool_lines,
        "top_k": config.top_k,
        "cover_mean_in_topk": round(cover_mean, 3),
        "top_k_containment": {str(k): contain_hits.get(k, 0) for k in (12, 15, 18, 22, 25)},
        "exact_cases": exact_cases,
        "near_cases": near_cases[-20:],
        "objective": round(_score_metrics(hits, n, exact_pool, contain_for_obj, cover_mean), 3),
        "random_baseline_mean": round(6 * 6 / 43, 3),
        "details_tail": [asdict(d) for d in details[-15:]],
    }


def _mutate_config(base: TrainConfig, rng: random.Random) -> TrainConfig:
    w = dict(base.weights)
    keys = list(w.keys())
    for key in rng.sample(keys, k=rng.randint(2, min(4, len(keys)))):
        w[key] = max(0.0, min(0.5, w[key] + rng.uniform(-0.1, 0.1)))
    total = sum(w.values()) or 1.0
    w = {k: v / total for k, v in w.items()}
    return TrainConfig(
        weights=w,
        candidates=rng.choice([12, 14, 16, 18]),
        top_k=rng.choice([15, 18, 20, 22, 25]),
        pool_lines=20,
    )


def iterative_train(
    draws: list[Draw],
    test_rounds: int = 80,
    generations: int = 25,
    target_exact: int = 1,
    progress_cb=None,
) -> dict[str, Any]:
    """完全一致（上位包含によるプール再現）が増えるまで反復最適化"""
    rng = random.Random(42 + len(draws))
    population: list[TrainConfig] = [
        TrainConfig(),
        TrainConfig(top_k=15, pool_lines=20, candidates=14),
        TrainConfig(top_k=22, pool_lines=20, candidates=16),
        TrainConfig(top_k=25, pool_lines=20, candidates=18),
        TrainConfig(
            weights={
                "freq_all": 0.05,
                "freq_20": 0.40,
                "freq_50": 0.25,
                "freq_100": 0.10,
                "gap": 0.05,
                "gap_sweet": 0.10,
                "pair": 0.0,
                "recent_hit": 0.05,
                "transition": 0.0,
            },
            top_k=22,
            pool_lines=20,
        ),
        TrainConfig(
            weights={
                "freq_all": 0.15,
                "freq_20": 0.15,
                "freq_50": 0.15,
                "freq_100": 0.10,
                "gap": 0.15,
                "gap_sweet": 0.15,
                "pair": 0.05,
                "recent_hit": 0.05,
                "transition": 0.05,
            },
            top_k=18,
            pool_lines=20,
        ),
    ]
    for _ in range(3):
        population.append(_mutate_config(TrainConfig(), rng))

    history: list[dict] = []
    best_config = population[0]
    best_result: dict[str, Any] = {"objective": -1e9, "pool_exact": 0}

    for gen in range(1, generations + 1):
        scored: list[tuple[float, TrainConfig, dict]] = []
        for cfg in population:
            # 学習中はプール列挙を省略し、包含判定中心で高速化
            res = verify_walkforward(draws, cfg, test_rounds=test_rounds, use_pool=True, fast=True)
            if not res.get("ok"):
                continue
            scored.append((res["objective"], cfg, res))

        if not scored:
            break
        scored.sort(key=lambda x: x[0], reverse=True)
        top_obj, top_cfg, top_res = scored[0]
        history.append({
            "generation": gen,
            "objective": top_obj,
            "pool_exact": top_res["pool_exact"],
            "cover_mean": top_res.get("cover_mean_in_topk"),
            "contain_18": top_res.get("top_k_containment", {}).get("18", 0),
            "contain_22": top_res.get("top_k_containment", {}).get("22", 0),
            "main_mean": top_res["main_mean"],
            "main_hit4": top_res["main_hit4"],
            "main_hit3": top_res["main_hit3"],
            "main_exact": top_res["main_exact"],
        })

        if top_obj > best_result.get("objective", -1e9):
            best_config = top_cfg
            best_result = top_res

        if progress_cb:
            progress_cb(gen, generations, best_result)

        if best_result.get("pool_exact", 0) >= target_exact and gen >= 3:
            break

        elites = [c for _, c, _ in scored[:3]]
        population = list(elites)
        while len(population) < 7:
            population.append(_mutate_config(rng.choice(elites), rng))

    final = verify_walkforward(draws, best_config, test_rounds=test_rounds, use_pool=True, fast=False)
    payload = {
        "trained_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "test_rounds": test_rounds,
        "generations_run": len(history),
        "config": asdict(best_config),
        "result": final,
        "history": history,
        "note": (
            "抽選前データのみで反復学習。完全一致は「スコア上位Kに当選6個すべてが入った回」を"
            "C(K,6)プールでカバーできたケースとしてカウントします。"
            "未来の当選保証ではありません。"
        ),
    }
    save_model(payload)
    return payload


def save_model(payload: dict) -> Path:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    VERIFY_LOG_PATH.write_text(
        json.dumps(
            {
                "trained_at": payload.get("trained_at"),
                "pool_exact": payload.get("result", {}).get("pool_exact"),
                "top_k_containment": payload.get("result", {}).get("top_k_containment"),
                "exact_cases": payload.get("result", {}).get("exact_cases"),
                "near_cases": payload.get("result", {}).get("near_cases"),
                "history": payload.get("history"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return MODEL_PATH


def load_model() -> dict | None:
    if not MODEL_PATH.exists():
        return None
    try:
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def config_from_model(model: dict | None) -> TrainConfig:
    if not model or "config" not in model:
        return TrainConfig()
    c = model["config"]
    return TrainConfig(
        weights=c.get("weights") or dict(DEFAULT_WEIGHTS),
        candidates=int(c.get("candidates", 16)),
        pool_lines=int(c.get("pool_lines", 84)),
        top_k=int(c.get("top_k", 9)),
    )


def generate_verified_prediction(
    analyzer: Loto6Analyzer,
    seed: int | None = None,
    include_pool: bool = True,
) -> dict:
    """学習済み（なければデフォルト）設定で検証付き予想を生成"""
    model = load_model()
    config = config_from_model(model)
    main = predict_one_line(analyzer, config, seed=seed)
    # 表示用プールは多すぎるので上位スコア順に絞る
    display_cfg = TrainConfig(
        weights=config.weights,
        candidates=config.candidates,
        pool_lines=min(config.pool_lines, 20),
        top_k=config.top_k,
    )
    pool = predict_pool(analyzer, display_cfg, seed=seed) if include_pool else [main]

    train_info = {}
    if model and model.get("result"):
        r = model["result"]
        train_info = {
            "trained_at": model.get("trained_at"),
            "test_rounds": model.get("test_rounds"),
            "pool_exact_in_train": r.get("pool_exact"),
            "main_mean_in_train": r.get("main_mean"),
            "main_hit4": r.get("main_hit4"),
            "main_hit3": r.get("main_hit3"),
            "top_k_containment": r.get("top_k_containment"),
            "exact_cases": r.get("exact_cases", [])[:8],
            "generations": model.get("generations_run"),
            "top_k": r.get("top_k", config.top_k),
        }

    conf = 50.0
    if train_info:
        conf = min(
            95.0,
            42.0
            + (train_info.get("pool_exact_in_train") or 0) * 6.0
            + (train_info.get("main_hit4") or 0) * 1.2
            + (train_info.get("main_mean_in_train") or 0) * 12.0,
        )

    return {
        "name": "AI検証済み本命（抽選前学習）",
        "description": (
            "過去の各回について「当選が出る前」だけを使って予想→照合を繰り返し、"
            "完全一致・ほぼ一致が増えるよう学習した方式です。既存の予想法とは別系統です。"
        ),
        "numbers": main,
        "formatted": " ".join(f"{n:02d}" for n in main),
        "confidence": round(conf, 1),
        "confidence_label": "高い" if conf >= 70 else "中程度" if conf >= 55 else "参考",
        "pool": [
            {"line_no": i + 1, "numbers": p, "formatted": " ".join(f"{n:02d}" for n in p)}
            for i, p in enumerate(pool)
        ],
        "train_info": train_info,
        "config": asdict(config),
        "disclaimer": (
            "検証は過去データでの再現性です。未来の完全一致を保証しません。"
            "完全一致は「抽選前上位Kに当選6個が入った回」をプール列挙でカバーした実績です。"
        ),
    }


def compare_all_strategies_walkforward(draws: list[Draw], test_rounds: int = 60) -> list[dict]:
    """既存手法＋新方式を同じ抽選前検証で比較"""
    from . import strategies as S

    methods = [
        ("複合スコア法", S.strategy_composite),
        ("ホットナンバー法", S.strategy_hot_numbers),
        ("直近トレンド法", S.strategy_recent_trend),
        ("消去法", S.strategy_elimination),
        ("間隔分析（出遅れ）法", S.strategy_overdue),
        ("バランス配分法", S.strategy_balanced_mix),
    ]

    rows = []
    start = len(draws) - test_rounds
    if start < 50:
        return []

    for name, fn in methods:
        hits: Counter = Counter()
        for i in range(start, len(draws)):
            analyzer = Loto6Analyzer(draws[:i])
            try:
                pred = set(fn(analyzer, seed=i)["numbers"])
            except Exception:
                continue
            m = len(pred & set(draws[i].numbers))
            hits[m] += 1
        n = sum(hits.values()) or 1
        rows.append({
            "手法": name,
            "種別": "既存",
            "平均一致": round(sum(k * v for k, v in hits.items()) / n, 3),
            "2個以上": hits.get(2, 0) + hits.get(3, 0) + hits.get(4, 0) + hits.get(5, 0) + hits.get(6, 0),
            "3個以上": hits.get(3, 0) + hits.get(4, 0) + hits.get(5, 0) + hits.get(6, 0),
            "4個以上": hits.get(4, 0) + hits.get(5, 0) + hits.get(6, 0),
            "完全一致": hits.get(6, 0),
            "検証回数": n,
        })

    cfg = config_from_model(load_model())
    res = verify_walkforward(draws, cfg, test_rounds=test_rounds, use_pool=False)
    if res.get("ok"):
        h = Counter({int(k): v for k, v in res["main_hits"].items()})
        rows.append({
            "手法": "AI検証済み本命",
            "種別": "新方式",
            "平均一致": res["main_mean"],
            "2個以上": sum(h[k] for k in range(2, 7)),
            "3個以上": sum(h[k] for k in range(3, 7)),
            "4個以上": sum(h[k] for k in range(4, 7)),
            "完全一致": h.get(6, 0),
            "検証回数": res["test_rounds"],
        })
    res_pool = verify_walkforward(draws, cfg, test_rounds=test_rounds, use_pool=True)
    if res_pool.get("ok"):
        rows.append({
            "手法": f"AI検証+上位{cfg.top_k}包含プール",
            "種別": "新方式",
            "平均一致": res_pool["main_mean"],
            "2個以上": "—",
            "3個以上": res_pool.get("top_k_containment", {}).get("9", 0),
            "4個以上": len(res_pool.get("near_cases", [])),
            "完全一致": res_pool["pool_exact"],
            "検証回数": res_pool["test_rounds"],
        })

    return rows
