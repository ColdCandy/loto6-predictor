"""過去当選データの統計分析"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from .data import Draw


class Loto6Analyzer:
    def __init__(self, draws: list[Draw]):
        self.draws = draws
        self._freq_all: Counter[int] | None = None
        self._last_seen: dict[int, int] | None = None
        self._pair_freq: Counter[tuple[int, int]] | None = None

    @property
    def total_rounds(self) -> int:
        return len(self.draws)

    @property
    def latest(self) -> Draw | None:
        return self.draws[-1] if self.draws else None

    def frequency(self, include_bonus: bool = True) -> Counter[int]:
        if self._freq_all is None:
            c: Counter[int] = Counter()
            for d in self.draws:
                c.update(d.numbers)
                if include_bonus:
                    c[d.bonus] += 1
            self._freq_all = c
        return self._freq_all

    def recent_frequency(self, last_n: int = 50, include_bonus: bool = True) -> Counter[int]:
        c: Counter[int] = Counter()
        for d in self.draws[-last_n:]:
            c.update(d.numbers)
            if include_bonus:
                c[d.bonus] += 1
        return c

    def last_seen_gap(self) -> dict[int, int]:
        """各数字が最後に出てから何回経ったか（0=直近回）"""
        if self._last_seen is None:
            gaps = {n: len(self.draws) for n in range(1, 44)}
            for i, d in enumerate(reversed(self.draws)):
                for n in d.numbers:
                    if gaps[n] == len(self.draws):
                        gaps[n] = i
                if gaps[d.bonus] == len(self.draws):
                    gaps[d.bonus] = i
            self._last_seen = gaps
        return self._last_seen

    def pair_frequency(self) -> Counter[tuple[int, int]]:
        if self._pair_freq is None:
            c: Counter[tuple[int, int]] = Counter()
            for d in self.draws:
                for pair in combinations(sorted(d.numbers), 2):
                    c[pair] += 1
            self._pair_freq = c
        return self._pair_freq

    def odd_even_distribution(self) -> dict[str, float]:
        """奇数の個数の分布（0〜6個）"""
        dist: Counter[int] = Counter()
        for d in self.draws:
            odd_count = sum(1 for n in d.numbers if n % 2 == 1)
            dist[odd_count] += 1
        total = len(self.draws)
        return {f"奇数{k}個": v / total * 100 for k, v in sorted(dist.items())}

    def sum_range_stats(self) -> dict[str, float]:
        sums = [sum(d.numbers) for d in self.draws]
        return {
            "平均": sum(sums) / len(sums),
            "最小": float(min(sums)),
            "最大": float(max(sums)),
        }

    def top_numbers(self, n: int = 10, last_n: int | None = None) -> list[tuple[int, int]]:
        freq = self.recent_frequency(last_n) if last_n else self.frequency()
        return freq.most_common(n)

    def overdue_numbers(self, n: int = 10) -> list[tuple[int, int]]:
        gaps = self.last_seen_gap()
        return sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:n]

    def number_scores(self, last_n: int = 100) -> dict[int, float]:
        """複合スコア（出現頻度 + 最近の傾向 + 間隔）"""
        all_freq = self.frequency()
        recent = self.recent_frequency(last_n)
        gaps = self.last_seen_gap()
        max_all = max(all_freq.values()) or 1
        max_recent = max(recent.values()) or 1
        max_gap = max(gaps.values()) or 1

        scores: dict[int, float] = {}
        for num in range(1, 44):
            scores[num] = (
                all_freq[num] / max_all * 0.25
                + recent[num] / max_recent * 0.45
                + gaps[num] / max_gap * 0.30
            )
        return scores

    def best_pairs_for(self, num: int, n: int = 5) -> list[tuple[int, int]]:
        pairs = self.pair_frequency()
        related: list[tuple[int, int]] = []
        for (a, b), count in pairs.items():
            if a == num:
                related.append((b, count))
            elif b == num:
                related.append((a, count))
        return sorted(related, key=lambda x: x[1], reverse=True)[:n]

    def number_profile(self, numbers: list[int]) -> list[dict]:
        """予想番号向けの出現・直近・出遅れプロファイル"""
        freq = self.frequency(include_bonus=False)
        recent = self.recent_frequency(50, include_bonus=False)
        gaps = self.last_seen_gap()
        rows: list[dict] = []
        for n in sorted(set(numbers)):
            if not (1 <= n <= 43):
                continue
            rows.append(
                {
                    "number": n,
                    "all_count": int(freq[n]),
                    "recent50": int(recent[n]),
                    "gap": int(gaps.get(n, 0)),
                    "all_rate": round(freq[n] / max(len(self.draws), 1), 4),
                    "recent_rate": round(recent[n] / min(50, max(len(self.draws), 1)), 4),
                }
            )
        return rows

    def rolling_hit_series(
        self,
        numbers: list[int],
        window: int = 50,
        windows: int = 12,
    ) -> dict:
        """直近を window 回×windows 個に分け、各番号の出現回数推移を返す"""
        nums = [n for n in sorted(set(numbers)) if 1 <= n <= 43]
        total_need = window * windows
        if len(self.draws) < window:
            return {"labels": [], "series": {n: [] for n in nums}, "window": window}

        start = max(0, len(self.draws) - total_need)
        usable = self.draws[start:]
        # usable を window サイズのチャンクに分割（端数は先頭から捨てる）
        n_win = len(usable) // window
        usable = usable[len(usable) - n_win * window :]
        labels: list[str] = []
        series: dict[int, list[int]] = {n: [] for n in nums}
        for i in range(n_win):
            chunk = usable[i * window : (i + 1) * window]
            c: Counter[int] = Counter()
            for d in chunk:
                c.update(d.numbers)
            first_r = chunk[0].round_num
            last_r = chunk[-1].round_num
            labels.append(f"{first_r}-{last_r}")
            for n in nums:
                series[n].append(int(c[n]))
        return {"labels": labels, "series": series, "window": window}
