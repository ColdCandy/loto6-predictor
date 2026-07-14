/**
 * ロト6予想 - ブラウザ版（Python不要）
 * LOTODATA は build_standalone.py が埋め込む
 */

class SeededRNG {
  constructor(seed = Date.now()) {
    this.state = seed >>> 0;
  }
  next() {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  choice(arr) {
    return arr[Math.floor(this.next() * arr.length)];
  }
  choices(arr, weights, k) {
    const total = weights.reduce((s, w) => s + w, 0);
    const out = [];
    for (let i = 0; i < k; i++) {
      let r = this.next() * total;
      for (let j = 0; j < arr.length; j++) {
        r -= weights[j];
        if (r <= 0) {
          out.push(arr[j]);
          break;
        }
      }
    }
    return out;
  }
  sample(arr, n) {
    const shuffled = this.shuffle(arr);
    return shuffled.slice(0, n);
  }
}

class Loto6Analyzer {
  constructor(draws) {
    this.draws = draws;
    this._freq = null;
    this._gaps = null;
    this._pairs = null;
  }

  get totalRounds() {
    return this.draws.length;
  }

  get latest() {
    return this.draws[this.draws.length - 1] || null;
  }

  frequency(includeBonus = true) {
    if (this._freq) return this._freq;
    const c = {};
    for (let n = 1; n <= 43; n++) c[n] = 0;
    for (const d of this.draws) {
      for (const n of d.n) c[n]++;
      if (includeBonus) c[d.b]++;
    }
    this._freq = c;
    return c;
  }

  recentFrequency(lastN = 50, includeBonus = true) {
    const c = {};
    for (let n = 1; n <= 43; n++) c[n] = 0;
    for (const d of this.draws.slice(-lastN)) {
      for (const n of d.n) c[n]++;
      if (includeBonus) c[d.b]++;
    }
    return c;
  }

  lastSeenGap() {
    if (this._gaps) return this._gaps;
    const gaps = {};
    for (let n = 1; n <= 43; n++) gaps[n] = this.draws.length;
    for (let i = this.draws.length - 1; i >= 0; i--) {
      const d = this.draws[i];
      const elapsed = this.draws.length - 1 - i;
      for (const n of d.n) {
        if (gaps[n] === this.draws.length) gaps[n] = elapsed;
      }
      if (gaps[d.b] === this.draws.length) gaps[d.b] = elapsed;
    }
    this._gaps = gaps;
    return gaps;
  }

  pairFrequency() {
    if (this._pairs) return this._pairs;
    const c = new Map();
    for (const d of this.draws) {
      const sorted = [...d.n].sort((a, b) => a - b);
      for (let i = 0; i < sorted.length; i++) {
        for (let j = i + 1; j < sorted.length; j++) {
          const key = `${sorted[i]}-${sorted[j]}`;
          c.set(key, (c.get(key) || 0) + 1);
        }
      }
    }
    this._pairs = c;
    return c;
  }

  topNumbers(n = 10, lastN = null) {
    const freq = lastN ? this.recentFrequency(lastN) : this.frequency();
    return Object.entries(freq)
      .map(([num, count]) => [+num, count])
      .sort((a, b) => b[1] - a[1])
      .slice(0, n);
  }

  overdueNumbers(n = 10) {
    const gaps = this.lastSeenGap();
    return Object.entries(gaps)
      .map(([num, gap]) => [+num, gap])
      .sort((a, b) => b[1] - a[1])
      .slice(0, n);
  }

  numberScores(lastN = 100) {
    const allFreq = this.frequency();
    const recent = this.recentFrequency(lastN);
    const gaps = this.lastSeenGap();
    const maxAll = Math.max(...Object.values(allFreq)) || 1;
    const maxRecent = Math.max(...Object.values(recent)) || 1;
    const maxGap = Math.max(...Object.values(gaps)) || 1;
    const scores = {};
    for (let num = 1; num <= 43; num++) {
      scores[num] =
        (allFreq[num] / maxAll) * 0.25 +
        (recent[num] / maxRecent) * 0.45 +
        (gaps[num] / maxGap) * 0.3;
    }
    return scores;
  }

  oddEvenDistribution() {
    const dist = {};
    for (let i = 0; i <= 6; i++) dist[i] = 0;
    for (const d of this.draws) {
      const odd = d.n.filter((x) => x % 2 === 1).length;
      dist[odd]++;
    }
    const total = this.draws.length;
    const result = {};
    for (const [k, v] of Object.entries(dist)) {
      result[`奇数${k}個`] = (v / total) * 100;
    }
    return result;
  }

