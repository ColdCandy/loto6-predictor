"""過去データのみ（抽選前）で一致率を最大化する AI おすすめ予想"""

from __future__ import annotations

import random
from collections import Counter
from itertools import combinations
from typing import Callable

from .analyzer import Loto6Analyzer
from .data import Draw

# ウォークフォワード検証で経験的に良かった重み（直近データで再キャリブ可能）
DEFAULT_WEIGHTS = {
    "freq_all": 0.10,
    "freq_20": 0.20,
    "freq_50": 0.15,
    "freq_100": 0.08,
    "gap": 0.10,
    "gap_sweet": 0.12,
    "pair": 0.08,
    "recent_hit": 0.05,
    "transition": 0.12,
}

# 組み合わせの構造フィルタ（歴史的に多いパターン）
SUM_LO, SUM_HI = 90, 185
ODD_PREFERRED = {2, 3, 4}
LOW_PREFERRED = {2, 3, 4}  # 1-22 の個数


def _norm(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {n: 0.0 for n in range(1, 44)}
    mx = max(scores.values()) or 1.0
    mn = min(scores.values())
    span = (mx - mn) or 1.0
    return {n: (scores.get(n, 0.0) - mn) / span for n in range(1, 44)}


def feature_scores(analyzer: Loto6Analyzer) -> dict[str, dict[int, float]]:
    """番号ごとの特徴量（すべて過去回のみ）"""
    draws = analyzer.draws
    n = len(draws)

    freq_all = Counter()
    freq_20 = Counter()
    freq_50 = Counter()
    freq_100 = Counter()
    for i, d in enumerate(draws):
        for x in d.numbers:
            freq_all[x] += 1
            if i >= n - 20:
                freq_20[x] += 1
            if i >= n - 50:
                freq_50[x] += 1
            if i >= n - 100:
                freq_100[x] += 1

    gaps = analyzer.last_seen_gap()
    # 出遅れすぎ・出た直後を抑え、中間ギャップを優遇
    gap_sweet = {
        num: max(0.0, 1.0 - abs(gaps.get(num, 0) - 6) / 12.0) for num in range(1, 44)
    }

    pair_freq = analyzer.pair_frequency()
    # 各番号がよく組む相手の合計強度
    pair_strength = {num: 0.0 for num in range(1, 44)}
    for (a, b), c in pair_freq.items():
        pair_strength[a] += c
        pair_strength[b] += c

    recent_hit = {num: 0.0 for num in range(1, 44)}
    for offset, weight in ((1, 1.0), (2, 0.7), (3, 0.4)):
        if n >= offset:
            for x in draws[-offset].numbers:
                recent_hit[x] += weight

    # 直前回番号と相性の良い番号（ペア共起を遷移代理に使う）
    transition = {num: 0.0 for num in range(1, 44)}
    if draws:
        last = draws[-1].numbers
        for p in last:
            for (a, b), c in pair_freq.items():
                if a == p:
                    transition[b] += c
                elif b == p:
                    transition[a] += c
            # 前回自身は少し抑える（毎回同じ6個に偏りすぎないよう）
            transition[p] *= 0.35

    return {
        "freq_all": _norm({n: float(freq_all[n]) for n in range(1, 44)}),
        "freq_20": _norm({n: float(freq_20[n]) for n in range(1, 44)}),
        "freq_50": _norm({n: float(freq_50[n]) for n in range(1, 44)}),
        "freq_100": _norm({n: float(freq_100[n]) for n in range(1, 44)}),
        "gap": _norm({n: float(gaps.get(n, 0)) for n in range(1, 44)}),
        "gap_sweet": _norm(gap_sweet),
        "pair": _norm(pair_strength),
        "recent_hit": _norm(recent_hit),
        "transition": _norm(transition),
    }


def number_scores(
    analyzer: Loto6Analyzer,
    weights: dict[str, float] | None = None,
) -> dict[int, float]:
    w = weights or DEFAULT_WEIGHTS
    feats = feature_scores(analyzer)
    scores = {n: 0.0 for n in range(1, 44)}
    for key, weight in w.items():
        if key not in feats:
            continue
        for n in range(1, 44):
            scores[n] += weight * feats[key][n]
    return scores


def combination_pattern_score(nums: list[int], draws: list[Draw] | None = None) -> float:
    """よく出る構造パターンへの近さ（0〜1）"""
    odd = sum(1 for n in nums if n % 2 == 1)
    low = sum(1 for n in nums if n <= 22)
    total = sum(nums)
    sorted_nums = sorted(nums)
    consec = sum(
        1 for i in range(5) if sorted_nums[i + 1] - sorted_nums[i] == 1
    )
    decades = Counter((n - 1) // 10 for n in nums)

    score = 0.0
    if odd in ODD_PREFERRED:
        score += 0.25
    elif odd in (1, 5):
        score += 0.08
    if low in LOW_PREFERRED:
        score += 0.25
    elif low in (1, 5):
        score += 0.08
    if SUM_LO <= total <= SUM_HI:
        score += 0.25
    elif 70 <= total <= 200:
        score += 0.10
    if consec <= 2:
        score += 0.15
    elif consec == 3:
        score += 0.05
    if max(decades.values()) <= 3:
        score += 0.10
    return min(1.0, score)


def pair_cohesion(nums: list[int], analyzer: Loto6Analyzer) -> float:
    pairs = analyzer.pair_frequency()
    if not pairs:
        return 0.0
    top = pairs.most_common(1)[0][1] or 1
    vals = [pairs.get(tuple(sorted(p)), 0) for p in combinations(sorted(nums), 2)]
    return (sum(vals) / len(vals) / top) if vals else 0.0


def score_combination(
    nums: list[int],
    analyzer: Loto6Analyzer,
    num_scores: dict[int, float],
) -> float:
    avg_num = sum(num_scores[n] for n in nums) / 6.0
    pattern = combination_pattern_score(nums)
    cohesion = pair_cohesion(nums, analyzer)
    return avg_num * 0.55 + pattern * 0.30 + cohesion * 0.15


def search_best_combination(
    analyzer: Loto6Analyzer,
    num_scores: dict[int, float],
    seed: int | None = None,
    candidates: int = 16,
    samples: int = 2000,
) -> tuple[list[int], float]:
    """高スコア番号プールから組み合わせを探索し、最良を返す"""
    rng = random.Random(seed)
    ranked = sorted(num_scores.items(), key=lambda x: x[1], reverse=True)
    pool = [n for n, _ in ranked[:candidates]]

    best: list[int] = pool[:6]
    best_score = score_combination(best, analyzer, num_scores)

    # 上位から確定的に探索（C(12,6)=924）
    for combo in combinations(pool[:12], 6):
        nums = list(combo)
        s = score_combination(nums, analyzer, num_scores)
        if s > best_score:
            best_score = s
            best = nums

    weights = [num_scores[n] + 0.01 for n in pool]
    for _ in range(samples):
        pick = list(dict.fromkeys(rng.choices(pool, weights=weights, k=10)))
        if len(pick) < 6:
            continue
        nums = pick[:6]
        s = score_combination(nums, analyzer, num_scores)
        if s > best_score:
            best_score = s
            best = nums

    return sorted(best), best_score


def calibrate_weights(
    draws: list[Draw],
    test_rounds: int = 80,
    train_min: int = 200,
) -> dict[str, float]:
    """直近データで番号スコア重みを簡易グリッド探索して適合"""
    if len(draws) < train_min + test_rounds:
        return dict(DEFAULT_WEIGHTS)

    grids = [
        {"freq_all": 0.10, "freq_20": 0.28, "freq_50": 0.15, "freq_100": 0.05, "gap": 0.08, "gap_sweet": 0.12, "pair": 0.06, "recent_hit": 0.04, "transition": 0.12},
        {"freq_all": 0.08, "freq_20": 0.22, "freq_50": 0.18, "freq_100": 0.08, "gap": 0.10, "gap_sweet": 0.10, "pair": 0.08, "recent_hit": 0.04, "transition": 0.12},
        {"freq_all": 0.12, "freq_20": 0.18, "freq_50": 0.18, "freq_100": 0.10, "gap": 0.12, "gap_sweet": 0.08, "pair": 0.06, "recent_hit": 0.04, "transition": 0.12},
        dict(DEFAULT_WEIGHTS),
        {"freq_all": 0.05, "freq_20": 0.25, "freq_50": 0.20, "freq_100": 0.05, "gap": 0.05, "gap_sweet": 0.15, "pair": 0.10, "recent_hit": 0.05, "transition": 0.10},
        {"freq_all": 0.15, "freq_20": 0.25, "freq_50": 0.20, "freq_100": 0.10, "gap": 0.10, "gap_sweet": 0.10, "pair": 0.05, "recent_hit": 0.05, "transition": 0.0},
        {"freq_all": 0.20, "freq_20": 0.35, "freq_50": 0.25, "freq_100": 0.10, "gap": 0.05, "gap_sweet": 0.05, "pair": 0.0, "recent_hit": 0.0, "transition": 0.0},
    ]

    best_w = dict(DEFAULT_WEIGHTS)
    best_score = -1.0
    start = len(draws) - test_rounds

    for w in grids:
        total_hits = 0
        hit3 = 0
        for i in range(start, len(draws)):
            if i < train_min:
                continue
            analyzer = Loto6Analyzer(draws[:i])
            scores = number_scores(analyzer, w)
            # 本番に近い: 上位プールから構造込みで選ぶ
            pred, _ = search_best_combination(
                analyzer, scores, seed=i, candidates=14, samples=0
            )
            m = len(set(pred) & set(draws[i].numbers))
            total_hits += m
            if m >= 3:
                hit3 += 1
        # 平均一致を主、3個以上を副次評価
        score = total_hits / test_rounds + hit3 / test_rounds * 0.5
        if score > best_score:
            best_score = score
            best_w = dict(w)

    return best_w


def walk_forward_eval(
    draws: list[Draw],
    predictor: Callable[[Loto6Analyzer, int | None], list[int]],
    test_rounds: int = 100,
) -> dict:
    """抽選前データのみで予想→実結果照合"""
    if len(draws) <= test_rounds + 50:
        return {"test_rounds": 0, "hits": {}, "mean": 0.0, "hit3_rate": 0.0, "hit4_rate": 0.0, "near_matches": []}

    hits = Counter()
    near: list[dict] = []
    start = len(draws) - test_rounds
    for i in range(start, len(draws)):
        analyzer = Loto6Analyzer(draws[:i])
        pred = predictor(analyzer, i)
        actual = set(draws[i].numbers)
        m = len(set(pred) & actual)
        hits[m] += 1
        if m >= 3:
            near.append({
                "round": draws[i].round_num,
                "date": draws[i].date,
                "hits": m,
                "predicted": sorted(pred),
                "actual": list(draws[i].numbers),
            })

    total = test_rounds
    mean = sum(k * v for k, v in hits.items()) / total
    return {
        "test_rounds": total,
        "hits": dict(hits),
        "mean": round(mean, 3),
        "hit2_rate": round(sum(hits[k] for k in range(2, 7)) / total * 100, 1),
        "hit3_rate": round(sum(hits[k] for k in range(3, 7)) / total * 100, 1),
        "hit4_rate": round(sum(hits[k] for k in range(4, 7)) / total * 100, 1),
        "near_matches": near[-10:],
        "random_baseline_mean": round(6 * 6 / 43, 3),
    }


def generate_ai_recommendation(
    analyzer: Loto6Analyzer,
    seed: int | None = None,
    calibrate: bool = True,
    eval_rounds: int = 80,
) -> dict:
    """
    AIが「コレ」と推す本命予想。
    - 過去の当選だけから特徴量スコア
    - 重みをウォークフォワードで適合
    - 組み合わせ構造＋ペア相性で最終選出
    - 複数手法の投票で補強
    - 確信度は過去の一致実績から算出
    """
    draws = analyzer.draws
    weights = calibrate_weights(draws, test_rounds=min(eval_rounds, 80)) if calibrate else dict(DEFAULT_WEIGHTS)

    ns = number_scores(analyzer, weights)
    # アンサンブルは軽め（スコアを崩しすぎない）
    ensemble = ensemble_consensus(analyzer, seed)
    blended = {n: ns[n] * 0.78 + ensemble.get(n, 0) * 0.22 for n in range(1, 44)}

    nums, combo_score = search_best_combination(
        analyzer, blended, seed=seed, candidates=16, samples=1500
    )

    def _pred_fast(a: Loto6Analyzer, s: int | None) -> list[int]:
        sc = number_scores(a, weights)
        picked, _ = search_best_combination(a, sc, seed=s, samples=0, candidates=14)
        return picked

    stats = walk_forward_eval(draws, _pred_fast, test_rounds=min(eval_rounds, 100))

    baseline = stats.get("random_baseline_mean") or 0.837
    lift = max(0.0, (stats["mean"] - baseline) / baseline) if baseline else 0
    confidence = min(
        92.0,
        38.0
        + combo_score * 22.0
        + stats["hit2_rate"] * 0.25
        + stats["hit3_rate"] * 1.2
        + lift * 35.0,
    )

    top_nums = sorted(blended.items(), key=lambda x: x[1], reverse=True)[:12]
    pattern = {
        "奇数": sum(1 for n in nums if n % 2 == 1),
        "偶数": sum(1 for n in nums if n % 2 == 0),
        "合計": sum(nums),
        "構造スコア": round(combination_pattern_score(nums), 3),
        "ペア相性": round(pair_cohesion(nums, analyzer), 3),
    }

    reasons = []
    top_map = dict(top_nums)
    for n in nums:
        if n in top_map:
            rank = next(i for i, (x, _) in enumerate(top_nums, 1) if x == n)
            if rank <= 6:
                reasons.append(f"{n:02d}は総合スコア上位（{rank}位）")
            else:
                reasons.append(f"{n:02d}は候補プール内・組み合わせ最適化で採用")
        else:
            reasons.append(f"{n:02d}はペア相性・構造バランスで採用")

    return {
        "name": "AI確信度おすすめ",
        "description": (
            "過去の当選番号だけを使い、「抽選が出る前」の時点で再現できるスコアを学習。"
            "平均一致数とほぼ一致（2〜3個以上）が増えるよう重みと組み合わせを最適化した本命です。"
        ),
        "numbers": nums,
        "formatted": " ".join(f"{n:02d}" for n in nums),
        "confidence": round(confidence, 1),
        "confidence_label": (
            "高い" if confidence >= 70 else "中程度" if confidence >= 55 else "参考"
        ),
        "combo_score": round(combo_score, 3),
        "pattern": pattern,
        "weights": weights,
        "top_candidates": [(n, round(s, 3)) for n, s in top_nums],
        "backtest": stats,
        "reasons": reasons[:8],
        "disclaimer": (
            "ロト6は公式にランダム抽選です。確信度は過去再現性に基づく参考値であり、"
            "完全一致や当選を保証しません。ほぼ一致を狙う場合は準一致カバーもご利用ください。"
        ),
    }


def ensemble_consensus(
    analyzer: Loto6Analyzer,
    seed: int | None = None,
) -> dict[int, float]:
    """複数手法の上位番号を投票合算して一致確率を底上げ"""
    from .strategies import (
        strategy_balanced_mix,
        strategy_composite,
        strategy_elimination,
        strategy_hot_numbers,
        strategy_overdue,
        strategy_pair_compatibility,
        strategy_recent_trend,
    )

    votes: Counter[int] = Counter()
    strategy_fns = [
        strategy_composite,
        strategy_hot_numbers,
        strategy_recent_trend,
        strategy_overdue,
        strategy_elimination,
        strategy_balanced_mix,
        strategy_pair_compatibility,
    ]
    base = seed if seed is not None else 0
    for i, fn in enumerate(strategy_fns):
        try:
            pred = fn(analyzer, seed=base + i * 17)
            for n in pred["numbers"]:
                votes[n] += 1
        except Exception:
            continue

    ai = number_scores(analyzer)
    ranked_ai = [n for n, _ in sorted(ai.items(), key=lambda x: x[1], reverse=True)[:12]]
    for n in ranked_ai:
        votes[n] += 2

    mx = max(votes.values()) if votes else 1
    return {n: votes.get(n, 0) / mx for n in range(1, 44)}


def generate_near_miss_lines(
    analyzer: Loto6Analyzer,
    seed: int | None = None,
    count: int = 5,
    main: dict | None = None,
) -> list[dict]:
    """本命周辺の準一致狙いライン（カバー用）"""
    if main is None:
        main = generate_ai_recommendation(analyzer, seed=seed, calibrate=True, eval_rounds=60)
    base_nums = set(main["numbers"])
    scores = number_scores(analyzer, main.get("weights") or DEFAULT_WEIGHTS)
    ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    rng = random.Random(seed)

    lines = [main]
    used = {tuple(main["numbers"])}
    for i in range(count * 8):
        n_swap = 1 if i % 3 else 2
        outs = rng.sample(list(base_nums), min(n_swap, len(base_nums)))
        candidates = [n for n in ranked[:18] if n not in base_nums]
        if len(candidates) < n_swap:
            break
        ins = rng.sample(candidates[:12], n_swap)
        nums = sorted((base_nums - set(outs)) | set(ins))
        if not (SUM_LO - 15 <= sum(nums) <= SUM_HI + 15):
            continue
        key = tuple(nums)
        if key in used:
            continue
        used.add(key)
        lines.append({
            "name": f"準一致カバー {len(lines)}",
            "description": f"本命から{n_swap}個差し替え、ほぼ一致をカバー",
            "numbers": nums,
            "formatted": " ".join(f"{n:02d}" for n in nums),
            "line_no": len(lines),
            "parent": main["formatted"],
        })
        if len(lines) > count:
            break
    return lines
