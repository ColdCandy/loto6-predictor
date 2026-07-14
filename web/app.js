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

const MINE_KEY = "loto6_my_numbers_v1";
const PRIZE_NAMES = {
  1: "1等（6個一致）",
  2: "2等（5個+ボーナス）",
  3: "3等（5個一致）",
  4: "4等（4個一致）",
  5: "5等（3個一致）",
};

function showToast(msg) {
  let el = document.getElementById("toast-mini");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast-mini";
    el.className = "toast-mini";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.remove("show"), 1800);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast("コピーしました");
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    showToast("コピーしました");
  }
}

function loadMine() {
  try {
    return JSON.parse(localStorage.getItem(MINE_KEY) || "[]");
  } catch (_) {
    return [];
  }
}

function saveMine(items) {
  localStorage.setItem(MINE_KEY, JSON.stringify(items.slice(0, 40)));
}

function addMine(numbers, label) {
  const formatted = formatNumbers(numbers);
  const items = loadMine().filter((x) => x.formatted !== formatted);
  items.unshift({
    formatted,
    numbers: [...numbers].sort((a, b) => a - b),
    label: label || "保存番号",
    savedAt: new Date().toISOString(),
  });
  saveMine(items);
  showToast("マイ番号に保存しました");
  renderMineList();
}

function parseNumbers(text) {
  const parts = String(text || "")
    .split(/[\s,、．.]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => parseInt(s, 10));
  const nums = parts.filter((n) => Number.isInteger(n) && n >= 1 && n <= 43);
  const uniq = [...new Set(nums)];
  if (uniq.length !== 6) return null;
  return uniq.sort((a, b) => a - b);
}

function findDrawByRound(round) {
  if (!analyzer) return null;
  return analyzer.draws.find((d) => d.r === round) || null;
}

function checkWinning(picked, draw) {
  const set = new Set(picked);
  const main = new Set(draw.n);
  const hits = [...set].filter((n) => main.has(n)).length;
  const bonusHit = set.has(draw.b);
  let tier = null;
  if (hits === 6) tier = 1;
  else if (hits === 5 && bonusHit) tier = 2;
  else if (hits === 5) tier = 3;
  else if (hits === 4) tier = 4;
  else if (hits === 3) tier = 5;
  return {
    hits,
    bonusHit,
    tier,
    prizeName: tier ? PRIZE_NAMES[tier] : "はずれ",
    matched: [...set].filter((n) => main.has(n)).sort((a, b) => a - b),
  };
}

function nextDrawDates(count = 4) {
  const found = [];
  const now = new Date();
  const jst = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Tokyo" }));
  for (let i = 0; i < 21 && found.length < count; i++) {
    const d = new Date(jst);
    d.setDate(jst.getDate() + i);
    const wd = d.getDay(); // 0=Sun ... 1=Mon, 4=Thu
    if (wd === 1 || wd === 4) found.push(d);
  }
  return found;
}

