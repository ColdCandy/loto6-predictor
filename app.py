"""Streamlit GUI - ロト6予想番号"""

from __future__ import annotations

import json
import random
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from loto6_predictor.apple_ui import inject_apple_theme, render_hero
from loto6_predictor.auth import render_sidebar_account, require_login
from loto6_predictor.analyzer import Loto6Analyzer
from loto6_predictor.cloud import is_cloud_hosted
from loto6_predictor.data import (
    get_data_status,
    get_monitor_live_status,
    load_draws,
    load_watch_state,
    realtime_poll_interval_seconds,
    realtime_watch_update,
)
from loto6_predictor.checker import (
    analyze_numbers,
    backtest_numbers,
    check_winning,
    format_draw_date,
    next_draw_dates,
)
from loto6_predictor.favorites import delete_favorite, load_favorites, save_favorite
from loto6_predictor.strategies import (
    STRATEGY_BY_NAME,
    backtest_strategy,
    generate_all_predictions,
    generate_multiple_lines,
    strategy_ai_confidence,
    strategy_ai_verified,
    strategy_composite,
    strategy_loto67_overlap,
    strategy_monthly_anchor,
    strategy_monthly_inverse,
    strategy_overdue,
    strategy_quick_pick,
    strategy_recent_trend,
)
from loto6_predictor.monthly_patterns import monthly_analysis_summary
from loto6_predictor.loto7_data import DEFAULT_DATA_PATH as LOTO7_DATA_PATH
from loto6_predictor.loto7_data import get_data_status as get_loto7_data_status
from loto6_predictor.loto7_data import load_draws as load_loto7_draws


def _get_lan_ip() -> str | None:
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None