  sumRangeStats() {
    const sums = this.draws.map((d) => d.n.reduce((a, b) => a + b, 0));
    return {
      平均: sums.reduce((a, b) => a + b, 0) / sums.length,
      最小: Math.min(...sums),
      最大: Math.max(...sums),
    };
  }
}

function formatNumbers(nums) {
  return [...nums].sort((a, b) => a - b).map((n) => String(n).padStart(2, "0")).join(" ");
}

function isBalanced(nums) {
  const odd = nums.filter((n) => n % 2 === 1).length;
  if (odd === 0 || odd === 6) return false;
  const total = nums.reduce((a, b) => a + b, 0);
  if (total < 80 || total > 220) return false;
  const low = nums.filter((n) => n <= 22).length;
  if (low === 0 || low === 6) return false;
  const sorted = [...nums].sort((a, b) => a - b);
  let consecutive = 0;
  for (let i = 0; i < sorted.length - 1; i++) {
    if (sorted[i + 1] - sorted[i] === 1) consecutive++;
  }
  return consecutive <= 3;
}

function pickFromScores(analyzer, scores, seed = null) {
  const rng = new SeededRNG(seed ?? Date.now());
  const ranked = Object.entries(scores)
    .map(([n, s]) => [+n, s])
    .sort((a, b) => b[1] - a[1]);
  const pool = ranked.slice(0, 18).map(([n]) => n);
  const weights = pool.map((n) => scores[n]);

  for (let t = 0; t < 500; t++) {
    const chosen = rng.choices(pool, weights, 12);
    const unique = [...new Set(chosen)];
    if (unique.length >= 6) {
      const candidate = rng.sample(unique.slice(0, 10), 6);
      if (isBalanced(candidate)) return candidate;
    }
  }
  return ranked.slice(0, 6).map(([n]) => n);
}

function makeResult(name, description, numbers, extra = {}) {
  return { name, description, numbers, formatted: formatNumbers(numbers), ...extra };
}

const Strategies = {
  composite(analyzer, seed) {
    const scores = analyzer.numberScores(100);
    const nums = pickFromScores(analyzer, scores, seed);
    return makeResult(
      "複合スコア法（おすすめ）",
      "出現頻度・直近傾向・出遅れを総合的に評価します",
      nums
    );
  },
  hot(analyzer, seed) {
    const scores = {};
    for (let n = 1; n <= 43; n++) scores[n] = 0;
    analyzer.topNumbers(15).forEach(([n, c]) => (scores[n] = c));
    return makeResult(
      "ホットナンバー法",
      "過去全体で出現回数が多い数字を中心に選びます",
      pickFromScores(analyzer, scores, seed)
    );
  },
  recent(analyzer, seed) {
    const scores = {};
    for (let n = 1; n <= 43; n++) scores[n] = 0;
    analyzer.topNumbers(15, 50).forEach(([n, c]) => (scores[n] = c * 2));
    return makeResult(
      "直近トレンド法",
      "直近50回でよく出ている数字を重視します",
      pickFromScores(analyzer, scores, seed)
    );
  },
  overdue(analyzer, seed) {
    const scores = {};
    for (let n = 1; n <= 43; n++) scores[n] = 0;
    analyzer.overdueNumbers(15).forEach(([n, gap]) => (scores[n] = gap));
    return makeResult(
      "間隔分析（出遅れ）法",
      "長期間出ていない数字が出るという考え方に基づきます",
      pickFromScores(analyzer, scores, seed)
    );
  },
  pair(analyzer, seed) {
    const rng = new SeededRNG(seed ?? Date.now());
    const pairs = analyzer.pairFrequency();
    const topPairs = [...pairs.entries()]
      .map(([key, count]) => ({ pair: key.split("-").map(Number), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 30);
    const shuffled = rng.shuffle(topPairs);
    const nums = new Set();
    for (const { pair } of shuffled) {
      nums.add(pair[0]);
      nums.add(pair[1]);
      if (nums.size >= 6) break;
    }
    if (nums.size < 6) {
      analyzer.topNumbers(6).forEach(([n]) => nums.add(n));
    }
    const result = [...nums].sort((a, b) => a - b).slice(0, 6);
    return makeResult(
      "相性ペア法",
      "過去に一緒に出やすい数字のペアを組み合わせます",
      result
    );
  },
  elimination(analyzer, seed) {
    const freq = analyzer.frequency();
    const recent = analyzer.recentFrequency(100);
    const sortedVals = Object.values(freq).sort((a, b) => a - b);
    const threshold = sortedVals[10];
    const eliminated = [];
    for (let n = 1; n <= 43; n++) {
      if (freq[n] <= threshold && recent[n] <= 2) eliminated.push(n);
    }
    const scores = analyzer.numberScores();
    const filtered = {};
    for (let n = 1; n <= 43; n++) {
      if (!eliminated.includes(n)) filtered[n] = scores[n];
    }
    return makeResult(
      "消去法",
      "出にくい数字を除外し、残りから選びます",
      pickFromScores(analyzer, filtered, seed),
      { eliminated }
    );
  },
  balanced(analyzer, seed) {
    const rng = new SeededRNG(seed ?? Date.now());
    const scores = analyzer.numberScores();
    const ranked = Object.entries(scores)
      .map(([n, s]) => [+n, s])
      .sort((a, b) => b[1] - a[1])
      .map(([n]) => n);

    for (let t = 0; t < 1000; t++) {
      const odds = ranked.filter((n) => n % 2 === 1).slice(0, 12);
      const evens = ranked.filter((n) => n % 2 === 0).slice(0, 12);
      const pick = new Set();
      rng.sample(odds, Math.min(3, odds.length)).forEach((n) => pick.add(n));
      rng.sample(evens, Math.min(3, evens.length)).forEach((n) => pick.add(n));
      while (pick.size < 6) pick.add(rng.choice(ranked.slice(0, 20)));
      const nums = [...pick].slice(0, 6);
      if (isBalanced(nums)) {
        return makeResult(
          "バランス配分法",
          "奇数/偶数・小/大のバランスを考慮して選びます",
          nums
        );
      }
    }
    return makeResult(
      "バランス配分法",
      "奇数/偶数・小/大のバランスを考慮して選びます",
      ranked.slice(0, 6)
    );
  },
};

const STRATEGY_LIST = [
  { key: "composite", label: "複合スコア法（おすすめ）" },
  { key: "hot", label: "ホットナンバー法" },
  { key: "recent", label: "直近トレンド法" },
  { key: "overdue", label: "間隔分析（出遅れ）法" },
  { key: "pair", label: "相性ペア法" },
  { key: "elimination", label: "消去法" },
  { key: "balanced", label: "バランス配分法" },
];

function generateAll(analyzer, seed) {
  return STRATEGY_LIST.map(({ key }) => Strategies[key](analyzer, seed));
}

function renderBalls(nums) {
  return nums
    .sort((a, b) => a - b)
    .map((n, i) => `<span class="ball" style="animation-delay:${i * 2.78}ms">${String(n).padStart(2, "0")}</span>`)
    .join("");
}

function renderBarChart(containerId, data, labelKey = "label", valueKey = "value") {
  const el = document.getElementById(containerId);
  if (!el) return;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  el.innerHTML = data
    .map(
      (d) => `
    <div class="bar-row">
      <span class="bar-label">${d[labelKey]}</span>
      <div class="apple-bar-track"><div class="apple-bar-fill" style="width:${(d[valueKey] / max) * 100}%"></div></div>
      <span class="bar-value">${d[valueKey]}</span>
    </div>`
    )
    .join("");
  if (window.UltraSmooth) {
    requestAnimationFrame(() => UltraSmooth.animateBars(el));
  }
}

function renderPrediction(container, pred) {
  let html = `<div class="apple-result-box smooth-reveal">
    <h3>${pred.name}</h3>
    <p class="desc">${pred.description}</p>
    <div class="ball-row">${renderBalls(pred.numbers)}</div>
    <p class="copy-text">コピー用: ${pred.formatted}</p>`;
  if (pred.eliminated && pred.eliminated.length) {
    html += `<p class="eliminated">除外候補: ${pred.eliminated.slice(0, 12).map((n) => String(n).padStart(2, "0")).join(" ")}</p>`;
  }
  html += "</div>";
  container.innerHTML = html;
  if (window.UltraSmooth) {
    UltraSmooth.enhanceBalls(container);
  }
}

function renderAllPredictions(container, preds) {
  container.innerHTML = preds
    .map(
      (pred) => `<div class="apple-result-box smooth-reveal">
      <h3>${pred.name}</h3>
      <p class="desc">${pred.description}</p>
      <div class="ball-row">${renderBalls(pred.numbers)}</div>
      <p class="copy-text">コピー用: ${pred.formatted}</p>
    </div>`
    )
    .join("");
  if (window.UltraSmooth) UltraSmooth.enhanceBalls(container);
}

let analyzer = null;
let currentKey = null;
let currentSeed = Date.now() % 1000000;

function initApp() {
  try {
    if (typeof LOTODATA === "undefined" || !LOTODATA.draws || !LOTODATA.draws.length) {
      document.body.innerHTML =
        "<p style='padding:2rem;font-family:sans-serif'>データが読み込めません。" +
        "数分後にページを再読み込みするか、<a href='https://coldcandy.github.io/loto6-predictor/'>こちら</a>を開いてください。</p>";
      return;
    }

    analyzer = new Loto6Analyzer(LOTODATA.draws);
    const latest = analyzer.latest;

    // メトリクスは先に同期表示（アニメ失敗でも "-" のままにしない）
    const roundsEl = document.getElementById("meta-rounds");
    if (roundsEl) roundsEl.textContent = `${analyzer.totalRounds} 回`;
    document.getElementById("meta-latest-round").textContent = latest ? `第 ${latest.r} 回` : "-";
    document.getElementById("meta-latest-date").textContent = latest ? latest.d : "-";
    document.getElementById("meta-updated").textContent = LOTODATA.updated || "-";

    if (window.UltraSmooth && roundsEl) {
      try {
        UltraSmooth.animateValue(roundsEl, analyzer.totalRounds, 480, " 回");
      } catch (_) {}
    }

    if (latest) {
      document.getElementById("latest-balls").innerHTML = renderBalls(latest.n);
      document.getElementById("latest-bonus").textContent = `ボーナス: ${String(latest.b).padStart(2, "0")}`;
    }

    const btnArea = document.getElementById("strategy-buttons");
    STRATEGY_LIST.forEach(({ key, label }) => {
      const btn = document.createElement("button");
      btn.className = "apple-btn";
      btn.textContent = label;
      btn.onclick = () => {
        currentKey = key;
        currentSeed = Date.now() % 1000000;
        renderPrediction(document.getElementById("results"), Strategies[key](analyzer, currentSeed));
      };
      btnArea.appendChild(btn);
    });

  document.getElementById("btn-recommend").onclick = () => {
    currentKey = "composite";
    currentSeed = Date.now() % 1000000;
    renderPrediction(document.getElementById("results"), Strategies.composite(analyzer, currentSeed));
  };

  document.getElementById("btn-all").onclick = () => {
    currentKey = null;
    currentSeed = Date.now() % 1000000;
    renderAllPredictions(document.getElementById("results"), generateAll(analyzer, currentSeed));
  };

  document.getElementById("btn-reroll").onclick = () => {
    currentSeed = Date.now() % 1000000;
    if (currentKey) {
      renderPrediction(document.getElementById("results"), Strategies[currentKey](analyzer, currentSeed));
    } else {
      renderAllPredictions(document.getElementById("results"), generateAll(analyzer, currentSeed));
    }
  };

  document.querySelectorAll(".apple-tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".apple-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const panel = document.getElementById(tab.dataset.panel);
      panel.classList.add("active");
      if (window.UltraSmooth) UltraSmooth.smoothTabSwitch(panel);
      if (tab.dataset.panel === "panel-stats") renderStats();
    };
  });
  } catch (err) {
    console.error(err);
    document.body.innerHTML =
      "<p style='padding:2rem;font-family:sans-serif'>画面の初期化に失敗しました。<br>" +
      String(err) +
      "<br><a href='https://coldcandy.github.io/loto6-predictor/'>再読み込み</a></p>";
  }
}

function renderStats() {
  const freq = analyzer.frequency();
  renderBarChart(
    "chart-all",
    analyzer.topNumbers(20).map(([n, c]) => ({ label: String(n).padStart(2, "0"), value: c }))
  );
  renderBarChart(
    "chart-recent",
    analyzer.topNumbers(20, 50).map(([n, c]) => ({ label: String(n).padStart(2, "0"), value: c }))
  );
  renderBarChart(
    "chart-heat",
    Object.entries(freq)
      .map(([n, c]) => ({ label: String(n).padStart(2, "0"), value: c }))
      .sort((a, b) => a.label.localeCompare(b.label))
  );

  const overdueEl = document.getElementById("overdue-table");
  overdueEl.innerHTML = analyzer
    .overdueNumbers(15)
    .map(([n, gap]) => `<tr><td>${String(n).padStart(2, "0")}</td><td>${gap}回前</td></tr>`)
    .join("");

  const oddDist = analyzer.oddEvenDistribution();
  renderBarChart(
    "chart-odd",
    Object.entries(oddDist).map(([k, v]) => ({ label: k, value: Math.round(v * 10) / 10 }))
  );

  const sum = analyzer.sumRangeStats();
  document.getElementById("sum-stats").textContent =
    `本数字合計: 平均 ${sum.平均.toFixed(1)} / 最小 ${sum.最小} / 最大 ${sum.最大}`;
}

document.addEventListener("DOMContentLoaded", initApp);