function formatJpDate(d) {
  const weekdays = "日月火水木金土";
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}（${weekdays[d.getDay()]}）`;
}

function nextDrawDeadline(d) {
  // 抽選日 18:45 JST を目安にカウントダウン
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return new Date(`${y}-${m}-${day}T18:45:00+09:00`);
}

function updateCountdown() {
  const valueEl = document.getElementById("countdown-value");
  const subEl = document.getElementById("countdown-sub");
  if (!valueEl) return;
  const upcoming = nextDrawDates(3);
  if (!upcoming.length) {
    valueEl.textContent = "-";
    return;
  }
  let targetDate = upcoming[0];
  let deadline = nextDrawDeadline(targetDate);
  const now = Date.now();
  if (deadline.getTime() <= now && upcoming[1]) {
    targetDate = upcoming[1];
    deadline = nextDrawDeadline(targetDate);
  }
  const diff = Math.max(0, deadline.getTime() - now);
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  valueEl.textContent =
    days > 0
      ? `${days}日 ${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
      : `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  if (subEl) {
    subEl.textContent = `次回 ${formatJpDate(targetDate)} 18:45 頃｜その後 ${upcoming
      .slice(1, 3)
      .map(formatJpDate)
      .join(" / ")}`;
  }
}

function predictionCardHtml(pred, extraButtons = "") {
  let html = `<div class="apple-result-box smooth-reveal" data-formatted="${pred.formatted}">
    <h3>${pred.name}</h3>
    <p class="desc">${pred.description || ""}</p>
    <div class="ball-row">${renderBalls(pred.numbers)}</div>
    <p class="copy-text">コピー用: ${pred.formatted}</p>
    <div class="result-actions">
      <button type="button" class="apple-btn apple-btn-primary btn-copy-line" data-text="${pred.formatted}">コピー</button>
      <button type="button" class="apple-btn btn-save-line" data-text="${pred.formatted}" data-label="${pred.name}">マイ番号に保存</button>
      ${extraButtons}
    </div>`;
  if (pred.eliminated && pred.eliminated.length) {
    html += `<p class="eliminated">除外候補: ${pred.eliminated
      .slice(0, 12)
      .map((n) => String(n).padStart(2, "0"))
      .join(" ")}</p>`;
  }
  html += "</div>";
  return html;
}

function bindResultActions(container) {
  if (!container) return;
  container.querySelectorAll(".btn-copy-line").forEach((btn) => {
    btn.onclick = () => copyText(btn.dataset.text || "");
  });
  container.querySelectorAll(".btn-save-line").forEach((btn) => {
    btn.onclick = () => {
      const nums = parseNumbers(btn.dataset.text || "");
      if (nums) addMine(nums, btn.dataset.label || "予想番号");
    };
  });
  container.querySelectorAll(".btn-check-line").forEach((btn) => {
    btn.onclick = () => {
      const input = document.getElementById("check-numbers");
      if (input) input.value = btn.dataset.text || "";
      document.querySelectorAll(".apple-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      const tab = document.querySelector('.apple-tab[data-panel="panel-check"]');
      const panel = document.getElementById("panel-check");
      if (tab) tab.classList.add("active");
      if (panel) panel.classList.add("active");
      runCheck(false);
    };
  });
}

function renderPrediction(container, pred) {
  container.innerHTML = predictionCardHtml(pred);
  bindResultActions(container);
  if (window.UltraSmooth) UltraSmooth.enhanceBalls(container);
}

function renderAllPredictions(container, preds) {
  container.innerHTML = preds.map((pred) => predictionCardHtml(pred)).join("");
  bindResultActions(container);
  if (window.UltraSmooth) UltraSmooth.enhanceBalls(container);
}

function buildWeeklyPack() {
  const tip = LOTODATA.ai_tip;
  const pack = [];
  if (tip && tip.numbers) {
    pack.push(
      makeResult(
        "AI検証済み本命",
        `第${tip.based_on_round || "?"}回学習｜確信度 ${tip.confidence || "-"}%`,
        tip.numbers
      )
    );
    (tip.pool || [])
      .filter((p) => p.line_no !== 1)
      .slice(0, 3)
      .forEach((p) => {
        pack.push(
          makeResult(
            `カバー行 ${p.line_no}`,
            "本命周辺の差し替え行（ほぼ一致狙い）",
            p.numbers
          )
        );
      });
  }
  pack.push(Strategies.composite(analyzer, currentSeed));
  pack.push(Strategies.recent(analyzer, currentSeed + 7));
  pack.push(Strategies.overdue(analyzer, currentSeed + 13));
  // 重複行を除外
  const seen = new Set();
  return pack.filter((p) => {
    if (seen.has(p.formatted)) return false;
    seen.add(p.formatted);
    return true;
  });
}

function renderWeeklyPack() {
  const box = document.getElementById("weekly-pack-results");
  if (!box) return;
  const pack = buildWeeklyPack();
  box.dataset.pack = JSON.stringify(pack.map((p) => ({ numbers: p.numbers, name: p.name })));
  box.innerHTML = pack.map((p) => predictionCardHtml(p)).join("");
  bindResultActions(box);
  if (window.UltraSmooth) UltraSmooth.enhanceBalls(box);
}

function renderMineList() {
  const el = document.getElementById("mine-list");
  if (!el) return;
  const items = loadMine();
  if (!items.length) {
    el.innerHTML = `<p class="hint">まだ保存がありません。「マイ番号に保存」やおすすめパックから追加できます</p>`;
    return;
  }
  el.innerHTML = items
    .map((item, idx) => {
      const saved = item.savedAt ? new Date(item.savedAt) : null;
      const when = saved
        ? `${saved.getMonth() + 1}/${saved.getDate()} ${String(saved.getHours()).padStart(2, "0")}:${String(
            saved.getMinutes()
          ).padStart(2, "0")}`
        : "";
      return `<div class="mine-item">
        <div class="mine-meta">${item.label || "保存番号"}｜${when}</div>
        <div class="ball-row">${renderBalls(item.numbers)}</div>
        <p class="copy-text">${item.formatted}</p>
        <div class="result-actions">
          <button type="button" class="apple-btn apple-btn-primary btn-copy-line" data-text="${item.formatted}">コピー</button>
          <button type="button" class="apple-btn btn-check-line" data-text="${item.formatted}">当選チェック</button>
          <button type="button" class="apple-btn btn-del-mine" data-idx="${idx}">削除</button>
        </div>
      </div>`;
    })
    .join("");
  bindResultActions(el);
  el.querySelectorAll(".btn-del-mine").forEach((btn) => {
    btn.onclick = () => {
      const items2 = loadMine();
      items2.splice(+btn.dataset.idx, 1);
      saveMine(items2);
      renderMineList();
      showToast("削除しました");
    };
  });
}

function runCheck(historyMode) {
  const out = document.getElementById("check-result");
  const nums = parseNumbers(document.getElementById("check-numbers")?.value);
  if (!nums) {
    out.innerHTML = `<div class="check-result-box lose">1〜43から重複なし6個を入力してください</div>`;
    return;
  }
  if (historyMode) {
    const target = analyzer.draws.slice(-100);
    const tally = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, miss: 0 };
    let best = null;
    for (const d of target) {
      const r = checkWinning(nums, d);
      if (r.tier) {
        tally[r.tier] += 1;
        if (!best || r.tier < best.tier) best = { ...r, round: d.r, date: d.d };
      } else tally.miss += 1;
    }
    out.innerHTML = `<div class="check-result-box ${best ? "win" : "lose"}">
      <div class="ball-row">${renderBalls(nums)}</div>
      <p style="margin-top:10px"><b>直近100回の結果</b></p>
      <p>1等 ${tally[1]} / 2等 ${tally[2]} / 3等 ${tally[3]} / 4等 ${tally[4]} / 5等 ${tally[5]} / はずれ ${tally.miss}</p>
      ${
        best
          ? `<p>最良: 第${best.round}回（${best.date}） ${best.prizeName}・一致 ${best.hits}個</p>`
          : "<p>5等以上はなし</p>"
      }
    </div>`;
    return;
  }

  const roundRaw = document.getElementById("check-round")?.value;
  const draw = roundRaw ? findDrawByRound(parseInt(roundRaw, 10)) : analyzer.latest;
  if (!draw) {
    out.innerHTML = `<div class="check-result-box lose">指定した回のデータが見つかりません</div>`;
    return;
  }
  const r = checkWinning(nums, draw);
  out.innerHTML = `<div class="check-result-box ${r.tier ? "win" : "lose"}">
    <p><b>第${draw.r}回（${draw.d}）</b></p>
    <p>あなたの番号</p>
    <div class="ball-row">${renderBalls(nums)}</div>
    <p style="margin-top:10px">当選番号</p>
    <div class="ball-row">${renderBalls(draw.n)}</div>
    <p style="margin-top:8px;color:var(--label-secondary)">ボーナス: ${String(draw.b).padStart(2, "0")}</p>
    <p style="margin-top:12px;font-size:1.1rem"><b>${r.prizeName}</b></p>
    <p>一致 ${r.hits}個${r.bonusHit ? " ＋ボーナス" : ""}｜一致数字: ${
      r.matched.length ? formatNumbers(r.matched) : "なし"
    }</p>
  </div>`;
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

    updateCountdown();
    setInterval(updateCountdown, 1000);

    const status = LOTODATA.auto_status;
    const statusCard = document.getElementById("auto-status-card");
    if (status && statusCard) {
      statusCard.style.display = "";
      const st = document.getElementById("auto-status-text");
      if (st) {
        st.textContent =
          `最終自動処理 ${status.checked_at || "-"}｜学習 ${status.trained ? "実施" : "スキップ"}｜` +
          `本命 ${status.tip_formatted || "-"}｜第${status.new_round || "?"}回まで保存済み`;
      }
    }

    const tip = LOTODATA.ai_tip;
    const tipCard = document.getElementById("ai-tip-card");
    if (tip && tip.numbers && tipCard) {
      tipCard.style.display = "";
      const meta = document.getElementById("ai-tip-meta");
      if (meta) {
        meta.textContent =
          `第${tip.based_on_round || "?"}回時点の学習結果｜確信度 ${tip.confidence || "-"}%（${tip.confidence_label || ""}）｜更新 ${tip.generated_at || ""}`;
      }
      document.getElementById("ai-tip-balls").innerHTML = renderBalls(tip.numbers);
      document.getElementById("ai-tip-copy").textContent = `コピー用: ${tip.formatted || ""}`;
      const poolEl = document.getElementById("ai-tip-pool");
      if (poolEl && tip.pool && tip.pool.length) {
        poolEl.innerHTML = tip.pool
          .slice(0, 8)
          .map((p) => `${p.line_no === 1 ? "★本命" : p.line_no + "."} ${p.formatted}`)
          .join("<br>");
      }
      const copyAi = document.getElementById("btn-copy-ai");
      const saveAi = document.getElementById("btn-save-ai");
      if (copyAi) copyAi.onclick = () => copyText(tip.formatted || formatNumbers(tip.numbers));
      if (saveAi) saveAi.onclick = () => addMine(tip.numbers, "AI検証済み本命");
    }

    document.getElementById("btn-weekly-pack").onclick = () => {
      currentSeed = Date.now() % 1000000;
      renderWeeklyPack();
    };
    document.getElementById("btn-save-pack").onclick = () => {
      const box = document.getElementById("weekly-pack-results");
      if (!box?.dataset.pack) {
        renderWeeklyPack();
      }
      const pack = JSON.parse(document.getElementById("weekly-pack-results").dataset.pack || "[]");
      pack.forEach((p) => addMine(p.numbers, p.name));
      showToast(`${pack.length}行を保存しました`);
      document.querySelectorAll(".apple-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      document.querySelector('.apple-tab[data-panel="panel-mine"]')?.classList.add("active");
      document.getElementById("panel-mine")?.classList.add("active");
      renderMineList();
    };

    // 起動時におすすめパックを自動表示
    renderWeeklyPack();
    renderMineList();

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

    document.getElementById("btn-check").onclick = () => runCheck(false);
    document.getElementById("btn-check-history").onclick = () => runCheck(true);
    document.getElementById("btn-clear-mine").onclick = () => {
      if (confirm("マイ番号をすべて削除しますか？")) {
        saveMine([]);
        renderMineList();
        showToast("削除しました");
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
        if (tab.dataset.panel === "panel-mine") renderMineList();
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
