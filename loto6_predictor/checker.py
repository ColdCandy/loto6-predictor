"""当選チェック・日程・番号分析などの便利機能"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .data import Draw

JST = timezone(timedelta(hours=9))

PRIZE_NAMES = {
    1: "1等（6個一致）",
    2: "2等（5個+ボーナス）",
    3: "3等（5個一致）",
    4: "4等（4個一致）",
    5: "5等（3個一致）",
}


def next_draw_dates(count: int = 4) -> list[date]:
    """次回以降の抽選日（月・木）"""
    today = datetime.now(JST).date()
    found: list[date] = []
    for i in range(21):
        d = today + timedelta(days=i)
        if d.weekday() in (0, 3):
            found.append(d)
        if len(found) >= count:
            break
    return found


def format_draw_date(d: date) -> str:
    weekdays = "月火水木金土日"
    return f"{d.year}/{d.month}/{d.day}（{weekdays[d.weekday()]}）"


def check_winning(picked: list[int], draw: Draw) -> dict:
    """購入番号と当選結果を照合"""
    if len(set(picked)) != 6 or any(n < 1 or n > 43 for n in picked):
        return {"valid": False, "error": "1〜43から重複なし6個を選んでください"}

    picked_set = set(picked)
    main = set(draw.numbers)
    hits = len(picked_set & main)
    bonus_hit = draw.bonus in picked_set

    tier: int | None = None
    if hits == 6:
        tier = 1
    elif hits == 5 and bonus_hit:
        tier = 2
    elif hits == 5:
        tier = 3
    elif hits == 4:
        tier = 4
    elif hits == 3:
        tier = 5

    matched = sorted(picked_set & main)
    return {
        "valid": True,
        "hits": hits,
        "bonus_hit": bonus_hit,
        "tier": tier,
        "prize_name": PRIZE_NAMES.get(tier) if tier else "はずれ",
        "matched_numbers": matched,
        "draw_round": draw.round_num,
        "draw_date": draw.date,
        "draw_numbers": list(draw.numbers),
        "draw_bonus": draw.bonus,
    }


def analyze_numbers(nums: list[int]) -> dict:
    """番号組み合わせの特徴分析"""
    sorted_nums = sorted(nums)
    odd = sum(1 for n in nums if n % 2 == 1)
    low = sum(1 for n in nums if n <= 22)
    total = sum(nums)
    consecutive = sum(
        1 for i in range(len(sorted_nums) - 1) if sorted_nums[i + 1] - sorted_nums[i] == 1
    )
    return {
        "奇数": odd,
        "偶数": 6 - odd,
        "小(1-22)": low,
        "大(23-43)": 6 - low,
        "合計": total,
        "連番ペア": consecutive,
        "最小": sorted_nums[0],
        "最大": sorted_nums[-1],
    }


def backtest_numbers(picked: list[int], draws: list[Draw], last_n: int = 100) -> dict:
    """過去N回に同じ番号で購入していたら的中は？"""
    target = draws[-last_n:] if last_n else draws
    results = {3: 0, 4: 0, 5: 0, "5+b": 0, 6: 0, 0: 0}
    best: dict | None = None

    for d in target:
        r = check_winning(picked, d)
        if not r["valid"]:
            continue
        hits = r["hits"]
        if r["tier"] == 2:
            results["5+b"] += 1
        elif hits == 6:
            results[6] += 1
        elif hits == 5:
            results[5] += 1
        elif hits == 4:
            results[4] += 1
        elif hits == 3:
            results[3] += 1
        else:
            results[0] += 1
        if r["tier"] and (best is None or r["tier"] < best["tier"]):
            best = {"round": d.round_num, "date": d.date, "tier": r["tier"], "hits": hits}

    return {
        "test_rounds": len(target),
        "hit3_or_more": results[3] + results[4] + results[5] + results["5+b"] + results[6],
        "results": results,
        "best": best,
    }