def _init_streamlit_ui() -> None:
    """クラウド起動を安定させるため、最初の Streamlit 操作は main 内で1回だけ実行"""
    if st.session_state.get("_ui_ready"):
        # streamlit_app 側で page_config 済みならテーマだけ注入
        try:
            inject_apple_theme()
        except Exception:
            pass
        return
    try:
        st.set_page_config(
            page_title="ロト6 予想番号",
            page_icon="🎱",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass
    try:
        inject_apple_theme()
    except Exception:
        pass
    st.session_state["_ui_ready"] = True


@st.cache_data(ttl=30)
def load_analyzer() -> Loto6Analyzer:
    from loto6_predictor.data import download_csv, DEFAULT_DATA_PATH

    draws = load_draws(auto_refresh=False)
    if not draws:
        try:
            download_csv(DEFAULT_DATA_PATH)
            draws = load_draws(auto_refresh=False)
        except Exception:
            pass
    if not draws:
        raise RuntimeError(
            "当選データがありません。ネット接続を確認するか、"
            "https://coldcandy.github.io/loto6-predictor/ をご利用ください。"
        )
    return Loto6Analyzer(draws)


def _render_live_monitor_bar() -> None:
    if is_cloud_hosted():
        # Cloud では描画経路でネット取得しない（起動ハング / Oh no の原因になる）
        status = get_data_status()
        from datetime import datetime, timezone, timedelta as td

        jst = timezone(td(hours=9))
        now_str = datetime.now(jst).strftime("%H:%M:%S")
        st.markdown(
            f'<div class="live-status">'
            f'<span class="pulse-dot"></span>'
            f'<span>クラウド常時稼働中</span>'
            f'<span>｜ 現在 <b>{now_str}</b></span>'
            f'<span>｜ 第<b>{status.get("latest_round", "-")}</b>回</span>'
            f'<span>｜ 更新: {status.get("updated_at", "-")}</span>'
            f'<span>｜ 最新化は左の「今すぐ最新データを取得」</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    live = get_monitor_live_status()

    if live["due"]:
        result = realtime_watch_update(force=True)
        st.session_state["watch_result"] = result
        if result.updated:
            load_analyzer.clear()
            if result.latest_round != result.previous_round:
                st.toast(f"🎉 第{result.latest_round}回の当選データを取得しました！", icon="🎱")
            st.rerun()
        live = get_monitor_live_status()

    if live.get("error"):
        st.markdown(
            f'<div class="live-status" style="background:#fff5f5;border-color:#ffc9c9;color:#c92a2a">'
            f'<span class="pulse-dot" style="background:#fa5252"></span>'
            f'接続エラー: {live["error"]} ｜ 再試行まで {live["remaining"]}秒</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="live-status">'
            f'<span class="pulse-dot"></span>'
            f'<span>リアルタイム監視中（{live["mode"]}・{live["poll_seconds"]}秒ごと）</span>'
            f'<span>｜ 最終確認 <b>{live["last_check"]}</b></span>'
            f'<span>｜ 次回チェック <b>{live["remaining"]}</b>秒</span>'
            f'<span>｜ 現在時刻 <b>{live["now"]}</b></span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_live_sidebar_panel() -> None:
    status = get_data_status()
    from datetime import datetime, timezone, timedelta as td

    jst = timezone(td(hours=9))
    now_str = datetime.now(jst).strftime("%H:%M:%S")

    if is_cloud_hosted():
        last_check = status.get("updated_at", "-")
        html = (
            f'<div class="sidebar-live">'
            f'<b>📡 クラウド監視</b><br>'
            f'現在: <b>{now_str}</b><br>'
            f'最終確認: {last_check}<br>'
        )
        if status.get("exists"):
            html += (
                f'第{status["latest_round"]}回 ({status["latest_date"]})<br>'
                f'データ更新: {status["updated_at"]}'
            )
        html += "<br><br><b>☁️ 安定動作モード</b><br>最新化は「今すぐ最新データを取得」"
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        return

    live = get_monitor_live_status()
    remaining = live["remaining"]
    last_check = live["last_check"]

    html = (
        f'<div class="sidebar-live">'
        f'<b>📡 リアルタイム監視</b><br>'
        f'現在: <b>{live["now"]}</b><br>'
        f'次回まで: <b>{remaining}</b>秒<br>'
        f'最終確認: {last_check}<br>'
    )
    if status.get("exists"):
        html += (
            f'第{status["latest_round"]}回 ({status["latest_date"]})<br>'
            f'データ更新: {status["updated_at"]}'
        )
    if live["draw_window"]:
        html += "<br>🔴 抽選日モード（30秒間隔）"
    try:
        from tools.security_monitor import get_security_status

        sec = get_security_status()
        html += (
            f'<br><br><b>🛡️ セキュリティ監視</b><br>'
            f'状態: {"稼働中" if sec["active"] else "停止"}<br>'
            f'接続: 全体 {sec["connections"]} / 外部 {sec["external_connections"]}<br>'
            f'（127.0.0.1は正常動作として除外）'
        )
    except Exception:
        pass
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _live_poll_interval() -> timedelta:
    """Cloud は1秒二重 fragment で落ちやすいので間隔を広げる"""
    return timedelta(seconds=10) if is_cloud_hosted() else timedelta(seconds=1)


def _show_live_monitor() -> None:
    if not hasattr(st, "fragment") or is_cloud_hosted():
        # Cloud: fragment の高頻度自動実行で「Oh no」になりやすい → 静的表示＋手動更新ボタン
        _render_live_monitor_bar()
        return
    try:

        @st.fragment(run_every=_live_poll_interval())
        def _frag() -> None:
            _render_live_monitor_bar()

        _frag()
    except Exception:
        _render_live_monitor_bar()


def _show_live_sidebar() -> None:
    if not hasattr(st, "fragment") or is_cloud_hosted():
        _render_live_sidebar_panel()
        return
    try:

        @st.fragment(run_every=_live_poll_interval())
        def _frag() -> None:
            _render_live_sidebar_panel()

        _frag()
    except Exception:
        _render_live_sidebar_panel()


def _html_bar_chart(data, *, title: str | None = None, height: int | None = None) -> None:
    """altair 非依存の棒グラフ（Streamlit Cloud の TypedDict TypeError 回避）"""
    try:
        if isinstance(data, pd.Series):
            df = data.to_frame(name=str(data.name or "値"))
        else:
            df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)

        if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()
        label_col = str(df.columns[0])
        value_cols = [c for c in df.columns if c != label_col]
        if not value_cols:
            st.dataframe(df, hide_index=True, use_container_width=True)
            return

        for c in value_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        max_v = float(df[value_cols].to_numpy().max()) if len(df) else 1.0
        if max_v <= 0:
            max_v = 1.0

        colors = ["#007aff", "#34c759", "#ff9500", "#af52de", "#ff3b30", "#5856d6"]
        parts: list[str] = []
        if title:
            parts.append(f'<div style="font-weight:600;margin:0 0 8px">{title}</div>')
        if len(value_cols) > 1:
            legend = "　".join(
                f'<span style="color:{colors[i % len(colors)]}">■</span> {c}'
                for i, c in enumerate(value_cols)
            )
            parts.append(f'<div style="font-size:0.8rem;color:#86868b;margin-bottom:8px">{legend}</div>')

        for _, row in df.iterrows():
            label = str(row[label_col])
            parts.append('<div style="margin:0 0 10px">')
            parts.append(
                f'<div style="font-size:0.8rem;font-variant-numeric:tabular-nums;margin-bottom:4px">{label}</div>'
            )
            for i, col in enumerate(value_cols):
                val = float(row[col])
                pct = max(0.0, min(100.0, (val / max_v) * 100.0))
                color = colors[i % len(colors)]
                parts.append(
                    '<div style="display:flex;align-items:center;gap:8px;margin:2px 0">'
                    f'<div style="flex:1;height:10px;background:rgba(116,116,128,0.12);border-radius:5px;overflow:hidden">'
                    f'<div style="width:{pct:.1f}%;height:100%;background:{color};border-radius:5px"></div></div>'
                    f'<div style="width:48px;text-align:right;font-size:0.75rem;color:#86868b;'
                    f'font-variant-numeric:tabular-nums">{val:g}</div></div>'
                )
            parts.append("</div>")

        style_h = f"min-height:{int(height)}px;" if height else ""
        st.markdown(
            f'<div style="{style_h}padding:4px 0">{"".join(parts)}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        try:
            st.dataframe(data, use_container_width=True)
        except Exception:
            st.caption("グラフを表示できませんでした")


def _html_line_chart(data) -> None:
    """altair 非依存の折れ線（SVG）"""
    try:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
        df = df.reset_index()
        x_col = df.columns[0]
        y_cols = [c for c in df.columns if c != x_col]
        for c in y_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        if not y_cols or len(df) == 0:
            st.dataframe(df, hide_index=True, use_container_width=True)
            return

        w, h, pad = 640, 220, 28
        max_v = float(df[y_cols].to_numpy().max())
        if max_v <= 0:
            max_v = 1.0
        n = len(df)
        colors = ["#007aff", "#34c759", "#ff9500", "#af52de", "#ff3b30", "#5856d6"]

        def xy(i: int, v: float) -> tuple[float, float]:
            x = pad + (0 if n == 1 else i / (n - 1) * (w - 2 * pad))
            y = h - pad - (float(v) / max_v) * (h - 2 * pad)
            return x, y

        polylines = []
        for ci, col in enumerate(y_cols):
            pts = " ".join(f"{xy(i, row[col])[0]:.1f},{xy(i, row[col])[1]:.1f}" for i, row in df.iterrows())
            polylines.append(
                f'<polyline fill="none" stroke="{colors[ci % len(colors)]}" '
                f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{pts}" />'
            )
        legend = "　".join(
            f'<span style="color:{colors[i % len(colors)]}">■</span> {c}' for i, c in enumerate(y_cols)
        )
        labels = "".join(
            f'<text x="{xy(i, 0)[0]:.1f}" y="{h - 6}" text-anchor="middle" '
            f'font-size="10" fill="#86868b">{str(row[x_col])[-9:]}</text>'
            for i, row in df.iterrows()
            if i == 0 or i == n - 1 or i == n // 2
        )
        svg = (
            f'<div style="font-size:0.8rem;color:#86868b;margin-bottom:6px">{legend}</div>'
            f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" '
            f'style="background:rgba(116,116,128,0.06);border-radius:12px">'
            f'{"".join(polylines)}{labels}</svg>'
        )
        st.markdown(svg, unsafe_allow_html=True)
    except Exception:
        try:
            st.dataframe(data.reset_index() if hasattr(data, "reset_index") else data, hide_index=True)
        except Exception:
            st.caption("推移グラフを表示できませんでした")


def _safe_bar_chart(data, **kwargs) -> None:
    """altair 互換問題でも必ず見える棒グラフを出す"""
    height = kwargs.get("height")
    try:
        st.bar_chart(data, **kwargs)
    except Exception:
        _html_bar_chart(data, height=height)


def render_balls(numbers: list[int]) -> None:
    balls = "".join(
        f'<span class="ball" style="animation-delay:{i * 2.78}ms">{n:02d}</span>'
        for i, n in enumerate(sorted(numbers))
    )
    st.markdown(f'<div class="ball-row">{balls}</div>', unsafe_allow_html=True)


def render_prediction_viz(analyzer: Loto6Analyzer, numbers: list[int], title: str = "予想番号の可視化") -> None:
    """予想番号の出現・出遅れ・時期別推移をグラフ表示"""
    try:
        nums = sorted({n for n in numbers if 1 <= n <= 43})
        if not nums:
            return
        profile = analyzer.number_profile(nums)
        rolling = analyzer.rolling_hit_series(nums, window=50, windows=12)

        st.markdown(f"#### 📈 {title}")
        st.caption("全体出現 / 直近50回 / 出遅れ / 時期別推移（参考可視化・当選保証なし）")

        df_prof = pd.DataFrame(
            [
                {
                    "番号": f"{r['number']:02d}",
                    "全体出現": r["all_count"],
                    "直近50回": r["recent50"],
                    "出遅れ(回)": r["gap"],
                }
                for r in profile
            ]
        ).set_index("番号")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**出現回数**")
            _safe_bar_chart(df_prof[["全体出現", "直近50回"]])
        with c2:
            st.markdown("**出遅れ（経過回数）**")
            _safe_bar_chart(df_prof[["出遅れ(回)"]])

        if rolling.get("labels") and rolling.get("series"):
            st.markdown("**時期別推移（50回×区間）**")
            trend_cols = {"区間": rolling["labels"]}
            for n in nums:
                trend_cols[f"{n:02d}"] = rolling["series"].get(n, [])
            n_lab = len(rolling["labels"])
            for k, v in list(trend_cols.items()):
                if k == "区間":
                    continue
                if len(v) < n_lab:
                    trend_cols[k] = list(v) + [0] * (n_lab - len(v))
                elif len(v) > n_lab:
                    trend_cols[k] = list(v)[:n_lab]
            df_trend = pd.DataFrame(trend_cols).set_index("区間")
            try:
                st.line_chart(df_trend)
            except Exception:
                _html_line_chart(df_trend)

        with st.expander("数値表", expanded=False):
            st.dataframe(df_prof.reset_index(), hide_index=True, use_container_width=True)
    except Exception as e:
        st.caption(f"グラフ表示を省略しました（{type(e).__name__}）")


def render_prediction(pred: dict) -> None:
    st.markdown(f"**{pred['name']}**")
    st.caption(pred["description"])
    render_balls(pred["numbers"])
    info = analyze_numbers(pred["numbers"])
    st.caption(
        f"奇{info['奇数']}/偶{info['偶数']} ｜ "
        f"小{info['小(1-22)']}/大{info['大(23-43)']} ｜ "
        f"合計{info['合計']} ｜ 連番{info['連番ペア']}組"
    )
    if pred.get("confidence") is not None:
        conf = pred["confidence"]
        label = pred.get("confidence_label", "")
        st.progress(min(conf / 100.0, 1.0), text=f"AI確信度 {conf}%（{label}）")
        bt = pred.get("backtest") or {}
        if bt.get("test_rounds"):
            st.caption(
                f"過去検証（抽選前データのみ {bt['test_rounds']}回）: "
                f"平均一致 {bt['mean']}個 ｜ 2個以上 {bt.get('hit2_rate', 0)}% ｜ "
                f"3個以上 {bt.get('hit3_rate', 0)}% ｜ "
                f"ランダム基準 {bt.get('random_baseline_mean', 0.837)}"
            )
        ti = pred.get("train_info") or {}
        if ti:
            st.caption(
                f"抽選前学習: {ti.get('trained_at', '未学習')} ｜ "
                f"検証{ti.get('test_rounds', '?')}回 ｜ "
                f"プール完全一致 {ti.get('pool_exact_in_train', 0)}回 ｜ "
                f"平均一致 {ti.get('main_mean_in_train', '-')}"
            )
        if pred.get("pool"):
            with st.expander(f"完全一致カバー用プール（{len(pred['pool'])}口）", expanded=True):
                for line in pred["pool"]:
                    mark = "★本命" if line["line_no"] == 1 else f"{line['line_no']}."
                    st.markdown(f"**{mark}** `{line['formatted']}`")
        if pred.get("reasons"):
            with st.expander("この番号を推す理由", expanded=False):
                for r in pred["reasons"]:
                    st.write(f"・{r}")
                if pred.get("top_candidates"):
                    tops = "  ".join(f"{n:02d}({s})" for n, s in pred["top_candidates"][:8])
                    st.caption(f"候補上位: {tops}")
        if pred.get("disclaimer"):
            st.caption(pred["disclaimer"])
    if pred.get("anchor_info"):
        st.caption(f"📌 {pred['anchor_info']}")
    if pred.get("unlikely_numbers"):
        elim = " ".join(f"{n:02d}" for n in pred["unlikely_numbers"])
        st.caption(f"今月出にくい数字（逆張り採用）: {elim}")
    if pred.get("overlap_latest") is not None:
        if pred["overlap_latest"]:
            ov = " ".join(f"{n:02d}" for n in pred["overlap_latest"])
            st.caption(f"最新ロト6・7重複: {ov}")
        if pred.get("loto7_latest"):
            l7 = " ".join(f"{n:02d}" for n in pred["loto7_latest"])
            st.caption(f"最新ロト7本数字: {l7}（第{pred.get('loto7_round', '?')}回）")
    if "eliminated" in pred and pred["eliminated"]:
        elim = " ".join(f"{n:02d}" for n in pred["eliminated"][:12])
        st.caption(f"除外候補: {elim}")


def main() -> None:
    _init_streamlit_ui()

    if not require_login():
        st.stop()

    if "security_started" not in st.session_state:
        try:
            if not is_cloud_hosted():
                import sys

                root = Path(__file__).resolve().parent
                if str(root) not in sys.path:
                    sys.path.insert(0, str(root))
                from tools.realtime_monitor import start_background_monitor
                from tools.security_monitor import start_security_monitor

                start_background_monitor()
                start_security_monitor()
            st.session_state.security_started = True
        except Exception:
            st.session_state.security_started = False

    render_hero(cloud=is_cloud_hosted())

    _show_live_monitor()

    with st.sidebar:
        st.header("⚙️ 設定")
        render_sidebar_account()
        _show_live_sidebar()

        if st.button("🔄 今すぐ最新データを取得", use_container_width=True):
            with st.spinner("取得中..."):
                result = realtime_watch_update(force=True)
                load_analyzer.clear()
                st.session_state["watch_result"] = result
            if result.updated:
                st.success(f"第{result.latest_round}回まで更新しました！")
            else:
                st.info("最新の状態です（変更なし）")
            st.rerun()

        use_seed = st.checkbox("乱数シードを固定", value=False)
        seed = st.number_input("シード値", min_value=0, value=42, disabled=not use_seed)
        if not use_seed:
            seed = random.randint(0, 999999)

        st.divider()
        st.info(
            "宝くじは完全なランダム抽選です。\n\n"
            "このツールは参考情報であり、当選を保証するものではありません。"
        )

        upcoming = next_draw_dates(3)
        if upcoming:
            st.markdown("### 📅 次回抽選")
            for d in upcoming:
                st.caption(format_draw_date(d))

        if is_cloud_hosted():
            st.divider()
            st.markdown("### ☁️ 常時アクセス")
            st.success("このページはクラウドで24時間稼働しています")
            st.caption("URLをブックマークすれば、いつでもスマホから使えます")
        else:
            lan_ip = _get_lan_ip()
            if lan_ip:
                st.divider()
                st.markdown("### 📱 他の端末からアクセス")
                st.code(f"http://{lan_ip}:8501", language=None)
                st.caption("同じWi-Fiに接続したスマホ・タブレットのブラウザで開いてください")
                st.caption("PCオフでも使う → 「常時アクセス設定.bat」を実行")

    try:
        analyzer = load_analyzer()
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        st.stop()

    latest = analyzer.latest
    upcoming = next_draw_dates(1)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("分析回数", f"{analyzer.total_rounds} 回")
    with col2:
        if latest:
            st.metric("最新回", f"第 {latest.round_num} 回")
    with col3:
        if latest:
            st.metric("抽選日", latest.date)
    with col4:
        if upcoming:
            st.metric("次回抽選", format_draw_date(upcoming[0]))

    if latest:
        st.subheader("📋 最新当選番号")
        render_balls(list(latest.numbers))
        st.caption(f"ボーナス数字: **{latest.bonus:02d}**")

    # 今週のおすすめ（クラウド学習ヒント＋複合スコア＋カバー行）
    with st.expander("⭐ 今週のおすすめパック（クラウド学習連動）", expanded=True):
        tip = None
        tip_path = Path(__file__).resolve().parent / "data" / "ai_next_tip.json"
        if tip_path.exists():
            try:
                tip = json.loads(tip_path.read_text(encoding="utf-8"))
            except Exception:
                tip = None

        if tip and tip.get("numbers"):
            st.markdown(
                f"**AI検証済み本命**｜確信度 {tip.get('confidence', '-')}%"
                f"（{tip.get('confidence_label', '')}）｜更新 {tip.get('generated_at', '-')}"
            )
            render_balls(list(tip["numbers"]))
            st.code(tip.get("formatted") or " ".join(f"{n:02d}" for n in tip["numbers"]), language=None)
            pool = tip.get("pool") or []
            if len(pool) > 1:
                st.caption("カバー行（本命周辺）")
                for line in pool[1:5]:
                    st.write(
                        f"{'★' if line.get('line_no') == 1 else str(line.get('line_no', '')) + '.'} "
                        f"{line.get('formatted', '')}"
                    )
            render_prediction_viz(analyzer, list(tip["numbers"]), title="AI本命の推移")
        else:
            st.info("クラウド学習の本命がまだありません。GitHub Actions の自動更新後に表示されます。")

        if st.button("おすすめパックを今すぐ生成（複合＋直近＋出遅れ）", use_container_width=True):
            try:
                st.session_state["weekly_pack"] = [
                    strategy_composite(analyzer, seed=seed),
                    strategy_recent_trend(analyzer, seed=seed + 7),
                    strategy_overdue(analyzer, seed=seed + 13),
                ]
            except Exception as e:
                st.warning(f"パック生成に失敗しました: {type(e).__name__}")

        if st.session_state.get("weekly_pack"):
            st.markdown("#### 生成パック")
            for pred in st.session_state["weekly_pack"]:
                st.markdown(f"**{pred.get('name', '予想')}**")
                render_balls(list(pred["numbers"]))
                st.code(pred.get("formatted", ""), language=None)

        st.caption(
            "スマホだけで使う場合は公開サイト "
            "https://coldcandy.github.io/loto6-predictor/ も利用できます。"
        )

    st.divider()

    tab_predict, tab_verify, tab_check, tab_stats, tab_history = st.tabs(
        ["🎯 予想番号", "🔬 抽選前検証", "✅ 当選チェック", "📊 統計グラフ", "📚 当選データ"]
    )

    with tab_predict:
        st.subheader("予想法を選んでボタンを押してください")

        now_month = monthly_analysis_summary(analyzer.draws)
        with st.expander(f"📅 {now_month['month_label']}の分析（起点・出にくい数字・ロト7重複）", expanded=True):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                st.markdown("**月初回抽選（起点）**")
                if now_month["anchor"]:
                    render_balls(now_month["anchor_numbers"])
                    st.caption(
                        f"第{now_month['anchor_round']}回 {now_month['anchor_date']} "
                        f"（{now_month['years_analyzed']}年分の同月データを分析）"
                    )
                else:
                    st.caption("今月の起点データなし")
            with mc2:
                st.markdown("**今月出にくい数字 TOP8**")
                unlikely_text = " ".join(
                    f"{n:02d}" for n, _c, _r in now_month["unlikely"][:8]
                )
                st.code(unlikely_text, language=None)
                st.caption("月次逆張り法で逆に予想へ組み込みます")
            with mc3:
                st.markdown("**ロト6・7重複傾向**")
                l7 = load_loto7_draws()
                if l7:
                    l6_set = set(analyzer.latest.numbers) if analyzer.latest else set()
                    l7_set = set(l7[-1].numbers)
                    overlap = sorted(l6_set & l7_set)
                    st.caption(f"最新ロト7: 第{l7[-1].round_num}回")
                    if overlap:
                        st.code(" ".join(f"{n:02d}" for n in overlap), language=None)
                    else:
                        st.caption("最新回の直接重複なし（歴史傾向で分析）")
                else:
                    st.caption("ロト7データ取得中...")

            st.markdown("**今月の出やすい数字 TOP10**")
            top_m = "  ".join(f"{n:02d}({c}回)" for n, c in now_month["top_monthly"][:10])
            st.caption(top_m)

            special_cols = st.columns(3)
            with special_cols[0]:
                if st.button("📅 月次起点法", use_container_width=True, type="primary"):
                    st.session_state.selected_key = "月次起点法"
                    st.session_state.selected = strategy_monthly_anchor(analyzer, seed=seed)
                    st.session_state.results = None
            with special_cols[1]:
                if st.button("🔄 月次逆張り法", use_container_width=True, type="primary"):
                    st.session_state.selected_key = "月次逆張り法"
                    st.session_state.selected = strategy_monthly_inverse(analyzer, seed=seed)
                    st.session_state.results = None
            with special_cols[2]:
                if st.button("🎱 ロト6・7重複法", use_container_width=True, type="primary"):
                    st.session_state.selected_key = "ロト6・7重複法"
                    st.session_state.selected = strategy_loto67_overlap(analyzer, seed=seed)
                    st.session_state.results = None

        st.divider()

        if "results" not in st.session_state:
            st.session_state.results = None
        if "selected" not in st.session_state:
            st.session_state.selected = None
        if "selected_key" not in st.session_state:
            st.session_state.selected_key = None

        btn_cols = st.columns(4)
        strategy_names = list(STRATEGY_BY_NAME.keys())

        for i, name in enumerate(strategy_names):
            with btn_cols[i % 4]:
                if st.button(name, key=f"btn_{i}", use_container_width=True):
                    st.session_state.selected_key = name
                    st.session_state.selected = STRATEGY_BY_NAME[name](analyzer, seed=seed)
                    st.session_state.results = None

        st.markdown("")
        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button("🛡️ AI検証済み本命（抽選前学習）", type="primary", use_container_width=True):
                with st.spinner("学習済みモデルで本命＋プールを生成中..."):
                    st.session_state.selected_key = "AI検証済み本命（抽選前学習）"
                    st.session_state.selected = strategy_ai_verified(analyzer, seed=seed)
                    st.session_state.results = None
                    st.session_state.cover_lines = None
        with action_cols[1]:
            if st.button("🤖 AI確信度おすすめ", use_container_width=True):
                with st.spinner("過去データで一致率を最大化中..."):
                    st.session_state.selected_key = "AI確信度おすすめ"
                    st.session_state.selected = strategy_ai_confidence(analyzer, seed=seed)
                    st.session_state.results = None
                    from loto6_predictor.ai_recommender import generate_near_miss_lines

                    st.session_state.cover_lines = generate_near_miss_lines(
                        analyzer, seed=seed, count=4, main=st.session_state.selected
                    )
        with action_cols[2]:
            if st.button("📋 既存方式をすべて表示", use_container_width=True):
                with st.spinner("既存の全手法を計算中..."):
                    st.session_state.results = generate_all_predictions(analyzer, seed=seed)
                    st.session_state.selected = None
                    st.session_state.selected_key = None

        if st.button("🔀 番号を再生成", use_container_width=True):
            new_seed = random.randint(0, 999999)
            if st.session_state.selected_key:
                with st.spinner("再計算中..."):
                    st.session_state.selected = STRATEGY_BY_NAME[st.session_state.selected_key](
                        analyzer, seed=new_seed
                    )
                    if st.session_state.selected_key == "AI確信度おすすめ":
                        from loto6_predictor.ai_recommender import generate_near_miss_lines

                        st.session_state.cover_lines = generate_near_miss_lines(
                            analyzer, seed=new_seed, count=4, main=st.session_state.selected
                        )
            elif st.session_state.results:
                st.session_state.results = generate_all_predictions(analyzer, seed=new_seed)

        st.divider()

        if st.session_state.selected:
            st.markdown("### 🎯 予想結果")
            with st.container(border=True):
                render_prediction(st.session_state.selected)
            nums = st.session_state.selected["numbers"]
            st.success(f"コピー用: {' '.join(f'{n:02d}' for n in sorted(nums))}")
            render_prediction_viz(
                analyzer,
                list(nums),
                title=f"{st.session_state.selected.get('name', '予想')} の推移",
            )

        if st.session_state.get("cover_lines") and st.session_state.selected_key == "AI確信度おすすめ":
            st.markdown("#### 🎯 準一致カバー（本命＋差し替え）")
            st.caption("完全一致は極めて稀なため、本命周辺でほぼ一致を狙いやすくした複数行です")
            for line in st.session_state.cover_lines[1:]:
                st.markdown(f"**{line.get('name', '')}:** `{line['formatted']}`")

        if st.session_state.results:
            st.markdown("### 📋 全手法の予想結果")
            for pred in st.session_state.results:
                with st.container(border=True):
                    render_prediction(pred)
            render_prediction_viz(
                analyzer,
                list(st.session_state.results[0]["numbers"]),
                title=f"{st.session_state.results[0].get('name', '先頭手法')} の推移",
            )

        if not st.session_state.selected and not st.session_state.results:
            st.info("👆 上のボタンを押すと予想番号が表示されます")

        st.divider()
        st.markdown("### 🎲 追加機能")

        extra1, extra2, extra3 = st.columns(3)
        with extra1:
            if st.button("🎰 クイックピック", use_container_width=True):
                st.session_state.selected = strategy_quick_pick(analyzer, seed=seed)
                st.session_state.selected_key = "クイックピック"
                st.session_state.results = None
        with extra2:
            st.caption("一括生成数")
            multi_count = st.selectbox("生成数", [3, 5, 10], index=1, key="multi_count", label_visibility="collapsed")
        with extra3:
            if st.button(f"📦 {multi_count}パターン一括生成", use_container_width=True):
                with st.spinner("AI本命＋カバー行を生成中..."):
                    from loto6_predictor.ai_recommender import generate_near_miss_lines

                    st.session_state.multi_lines = generate_near_miss_lines(
                        analyzer, seed=seed, count=multi_count
                    )

        if st.session_state.get("multi_lines"):
            st.markdown("#### 📦 一括生成結果")
            for line in st.session_state.multi_lines:
                st.markdown(
                    f"**{line['line_no']}.** `{line['formatted']}` "
                    f"（奇{analyze_numbers(line['numbers'])['奇数']}/偶{analyze_numbers(line['numbers'])['偶数']}）"
                )
            all_text = "\n".join(l["formatted"] for l in st.session_state.multi_lines)
            st.download_button("📥 一括コピー用テキスト", all_text, "loto6_lines.txt", use_container_width=True)

        st.markdown("#### ⭐ お気に入り保存")
        fav_col1, fav_col2 = st.columns([3, 1])
        with fav_col1:
            fav_label = st.text_input("メモ（任意）", placeholder="例: 今週の本命", key="fav_label")
        with fav_col2:
            save_disabled = not st.session_state.get("selected")
            if st.button("保存", use_container_width=True, disabled=save_disabled):
                nums = st.session_state.selected["numbers"]
                save_favorite(nums, fav_label, st.session_state.selected.get("name", ""))
                st.success("保存しました！")
                st.rerun()

        favs = load_favorites()
        if favs:
            for i, fav in enumerate(favs[:5]):
                fc1, fc2 = st.columns([4, 1])
                with fc1:
                    st.caption(f"{fav['label']} ({fav['saved_at']}) — `{fav['formatted']}`")
                with fc2:
                    if st.button("削除", key=f"del_fav_{i}"):
                        delete_favorite(i)
                        st.rerun()

    with tab_verify:
        _render_verify_tab(analyzer)

    with tab_check:
        _render_check_tab(analyzer)

    with tab_stats:
        st.subheader("📊 数字の出現傾向")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("**全体の出現回数 TOP20**")
            freq = analyzer.frequency()
            df_all = pd.DataFrame(
                [{"番号": n, "出現回数": freq[n]} for n in range(1, 44)]
            ).sort_values("出現回数", ascending=False).head(20)
            _safe_bar_chart(df_all.set_index("番号"))

        with chart_col2:
            st.markdown("**直近50回の出現回数 TOP20**")
            recent = analyzer.recent_frequency(50)
            df_recent = pd.DataFrame(
                [{"番号": n, "出現回数": recent[n]} for n in range(1, 44)]
            ).sort_values("出現回数", ascending=False).head(20)
            _safe_bar_chart(df_recent.set_index("番号"))

        st.markdown("**全番号の出現回数ヒートマップ**")
        df_heat = pd.DataFrame(
            [{"番号": f"{n:02d}", "出現回数": freq[n]} for n in range(1, 44)]
        )
        _safe_bar_chart(df_heat.set_index("番号"), height=300)

        stat_col1, stat_col2 = st.columns(2)
        with stat_col1:
            st.markdown("**出遅れ番号 TOP15**")
            overdue = analyzer.overdue_numbers(15)
            df_overdue = pd.DataFrame(overdue, columns=["番号", "経過回数"])
            st.dataframe(df_overdue, hide_index=True, use_container_width=True)

        with stat_col2:
            st.markdown("**奇数個数の分布 (%)**")
            odd_dist = analyzer.odd_even_distribution()
            df_odd = pd.DataFrame(
                [{"パターン": k, "割合": v} for k, v in odd_dist.items()]
            )
            _safe_bar_chart(df_odd.set_index("パターン"))

        sum_stats = analyzer.sum_range_stats()
        st.markdown(
            f"**本数字合計の統計:** 平均 {sum_stats['平均']:.1f} / "
            f"最小 {sum_stats['最小']:.0f} / 最大 {sum_stats['最大']:.0f}"
        )

        st.divider()
        st.markdown("### 📈 番号の時期別推移（直近ホット）")
        hot = [n for n, _ in analyzer.top_numbers(6, last_n=50)]
        render_prediction_viz(analyzer, hot, title="直近ホット TOP6 の推移")

        st.divider()
        st.markdown("### 🔬 予想法バックテスト（参考）")
        st.caption("各手法で過去100回をシミュレーションした「3個以上一致」の回数です")
        bt = backtest_strategy(analyzer, test_rounds=100)
        if bt:
            df_bt = pd.DataFrame(bt)
            df_bt = df_bt.rename(columns={
                "strategy": "手法",
                "hit2_or_more": "2個以上",
                "hit3_or_more": "3個以上",
                "hit4_or_more": "4個以上",
                "rate3": "3個以上率(%)",
            })
            st.dataframe(df_bt, hide_index=True, use_container_width=True)
        else:
            st.info("バックテストに十分なデータがありません。")

    with tab_history:
        hist_l6, hist_l7 = st.tabs(["🎱 ロト6", "🎰 ロト7"])
        with hist_l6:
            _render_history_tab(analyzer)
        with hist_l7:
            _render_loto7_history_tab()


def _draw_to_row(d) -> dict:
    return {
        "回": d.round_num,
        "日付": d.date,
        "第1": f"{d.numbers[0]:02d}",
        "第2": f"{d.numbers[1]:02d}",
        "第3": f"{d.numbers[2]:02d}",
        "第4": f"{d.numbers[3]:02d}",
        "第5": f"{d.numbers[4]:02d}",
        "第6": f"{d.numbers[5]:02d}",
        "ボーナス": f"{d.bonus:02d}",
        "合計": sum(d.numbers),
    }


def _render_history_tab(analyzer: Loto6Analyzer) -> None:
    from loto6_predictor.data import DEFAULT_DATA_PATH, get_data_status

    st.subheader("📚 過去の当選番号データ")

    status = get_data_status()
    info1, info2, info3 = st.columns(3)
    with info1:
        st.metric("保存データ", f"{analyzer.total_rounds} 回分")
    with info2:
        latest = analyzer.latest
        st.metric("最新", f"第 {latest.round_num} 回" if latest else "-")
    with info3:
        st.metric("ファイル更新", status.get("updated_at", "-"))

    st.caption(f"保存場所: `{DEFAULT_DATA_PATH}` ｜ 取得元: loto6.thekyo.jp")

    st.divider()

    filter1, filter2, filter3 = st.columns(3)
    with filter1:
        sort_order = st.selectbox("表示順", ["新しい順", "古い順"], key="hist_sort")
    with filter2:
        show_count = st.selectbox("表示件数", [20, 50, 100, 200, 500], index=1, key="hist_count")
    with filter3:
        search_nums = st.multiselect(
            "含む数字で絞込",
            options=list(range(1, 44)),
            format_func=lambda x: f"{x:02d}",
            key="hist_nums",
        )

    max_round = analyzer.total_rounds
    round_from, round_to = st.slider(
        "回数の範囲",
        min_value=1,
        max_value=max_round,
        value=(max(1, max_round - 99), max_round),
        key="hist_range",
    )

    draws = list(analyzer.draws)
    filtered = [d for d in draws if round_from <= d.round_num <= round_to]
    if search_nums:
        nums_set = set(search_nums)
        filtered = [
            d for d in filtered
            if nums_set & set(d.numbers) or d.bonus in nums_set
        ]

    filtered.sort(key=lambda d: d.round_num, reverse=(sort_order == "新しい順"))
    total_filtered = len(filtered)
    filtered = filtered[:show_count]

    st.markdown(f"**表示: {len(filtered)} 件**（条件に一致: {total_filtered} 件 / 全 {analyzer.total_rounds} 件）")

    if filtered:
        df = pd.DataFrame([_draw_to_row(d) for d in filtered])
        st.dataframe(df, hide_index=True, use_container_width=True, height=400)

        if len(filtered) == 1:
            d = filtered[0]
            st.markdown("**当選番号**")
            render_balls(list(d.numbers))
            st.caption(f"ボーナス: **{d.bonus:02d}**")

        csv_text = "回,日付,第1,第2,第3,第4,第5,第6,ボーナス,合計\n"
        csv_text += "\n".join(
            f"{d.round_num},{d.date},"
            + ",".join(f"{n:02d}" for n in d.numbers)
            + f",{d.bonus:02d},{sum(d.numbers)}"
            for d in filtered
        )
        st.download_button(
            "📥 表示中のデータをCSVダウンロード",
            data=csv_text.encode("utf-8-sig"),
            file_name="loto6_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("条件に一致するデータがありません。")


def _draw_to_row_l7(d) -> dict:
    return {
        "回": d.round_num,
        "日付": d.date,
        "第1": f"{d.numbers[0]:02d}",
        "第2": f"{d.numbers[1]:02d}",
        "第3": f"{d.numbers[2]:02d}",
        "第4": f"{d.numbers[3]:02d}",
        "第5": f"{d.numbers[4]:02d}",
        "第6": f"{d.numbers[5]:02d}",
        "第7": f"{d.numbers[6]:02d}",
        "B1": f"{d.bonus[0]:02d}",
        "B2": f"{d.bonus[1]:02d}",
        "合計": sum(d.numbers),
    }


def _render_loto7_history_tab() -> None:
    st.subheader("📚 ロト7 過去の当選番号")

    draws = load_loto7_draws()
    if not draws:
        st.error("ロト7データを取得できませんでした。ネットワーク接続を確認してください。")
        if st.button("🔄 再取得", key="l7_retry"):
            try:
                from loto6_predictor.loto7_data import download_csv
                download_csv()
                st.rerun()
            except Exception as e:
                st.error(f"取得失敗: {e}")
        return

    status = get_loto7_data_status()
    latest = draws[-1]

    info1, info2, info3 = st.columns(3)
    with info1:
        st.metric("保存データ", f"{len(draws)} 回分")
    with info2:
        st.metric("最新", f"第 {latest.round_num} 回")
    with info3:
        st.metric("ファイル更新", status.get("updated_at", "-"))

    st.caption(f"保存場所: `{LOTO7_DATA_PATH}` ｜ 取得元: loto7.thekyo.jp")

    st.markdown("#### 📋 最新当選番号")
    render_balls(list(latest.numbers))
    st.caption(
        f"ボーナス数字: **{latest.bonus[0]:02d}** / **{latest.bonus[1]:02d}** ｜ "
        f"抽選日: {latest.date}"
    )

    st.divider()

    filter1, filter2, filter3 = st.columns(3)
    with filter1:
        sort_order = st.selectbox("表示順", ["新しい順", "古い順"], key="l7_hist_sort")
    with filter2:
        show_count = st.selectbox("表示件数", [20, 50, 100, 200, 500], index=1, key="l7_hist_count")
    with filter3:
        search_nums = st.multiselect(
            "含む数字で絞込",
            options=list(range(1, 38)),
            format_func=lambda x: f"{x:02d}",
            key="l7_hist_nums",
        )

    max_round = latest.round_num
    round_from, round_to = st.slider(
        "回数の範囲",
        min_value=1,
        max_value=max_round,
        value=(max(1, max_round - 99), max_round),
        key="l7_hist_range",
    )

    filtered = [d for d in draws if round_from <= d.round_num <= round_to]
    if search_nums:
        nums_set = set(search_nums)
        filtered = [
            d for d in filtered
            if nums_set & set(d.numbers) or nums_set & set(d.bonus)
        ]

    filtered.sort(key=lambda d: d.round_num, reverse=(sort_order == "新しい順"))
    total_filtered = len(filtered)
    filtered = filtered[:show_count]

    st.markdown(
        f"**表示: {len(filtered)} 件**（条件に一致: {total_filtered} 件 / 全 {len(draws)} 件）"
    )

    if filtered:
        df = pd.DataFrame([_draw_to_row_l7(d) for d in filtered])
        st.dataframe(df, hide_index=True, use_container_width=True, height=400)

        if len(filtered) == 1:
            d = filtered[0]
            st.markdown("**当選番号**")
            render_balls(list(d.numbers))
            st.caption(f"ボーナス: **{d.bonus[0]:02d}** / **{d.bonus[1]:02d}**")

        csv_text = "回,日付,第1,第2,第3,第4,第5,第6,第7,B1,B2,合計\n"
        csv_text += "\n".join(
            f"{d.round_num},{d.date},"
            + ",".join(f"{n:02d}" for n in d.numbers)
            + f",{d.bonus[0]:02d},{d.bonus[1]:02d},{sum(d.numbers)}"
            for d in filtered
        )
        st.download_button(
            "📥 表示中のデータをCSVダウンロード",
            data=csv_text.encode("utf-8-sig"),
            file_name="loto7_history.csv",
            mime="text/csv",
            use_container_width=True,
            key="l7_csv_dl",
        )
    else:
        st.info("条件に一致するデータがありません。")


def _render_verify_tab(analyzer: Loto6Analyzer) -> None:
    """抽選前想定の検証・反復学習UI（既存方式は維持）"""
    from loto6_predictor.walkforward_trainer import (
        compare_all_strategies_walkforward,
        generate_verified_prediction,
        iterative_train,
        load_model,
    )

    st.subheader("🔬 抽選前検証（Walk-Forward）")
    st.markdown(
        """
**やり方:** 過去の各回について「その回の当選番号が出る前」のデータだけを使い予想し、
実際の当選と照合します。完全一致・ほぼ一致が増えるまでパラメータを反復学習します。

既存の予想法（複合スコア・ホット・月次など）はそのまま残しています。
"""
    )
    st.warning(
        "ロト6はランダム抽選です。過去での完全一致再現を目標に学習しますが、"
        "未来の当選保証ではありません。完全一致を狙う場合はプール複数口が有効です。"
    )

    model = load_model()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("学習モデル", "あり" if model else "未学習")
    with c2:
        if model and model.get("result"):
            st.metric("学習時プール完全一致", f"{model['result'].get('pool_exact', 0)} 回")
        else:
            st.metric("学習時プール完全一致", "—")
    with c3:
        if model:
            st.metric("学習日時", model.get("trained_at", "—"))
        else:
            st.metric("学習日時", "—")

    st.markdown("### 1️⃣ 反復学習（完全一致を目指す）")
    g1, g2, g3 = st.columns(3)
    with g1:
        test_rounds = st.selectbox("検証回数", [40, 60, 80, 100], index=1, key="vf_rounds")
    with g2:
        generations = st.selectbox("学習世代数", [8, 12, 20, 30], index=1, key="vf_gens")
    with g3:
        target_exact = st.selectbox("目標・歴史的完全一致回数", [1, 2, 3], index=0, key="vf_target")

    if st.button("🚀 抽選前検証で学習開始（時間がかかります）", type="primary", use_container_width=True):
        progress = st.progress(0.0, text="学習準備中...")
        status = st.empty()

        def _cb(gen, total, best):
            progress.progress(gen / total, text=f"世代 {gen}/{total}")
            status.caption(
                f"暫定: 完全一致再現 {best.get('pool_exact', 0)} ｜ "
                f"上位カバー平均 {best.get('cover_mean_in_topk', '-')} ｜ "
                f"平均一致 {best.get('main_mean', '-')} ｜ "
                f"4個一致 {best.get('main_hit4', 0)}"
            )

        with st.spinner("抽選前データだけで反復学習中..."):
            payload = iterative_train(
                analyzer.draws,
                test_rounds=test_rounds,
                generations=generations,
                target_exact=target_exact,
                progress_cb=_cb,
            )
        progress.progress(1.0, text="完了")
        res = payload["result"]
        st.success(
            f"学習完了: プール完全一致（上位包含） {res.get('pool_exact', 0)}回 / "
            f"本命平均一致 {res.get('main_mean')} / "
            f"世代数 {payload.get('generations_run')}"
        )
        if res.get("top_k_containment"):
            st.caption(
                "上位Kに当選6個すべてが入った回数: "
                + " ｜ ".join(f"K={k}: {v}回" for k, v in res["top_k_containment"].items())
            )
        if res.get("exact_cases"):
            st.markdown("#### 🎉 歴史的に完全一致したケース")
            for ex in res["exact_cases"]:
                st.write(
                    f"第{ex['round']}回（{ex['date']}） "
                    f"予想 `{' '.join(f'{n:02d}' for n in ex['predicted'])}` = "
                    f"当選 `{' '.join(f'{n:02d}' for n in ex['actual'])}`"
                )
        if res.get("near_cases"):
            st.markdown("#### ほぼ一致（4個以上）")
            for nc in res["near_cases"][-8:]:
                st.caption(
                    f"第{nc['round']}回 {nc['hits']}個一致 — "
                    f"`{' '.join(f'{n:02d}' for n in nc['predicted'])}` vs "
                    f"`{' '.join(f'{n:02d}' for n in nc['actual'])}`"
                )
        if payload.get("history"):
            st.dataframe(pd.DataFrame(payload["history"]), hide_index=True, use_container_width=True)
        st.rerun()

    st.divider()
    st.markdown("### 2️⃣ 既存方式 vs 新方式の抽選前比較")
    if st.button("📊 同じ条件で既存・新方式を比較", use_container_width=True):
        with st.spinner("既存方式も含めて抽選前検証中..."):
            rows = compare_all_strategies_walkforward(analyzer.draws, test_rounds=60)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("比較に十分なデータがありません。")

    st.divider()
    st.markdown("### 3️⃣ 学習済みモデルで今すぐ本命を出す")
    if st.button("🛡️ 検証済み本命＋プールを生成", use_container_width=True):
        pred = generate_verified_prediction(analyzer, seed=random.randint(0, 999999))
        st.session_state.selected = pred
        st.session_state.selected_key = "AI検証済み本命（抽選前学習）"
        render_prediction(pred)
        st.success(f"コピー用本命: {pred['formatted']}")

    if model and model.get("result", {}).get("details_tail"):
        with st.expander("直近の抽選前検証明細（末尾）"):
            st.dataframe(pd.DataFrame(model["result"]["details_tail"]), hide_index=True)


def _render_check_tab(analyzer: Loto6Analyzer) -> None:
    st.subheader("✅ 当選チェック")
    st.caption("購入した番号が当たっているか確認できます")

    favs = load_favorites()
    if favs:
        fav_options = {f"{f['label']} — {f['formatted']}": f["numbers"] for f in favs}
        picked_fav = st.selectbox("お気に入りから読み込み", ["（選択しない）"] + list(fav_options.keys()))
        if picked_fav != "（選択しない）":
            st.session_state.check_nums = fav_options[picked_fav]

    picked = st.multiselect(
        "あなたの番号（6個選んでください）",
        options=list(range(1, 44)),
        format_func=lambda x: f"{x:02d}",
        max_selections=6,
        key="check_nums",
    )

    if len(picked) == 6:
        st.markdown("**選択中:** " + " ".join(f"{n:02d}" for n in sorted(picked)))
        info = analyze_numbers(picked)
        st.caption(
            f"奇数{info['奇数']} / 偶数{info['偶数']} ｜ "
            f"合計{info['合計']} ｜ 連番{info['連番ペア']}組"
        )

    check_mode = st.radio("照合対象", ["最新回", "回数を指定"], horizontal=True, key="check_mode")

    target_draw = analyzer.latest
    if check_mode == "回数を指定":
        round_num = st.number_input(
            "回数",
            min_value=1,
            max_value=analyzer.total_rounds,
            value=analyzer.total_rounds,
            key="check_round",
        )
        target_draw = next((d for d in analyzer.draws if d.round_num == round_num), None)

    if len(picked) == 6 and target_draw:
        result = check_winning(picked, target_draw)
        if not result["valid"]:
            st.error(result["error"])
        else:
            st.markdown(f"#### 第{result['draw_round']}回（{result['draw_date']}）との照合")
            st.markdown("**当選番号:** " + " ".join(f"{n:02d}" for n in result["draw_numbers"]))
            st.caption(f"ボーナス: {result['draw_bonus']:02d}")

            if result["tier"]:
                st.success(f"🎉 **{result['prize_name']}** — {result['hits']}個一致")
            else:
                st.warning(f"はずれ — {result['hits']}個一致（ボーナス: {'あり' if result['bonus_hit'] else 'なし'}）")

            if result["matched_numbers"]:
                st.info("一致: " + " ".join(f"{n:02d}" for n in result["matched_numbers"]))

            st.divider()
            st.markdown("#### 📈 過去100回シミュレーション")
            sim = backtest_numbers(picked, analyzer.draws, last_n=100)
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("3等以上", f"{sim['hit3_or_more']} 回")
            with sc2:
                st.metric("3個一致", f"{sim['results'][3]} 回")
            with sc3:
                st.metric("4個一致", f"{sim['results'][4]} 回")
            with sc4:
                st.metric("5個以上", f"{sim['results'][5] + sim['results']['5+b'] + sim['results'][6]} 回")
            if sim["best"]:
                b = sim["best"]
                st.caption(f"ベスト: 第{b['round']}回（{b['date']}）— {b['hits']}個一致")
    elif len(picked) != 6:
        st.info("6個の番号を選んでください。")


if __name__ == "__main__":
    main()
