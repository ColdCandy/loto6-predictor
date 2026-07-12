"""予想番号生成ストラテジー"""

from __future__ import annotations

import random
from datetime import datetime
from itertools import combinations

from .analyzer import Loto6Analyzer
from .loto7_data import load_draws as load_loto7_draws
from .monthly_patterns import (
    anchor_correlation_scores,
    get_current_month_anchor,
    loto6_loto7_overlap_scores,
    monthly_analysis_summary,
    monthly_unlikely_numbers,
)


def _format_numbers(nums: list[int]) -> str:
    return " ".join(f"{n:02d}" for n in sorted(nums))


def _is_balanced(nums: list[int]) -> bool:
    """よく出るパターンに近いか簡易チェック"""
    odd = sum(1 for n in nums if n % 2 == 1)
    if odd in (0, 6):
        return False
    total = sum(nums)
    if total < 80 or total > 220:
        return False
    low = sum(1 for n in nums if n <= 22)
    if low in (0, 6):
        return False
    sorted_nums = sorted(nums)
    consecutive = sum(
        1 for i in range(len(sorted_nums) - 1) if sorted_nums[i + 1] - sorted_nums[i] == 1
    )
    return consecutive <= 3


def _pick_from_scores(analyzer: Loto6Analyzer, scores: dict[int, float], seed: int | None = None) -> list[int]:
    rng = random.Random(seed)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    pool = [n for n, _ in ranked[:18]]
    weights = [scores[n] for n in pool]

    for _ in range(500):
        chosen = rng.choices(pool, weights=weights, k=12)
        unique = list(dict.fromkeys(chosen))
        if len(unique) >= 6:
            candidate = rng.sample(unique[:10], 6)
            if _is_balanced(candidate):
                return candidate

    return [n for n, _ in ranked[:6]]


