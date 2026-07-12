"""月次パターン分析（月初回抽選起点・12ヶ月周期）"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .data import Draw

LOTTO6_START = datetime(2000, 10, 5)
DRAW_WEEKDAYS = {0, 3}  # 月・木


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y/%m/%d")


def first_draw_of_month(draws: list[Draw], year: int, month: int) -> Draw | None:
    """その月の最初の月曜・木曜抽選"""
    month_draws = [
        d for d in draws
        if (dt := _parse_date(d.date)).year == year
        and dt.month == month
        and dt.weekday() in DRAW_WEEKDAYS
    ]
    if not month_draws:
        return None
    return min(month_draws, key=lambda d: _parse_date(d.date))


def get_current_month_anchor(draws: list[Draw], year: int, month: int) -> Draw | None:
    """今月の起点となる最初の抽選（なければ直近月の起点）"""
    anchor = first_draw_of_month(draws, year, month)
    if anchor:
        return anchor
    for offset in range(1, 13):
        m = month - offset
        y = year
        while m < 1:
            m += 12
            y -= 1
        anchor = first_draw_of_month(draws, y, m)
        if anchor:
            return anchor
    return None


def monthly_frequency(draws: list[Draw], month: int) -> Counter[int]:
    """同じ暦月の全抽選での出現回数"""
    freq: Counter[int] = Counter()
    for d in draws:
        if _parse_date(d.date).month == month:
            freq.update(d.numbers)
    return freq


def anchor_correlation_scores(draws: list[Draw], month: int) -> dict[int, float]:
    """
    各月の最初の抽選番号を起点に、同月内でよく出る数字をスコア化。
    ロト6開始から12ヶ月周期で繰り返し集計。
    """
    scores: Counter[int] = Counter()
    years_seen: set[int] = set()

    for d in draws:
        dt = _parse_date(d.date)
        if dt.month != month:
            continue
        years_seen.add(dt.year)

    for year in sorted(years_seen):
        anchor = first_draw_of_month(draws, year, month)
        if not anchor:
            continue
        anchor_set = set(anchor.numbers)
        month_draws = [
            x for x in draws
            if (xdt := _parse_date(x.date)).year == year and xdt.month == month
        ]
        for md in month_draws:
            for n in md.numbers:
                weight = 1.5 if n in anchor_set else 1.0
                if n in anchor_set:
                    weight += 0.5
                scores[n] += weight

    if not scores:
        return {n: 0.0 for n in range(1, 44)}

    max_score = max(scores.values()) or 1
    return {n: scores.get(n, 0) / max_score for n in range(1, 44)}


def monthly_unlikely_numbers(
    draws: list[Draw],
    month: int,
    year: int | None = None,
    count: int = 12,
) -> list[tuple[int, int, float]]:
    """
    その月に出にくい数字（出現回数が少ない順）。
    返り値: (番号, 歴史的出現回数, 出にくさスコア)
    """
    freq = monthly_frequency(draws, month)
    month_draws_count = sum(
        1 for d in draws if _parse_date(d.date).month == month
    )
    if month_draws_count == 0:
        return [(n, 0, 1.0) for n in range(1, count + 1)]

    avg = sum(freq.values()) / 43 if freq else 0
    ranked: list[tuple[int, int, float]] = []
    for n in range(1, 44):
        c = freq.get(n, 0)
        rarity = 1.0 - (c / (avg + 1))
        ranked.append((n, c, round(rarity, 3)))

    ranked.sort(key=lambda x: (x[1], -x[0]))
    return ranked[:count]


def monthly_analysis_summary(
    draws: list[Draw],
    year: int | None = None,
    month: int | None = None,
) -> dict:
    """UI表示用の月次分析サマリー"""
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    anchor = get_current_month_anchor(draws, year, month)
    scores = anchor_correlation_scores(draws, month)
    unlikely = monthly_unlikely_numbers(draws, month, year)
    freq = monthly_frequency(draws, month)

    top_monthly = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
    top_scored = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

    years_with_data = sorted({
        _parse_date(d.date).year
        for d in draws
        if _parse_date(d.date).month == month
    })

    return {
        "year": year,
        "month": month,
        "month_label": f"{month}月",
        "anchor": anchor,
        "anchor_numbers": list(anchor.numbers) if anchor else [],
        "anchor_date": anchor.date if anchor else None,
        "anchor_round": anchor.round_num if anchor else None,
        "years_analyzed": len(years_with_data),
        "years_range": f"{years_with_data[0]}〜{years_with_data[-1]}" if years_with_data else "-",
        "top_monthly": top_monthly,
        "top_scored": top_scored,
        "unlikely": unlikely,
        "scores": scores,
    }


def loto6_loto7_overlap_scores(
    loto6_draws: list[Draw],
    loto7_draws: list,
    recent_l6: int = 30,
    recent_l7: int = 30,
) -> dict[int, float]:
    """
    ロト6(1-43)とロト7(1-37)で重なる数字の相関スコア。
    両方の直近抽選・全体頻度から算出。
    """
    from collections import Counter

    l6_all: Counter[int] = Counter()
    l7_all: Counter[int] = Counter()
    l6_recent: Counter[int] = Counter()
    l7_recent: Counter[int] = Counter()

    for d in loto6_draws:
        l6_all.update(d.numbers)
    for d in loto6_draws[-recent_l6:]:
        l6_recent.update(d.numbers)

    for d in loto7_draws:
        l7_all.update(d.numbers)
    for d in loto7_draws[-recent_l7:]:
        l7_recent.update(d.numbers)

    max_l6 = max(l6_all.values()) or 1
    max_l7 = max(l7_all.values()) or 1
    max_l6r = max(l6_recent.values()) or 1
    max_l7r = max(l7_recent.values()) or 1

    scores: dict[int, float] = {}
    for n in range(1, 38):
        if n > 43:
            break
        scores[n] = (
            l6_all[n] / max_l6 * 0.25
            + l7_all[n] / max_l7 * 0.25
            + l6_recent[n] / max_l6r * 0.25
            + l7_recent[n] / max_l7r * 0.25
        )

    latest_l6 = set(loto6_draws[-1].numbers) if loto6_draws else set()
    latest_l7 = set(loto7_draws[-1].numbers) if loto7_draws else set()
    for n in latest_l6 & latest_l7:
        if n in scores:
            scores[n] += 0.3

    return scores
