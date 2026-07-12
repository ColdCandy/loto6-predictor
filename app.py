"""Streamlit GUI - ロト6予想番号"""

from __future__ import annotations

import random

from datetime import timedelta

import pandas as pd
import streamlit as st

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
    strategy_composite,
    strategy_quick_pick,
)


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

st.set_page_config(
    page_title="ロト6 予想番号",
    page_icon="🎱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .ball {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 52px;
        height: 52px;
        margin: 4px;
        border-radius: 50%;
        background: linear-gradient(145deg, #ff6b6b, #c92a2a);
        color: white;
        font-size: 20px;
        font-weight: bold;
        box-shadow: 0 4px 8px rgba(0,0,0,0.25);
    }
    .ball-row { text-align: center; padding: 12px 0; }
    .result-box {
        background: #f8f9fa;
        border: 2px solid #dee2e6;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .main-title { text-align: center; color: #c92a2a; }
    .live-status {
        background: linear-gradient(90deg, #e6fcf5, #d3f9d8);
        border: 1px solid #8ce99a;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0 16px 0;
        font-size: 0.95rem;
        color: #2b8a3e;
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .pulse-dot {
        width: 10px;
        height: 10px;
        background: #40c057;
        border-radius: 50%;
        animation: pulse 1.5s ease-in-out infinite;
        flex-shrink: 0;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.3); }
    }
    .live-status b { color: #087f5b; }
    .sidebar-live {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=30)
def load_analyzer() -> Loto6Analyzer:
    draws = load_draws(auto_refresh=False)
    return Loto6Analyzer(draws)


@st.fragment(run_every=timedelta(seconds=1))
def _live_monitor_bar() -> None:
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


@st.fragment(run_every=timedelta(seconds=1))
def _live_sidebar_panel() -> None:
    live = get_monitor_live_status()
    status = get_data_status()
    html = (
        f'<div class="sidebar-live">'
        f'<b>📡 リアルタイム監視</b><br>'
        f'現在: <b>{live["now"]}</b><br>'
        f'次回まで: <b>{live["remaining"]}</b>秒<br>'
        f'最終確認: {live["last_check"]}<br>'
    )
    if status.get("exists"):
        html += (
            f'第{status["latest_round"]}回 ({status["latest_date"]})<br>'
            f'データ更新: {status["updated_at"]}'
        )
    if live["draw_window"]:
        html += "<br>🔴 抽選日モード（30秒間隔）"
    if not is_cloud_hosted():
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
    else:
        html += "<br><br><b>☁️ クラウド常時稼働</b><br>PCの電源が切れていても利用できます"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_balls(numbers: list[int]) -> None:
    balls = "".join(f'<span class="ball">{n:02d}</span>' for n in sorted(numbers))
    st.markdown(f'<div class="ball-row">{balls}</div>', unsafe_allow_html=True)


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
    if "eliminated" in pred and pred["eliminated"]:
        elim = " ".join(f"{n:02d}" for n in pred["eliminated"][:12])
        st.caption(f"除外候補: {elim}")


def main() -> None:
    if "security_started" not in st.session_state:
        try:
            import sys
            from pathlib import Path

            root = Path(__file__).resolve().parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from tools.realtime_monitor import start_background_monitor

            start_background_monitor()
            if not is_cloud_hosted():
                from tools.security_monitor import start_security_monitor

                start_security_monitor()
            st.session_state.security_started = True
        except Exception:
            st.session_state.security_started = False

    st.markdown('<h1 class="main-title">🎱 ロト6 予想番号ジェネレーター</h1>', unsafe_allow_html=True)
    if is_cloud_hosted():
        st.caption("☁️ クラウド常時稼働 — PCの電源が切れていてもアクセスできます")
    else:
        st.caption("過去の当選データをリアルタイム監視して予想番号を表示します")

    _live_monitor_bar()

    with st.sidebar:
        st.header("⚙️ 設定")
        _live_sidebar_panel()

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

    st.divider()

    tab_predict, tab_check, tab_stats, tab_history = st.tabs(
        ["🎯 予想番号", "✅ 当選チェック", "📊 統計グラフ", "📚 当選データ"]
    )

    with tab_predict:
        st.subheader("予想法を選んでボタンを押してください")

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
        action_cols = st.columns([1, 1, 2])
        with action_cols[0]:
            if st.button("✨ おすすめ（複合スコア）", type="primary", use_container_width=True):
                st.session_state.selected_key = "複合スコア法（おすすめ）"
                st.session_state.selected = strategy_composite(analyzer, seed=seed)
                st.session_state.results = None
        with action_cols[1]:
            if st.button("📋 全手法まとめて表示", use_container_width=True):
                st.session_state.results = generate_all_predictions(analyzer, seed=seed)
                st.session_state.selected = None
                st.session_state.selected_key = None
        with action_cols[2]:
            if st.button("🔀 番号を再生成", use_container_width=True):
                new_seed = random.randint(0, 999999)
                if st.session_state.selected_key:
                    st.session_state.selected = STRATEGY_BY_NAME[st.session_state.selected_key](
                        analyzer, seed=new_seed
                    )
                elif st.session_state.results:
                    st.session_state.results = generate_all_predictions(analyzer, seed=new_seed)

        st.divider()

        if st.session_state.selected:
            st.markdown("### 🎯 予想結果")
            st.markdown('<div class="result-box">', unsafe_allow_html=True)
            render_prediction(st.session_state.selected)
            st.markdown("</div>", unsafe_allow_html=True)
            nums = st.session_state.selected["numbers"]
            st.success(f"コピー用: {' '.join(f'{n:02d}' for n in sorted(nums))}")

        if st.session_state.results:
            st.markdown("### 📋 全手法の予想結果")
            for pred in st.session_state.results:
                with st.container():
                    st.markdown('<div class="result-box">', unsafe_allow_html=True)
                    render_prediction(pred)
                    st.markdown("</div>", unsafe_allow_html=True)

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
                st.session_state.multi_lines = generate_multiple_lines(
                    analyzer, strategy_composite, count=multi_count, seed=seed
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
            st.bar_chart(df_all.set_index("番号"))

        with chart_col2:
            st.markdown("**直近50回の出現回数 TOP20**")
            recent = analyzer.recent_frequency(50)
            df_recent = pd.DataFrame(
                [{"番号": n, "出現回数": recent[n]} for n in range(1, 44)]
            ).sort_values("出現回数", ascending=False).head(20)
            st.bar_chart(df_recent.set_index("番号"))

        st.markdown("**全番号の出現回数ヒートマップ**")
        df_heat = pd.DataFrame(
            [{"番号": f"{n:02d}", "出現回数": freq[n]} for n in range(1, 44)]
        )
        st.bar_chart(df_heat.set_index("番号"), height=300)

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
            st.bar_chart(df_odd.set_index("パターン"))

        sum_stats = analyzer.sum_range_stats()
        st.markdown(
            f"**本数字合計の統計:** 平均 {sum_stats['平均']:.1f} / "
            f"最小 {sum_stats['最小']:.0f} / 最大 {sum_stats['最大']:.0f}"
        )

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
        _render_history_tab(analyzer)


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
