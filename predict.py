#!/usr/bin/env python3
"""ロト6 予想番号生成ツール"""

from __future__ import annotations

import argparse
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from loto6_predictor.analyzer import Loto6Analyzer
from loto6_predictor.data import DEFAULT_DATA_PATH, auto_update_if_needed, get_data_status, load_draws
from loto6_predictor.strategies import backtest_strategy, generate_all_predictions


def print_header(analyzer: Loto6Analyzer) -> None:
    latest = analyzer.latest
    print("=" * 60)
    print("  ロト6 予想番号生成ツール")
    print("=" * 60)
    print(f"  分析データ: 第1回 〜 第{analyzer.total_rounds}回 ({analyzer.total_rounds}回分)")
    if latest:
        nums = " ".join(f"{n:02d}" for n in latest.numbers)
        print(f"  最新当選: 第{latest.round_num}回 ({latest.date})  {nums} + B{latest.bonus:02d}")
    print("=" * 60)
    print()
    print("【重要】宝くじは完全なランダム抽選です。")
    print("  過去データに基づく分析は参考情報であり、当選を保証するものではありません。")
    print()


def print_statistics(analyzer: Loto6Analyzer) -> None:
    print("--- 統計情報 ---")
    print("\n【出現回数 TOP10】")
    for n, c in analyzer.top_numbers(10):
        print(f"  {n:02d}番: {c}回")

    print("\n【直近50回 TOP10】")
    for n, c in analyzer.top_numbers(10, last_n=50):
        print(f"  {n:02d}番: {c}回")

    print("\n【出遅れ TOP10（経過回数）】")
    for n, gap in analyzer.overdue_numbers(10):
        print(f"  {n:02d}番: {gap}回前が最終出現")

    stats = analyzer.sum_range_stats()
    print(f"\n【本数字合計】平均 {stats['平均']:.1f} / 最小 {stats['最小']:.0f} / 最大 {stats['最大']:.0f}")

    print("\n【奇数個数の分布（%）】")
    for k, v in analyzer.odd_even_distribution().items():
        print(f"  {k}: {v:.1f}%")
    print()


def print_predictions(analyzer: Loto6Analyzer, seed: int | None) -> None:
    predictions = generate_all_predictions(analyzer, seed=seed)
    print("--- 予想番号 ---")
    for i, pred in enumerate(predictions, 1):
        print(f"\n{i}. {pred['name']}")
        print(f"   {pred['description']}")
        print(f"   → 【 {pred['formatted']} 】")
        if "eliminated" in pred:
            elim = " ".join(f"{n:02d}" for n in pred["eliminated"][:10])
            print(f"   （除外候補: {elim} ...）")
    print()


def print_backtest(analyzer: Loto6Analyzer, test_rounds: int) -> None:
    results = backtest_strategy(analyzer, test_rounds)
    if not results:
        print("バックテストに十分なデータがありません。")
        return
    print(f"--- バックテスト（直近{test_rounds}回）---")
    print("各手法で「過去データのみ」を使い、次回を予想した場合の一致率")
    print("（参考値。ランダムでも一定確率で一致します）\n")
    print(f"{'手法':<12} {'2個以上':>8} {'3個以上':>8} {'4個以上':>8} {'3個以上率':>10}")
    print("-" * 50)
    for r in results:
        print(
            f"{r['strategy']:<12} "
            f"{r['hit2_or_more']:>8} "
            f"{r['hit3_or_more']:>8} "
            f"{r['hit4_or_more']:>8} "
            f"{r['rate3']:>9.1f}%"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="ロト6 予想番号生成ツール")
    parser.add_argument("--update", action="store_true", help="最新データをダウンロード")
    parser.add_argument("--stats", action="store_true", help="統計情報のみ表示")
    parser.add_argument("--backtest", type=int, metavar="N", help="直近N回でバックテスト")
    parser.add_argument("--seed", type=int, default=None, help="乱数シード（再現用）")
    args = parser.parse_args()

    try:
        if args.update:
            print("最新データをダウンロード中...")
            auto_update_if_needed(force=True)
            print(f"保存完了: {DEFAULT_DATA_PATH}\n")
        elif auto_update_if_needed():
            status = get_data_status()
            print(f"当選データを自動更新しました（第{status['latest_round']}回まで）\n")

        draws = load_draws(auto_refresh=False)
        if not draws:
            print("データが読み込めませんでした。", file=sys.stderr)
            return 1

        analyzer = Loto6Analyzer(draws)
        print_header(analyzer)

        if args.stats:
            print_statistics(analyzer)
            return 0

        if args.backtest:
            print_backtest(analyzer, args.backtest)
            return 0

        print_statistics(analyzer)
        print_predictions(analyzer, seed=args.seed)

        print("=" * 60)
        print("  おすすめ: 「複合スコア法」の番号を参考にしてください")
        print("  データ更新: python predict.py --update")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