def strategy_hot_numbers(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """出現回数が多い数字（ホットナンバー）"""
    top = analyzer.top_numbers(15)
    scores = {n: c for n, c in top}
    for n in range(1, 44):
        scores.setdefault(n, 0)
    nums = _pick_from_scores(analyzer, scores, seed)
    return {
        "name": "ホットナンバー法",
        "description": "過去全体で出現回数が多い数字を中心に選びます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
    }


def strategy_recent_trend(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """直近50回の出現傾向"""
    top = analyzer.top_numbers(15, last_n=50)
    scores = {n: c * 2 for n, c in top}
    for n in range(1, 44):
        scores.setdefault(n, 0)
    nums = _pick_from_scores(analyzer, scores, seed)
    return {
        "name": "直近トレンド法",
        "description": "直近50回でよく出ている数字を重視します",
        "numbers": nums,
        "formatted": _format_numbers(nums),
    }


def strategy_overdue(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """間隔が空いている数字（オーバーデュー）"""
    overdue = analyzer.overdue_numbers(15)
    scores = {n: gap for n, gap in overdue}
    for n in range(1, 44):
        scores.setdefault(n, 0)
    nums = _pick_from_scores(analyzer, scores, seed)
    return {
        "name": "間隔分析（出遅れ）法",
        "description": "長期間出ていない数字が出るという考え方に基づきます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
    }


def strategy_pair_compatibility(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """相性の良い数字ペアを組み合わせ"""
    rng = random.Random(seed)
    pairs = analyzer.pair_frequency()
    top_pairs = pairs.most_common(30)
    nums: set[int] = set()
    shuffled = list(top_pairs)
    rng.shuffle(shuffled)
    for pair, _count in shuffled:
        a, b = pair
        nums.add(a)
        nums.add(b)
        if len(nums) >= 6:
            break
    if len(nums) < 6:
        for n, _ in analyzer.top_numbers(6):
            nums.add(n)
    result = sorted(list(nums)[:6])
    return {
        "name": "相性ペア法",
        "description": "過去に一緒に出やすい数字のペアを組み合わせます",
        "numbers": result,
        "formatted": _format_numbers(result),
    }


def strategy_elimination(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """消去法（簡易版）: 出にくい数字を除外"""
    freq = analyzer.frequency()
    recent = analyzer.recent_frequency(100)
    eliminated = set()
    for n in range(1, 44):
        if freq[n] <= sorted(freq.values())[10] and recent[n] <= 2:
            eliminated.add(n)
    candidates = [n for n in range(1, 44) if n not in eliminated]
    scores = analyzer.number_scores()
    filtered_scores = {n: scores[n] for n in candidates}
    nums = _pick_from_scores(analyzer, filtered_scores, seed)
    return {
        "name": "消去法",
        "description": "出にくい数字を除外し、残りから選びます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
        "eliminated": sorted(eliminated),
    }


def strategy_composite(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """複合スコア（頻度+直近+間隔）"""
    scores = analyzer.number_scores(last_n=100)
    nums = _pick_from_scores(analyzer, scores, seed)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "name": "複合スコア法（おすすめ）",
        "description": "出現頻度・直近傾向・出遅れを総合的に評価します",
        "numbers": nums,
        "formatted": _format_numbers(nums),
        "top_scores": [(n, round(s, 3)) for n, s in ranked[:10]],
    }


def strategy_balanced_mix(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """奇偶・大小のバランスを考慮"""
    rng = random.Random(seed)
    scores = analyzer.number_scores()
    ranked = [n for n, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

    for _ in range(1000):
        odds = [n for n in ranked if n % 2 == 1][:12]
        evens = [n for n in ranked if n % 2 == 0][:12]

        pick = set()
        pick.update(rng.sample(odds, min(3, len(odds))))
        pick.update(rng.sample(evens, min(3, len(evens))))
        while len(pick) < 6:
            pick.add(rng.choice(ranked[:20]))
        nums = list(pick)[:6]
        if _is_balanced(nums):
            return {
                "name": "バランス配分法",
                "description": "奇数/偶数・小/大のバランスを考慮して選びます",
                "numbers": nums,
                "formatted": _format_numbers(nums),
            }

    nums = ranked[:6]
    return {
        "name": "バランス配分法",
        "description": "奇数/偶数・小/大のバランスを考慮して選びます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
    }


def strategy_monthly_anchor(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """月初回抽選（月・木）起点の月次パターン法"""
    now = datetime.now()
    summary = monthly_analysis_summary(analyzer.draws, now.year, now.month)
    scores = anchor_correlation_scores(analyzer.draws, now.month)

    anchor = summary["anchor"]
    if anchor:
        for n in anchor.numbers:
            scores[n] = scores.get(n, 0) + 0.4

    nums = _pick_from_scores(analyzer, scores, seed)
    anchor_str = " ".join(f"{n:02d}" for n in summary["anchor_numbers"]) if summary["anchor_numbers"] else "なし"

    return {
        "name": "月次起点法",
        "description": (
            f"{summary['month_label']}の最初の月・木抽選（第{summary['anchor_round']}回 {summary['anchor_date']}）"
            f"を起点に、過去{summary['years_analyzed']}年分の同月データから出やすい番号を選びます"
        ),
        "numbers": nums,
        "formatted": _format_numbers(nums),
        "anchor_numbers": summary["anchor_numbers"],
        "anchor_info": f"起点: {anchor_str}",
        "month_top": summary["top_scored"][:6],
    }


def strategy_monthly_inverse(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """今月出にくい数字を逆に組み込む法"""
    now = datetime.now()
    unlikely = monthly_unlikely_numbers(analyzer.draws, now.month, now.year, count=15)
    unlikely_nums = [n for n, _count, _r in unlikely[:10]]

    monthly_scores = anchor_correlation_scores(analyzer.draws, now.month)
    rng = random.Random(seed)

    combined_scores: dict[int, float] = {}
    for n in range(1, 44):
        combined_scores[n] = monthly_scores.get(n, 0) * 0.4
    for n in unlikely_nums[:8]:
        combined_scores[n] = combined_scores.get(n, 0) + 0.6

    for _ in range(500):
        inverse_pick = set(rng.sample(unlikely_nums[:8], min(3, len(unlikely_nums[:8]))))
        hot_pick = sorted(monthly_scores.items(), key=lambda x: x[1], reverse=True)[:12]
        hot_nums = [n for n, _ in hot_pick if n not in inverse_pick]
        pick = set(inverse_pick)
        pick.update(rng.sample(hot_nums, min(3, len(hot_nums))))
        while len(pick) < 6:
            n = rng.choice(unlikely_nums + hot_nums)
            pick.add(n)
        nums = list(pick)[:6]
        if _is_balanced(nums):
            return {
                "name": "月次逆張り法",
                "description": (
                    f"{now.month}月に統計的に出にくい数字を逆に予想に組み込み、"
                    f"同月の出やすい数字とブレンドします"
                ),
                "numbers": nums,
                "formatted": _format_numbers(nums),
                "unlikely_numbers": unlikely_nums[:10],
                "unlikely_detail": [(n, c, r) for n, c, r in unlikely[:8]],
            }

    nums = _pick_from_scores(analyzer, combined_scores, seed)
    return {
        "name": "月次逆張り法",
        "description": f"{now.month}月に出にくい数字を逆に予想番号へ組み込みます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
        "unlikely_numbers": unlikely_nums[:10],
        "unlikely_detail": [(n, c, r) for n, c, r in unlikely[:8]],
    }


def strategy_loto67_overlap(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """ロト6・ロト7の重複数字から予想"""
    loto7_draws = load_loto7_draws()
    if not loto7_draws:
        scores = analyzer.number_scores()
        nums = _pick_from_scores(analyzer, scores, seed)
        return {
            "name": "ロト6・7重複法",
            "description": "ロト7データ未取得のためロト6スコアで代替",
            "numbers": nums,
            "formatted": _format_numbers(nums),
        }

    scores = loto6_loto7_overlap_scores(analyzer.draws, loto7_draws)
    for n in range(38, 44):
        scores[n] = scores.get(n, 0) * 0.3

    nums = _pick_from_scores(analyzer, scores, seed)

    latest_l6 = set(analyzer.draws[-1].numbers) if analyzer.draws else set()
    latest_l7 = set(loto7_draws[-1].numbers)
    overlap_latest = sorted(latest_l6 & latest_l7)
    top_overlap = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "name": "ロト6・7重複法",
        "description": (
            f"ロト6(1-43)とロト7(1-37)の共通数字の出現傾向から選びます。"
            f" 最新ロト7第{loto7_draws[-1].round_num}回との重複: "
            + (" ".join(f"{n:02d}" for n in overlap_latest) if overlap_latest else "なし")
        ),
        "numbers": nums,
        "formatted": _format_numbers(nums),
        "overlap_latest": overlap_latest,
        "top_overlap": top_overlap[:8],
        "loto7_latest": list(loto7_draws[-1].numbers),
        "loto7_round": loto7_draws[-1].round_num,
    }


def strategy_quick_pick(analyzer: Loto6Analyzer, seed: int | None = None) -> dict:
    """完全ランダム（バランス考慮）"""
    rng = random.Random(seed)
    for _ in range(1000):
        nums = sorted(rng.sample(range(1, 44), 6))
        if _is_balanced(nums):
            return {
                "name": "クイックピック",
                "description": "ランダムに選び、よく出るパターンに整えます",
                "numbers": nums,
                "formatted": _format_numbers(nums),
            }
    nums = sorted(rng.sample(range(1, 44), 6))
    return {
        "name": "クイックピック",
        "description": "ランダムに選び、よく出るパターンに整えます",
        "numbers": nums,
        "formatted": _format_numbers(nums),
    }


def generate_multiple_lines(
    analyzer: Loto6Analyzer,
    strategy_fn: callable,
    count: int = 5,
    seed: int | None = None,
) -> list[dict]:
    """同一手法で複数パターンを生成"""
    base = seed if seed is not None else random.randint(0, 999999)
    lines = []
    seen: set[tuple[int, ...]] = set()
    for i in range(count * 3):
        pred = strategy_fn(analyzer, seed=base + i)
        key = tuple(sorted(pred["numbers"]))
        if key in seen:
            continue
        seen.add(key)
        pred = {**pred, "line_no": len(lines) + 1}
        lines.append(pred)
        if len(lines) >= count:
            break
    return lines


STRATEGY_FUNCTIONS = [
    strategy_composite,
    strategy_monthly_anchor,
    strategy_monthly_inverse,
    strategy_loto67_overlap,
    strategy_hot_numbers,
    strategy_recent_trend,
    strategy_overdue,
    strategy_pair_compatibility,
    strategy_elimination,
    strategy_balanced_mix,
]

STRATEGY_BY_NAME: dict[str, callable] = {
    "複合スコア法（おすすめ）": strategy_composite,
    "月次起点法": strategy_monthly_anchor,
    "月次逆張り法": strategy_monthly_inverse,
    "ロト6・7重複法": strategy_loto67_overlap,
    "ホットナンバー法": strategy_hot_numbers,
    "直近トレンド法": strategy_recent_trend,
    "間隔分析（出遅れ）法": strategy_overdue,
    "相性ペア法": strategy_pair_compatibility,
    "消去法": strategy_elimination,
    "バランス配分法": strategy_balanced_mix,
    "クイックピック": strategy_quick_pick,
}


def generate_all_predictions(analyzer: Loto6Analyzer, seed: int | None = None) -> list[dict]:
    return [fn(analyzer, seed=seed) for fn in STRATEGY_FUNCTIONS]


def backtest_strategy(analyzer: Loto6Analyzer, test_rounds: int = 100) -> list[dict]:
    """過去データで各手法の「3個以上一致」率を簡易検証"""
    if len(analyzer.draws) <= test_rounds + 50:
        return []

    results = []
    strategy_fns = [
        ("複合スコア", strategy_composite),
        ("ホット", strategy_hot_numbers),
        ("直近トレンド", strategy_recent_trend),
        ("消去法", strategy_elimination),
    ]

    for name, fn in strategy_fns:
        hit3 = hit2 = hit4 = 0
        for i in range(len(analyzer.draws) - test_rounds, len(analyzer.draws)):
            train = Loto6Analyzer(analyzer.draws[:i])
            pred = fn(train, seed=i)["numbers"]
            actual = set(analyzer.draws[i].numbers)
            matches = len(set(pred) & actual)
            if matches >= 2:
                hit2 += 1
            if matches >= 3:
                hit3 += 1
            if matches >= 4:
                hit4 += 1
        results.append({
            "strategy": name,
            "test_rounds": test_rounds,
            "hit2_or_more": hit2,
            "hit3_or_more": hit3,
            "hit4_or_more": hit4,
            "rate3": round(hit3 / test_rounds * 100, 1),
        })
    return results
