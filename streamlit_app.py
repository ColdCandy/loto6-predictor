"""Streamlit Cloud / ローカル共通エントリーポイント（Main file = streamlit_app.py）"""

from __future__ import annotations

import traceback

import streamlit as st

PAGES_URL = "https://coldcandy.github.io/loto6-predictor/"


def _safe_page_config() -> None:
    try:
        st.set_page_config(page_title="ロト6 予想番号", page_icon="🎱", layout="wide")
    except Exception:
        pass


def _boot_error(exc: BaseException) -> None:
    _safe_page_config()
    st.title("ロト6 予想番号")
    st.error("アプリの起動に失敗しました。")
    st.info(
        "招待制アプリです。Secrets（auth.invites）を確認するか、"
        "いったん公開サイトをご利用ください。"
    )
    st.link_button("公開サイト（予想のみ・PC不要）を開く", PAGES_URL)
    with st.expander("エラー詳細（管理者向け）"):
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _ensure_local_data() -> None:
    """起動をネットワークに依存させない。既存CSVがあればそれを使う。"""
    try:
        from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv

        if DEFAULT_DATA_PATH.exists() and DEFAULT_DATA_PATH.stat().st_size > 1000:
            return
        download_csv(DEFAULT_DATA_PATH)
    except Exception:
        pass


def _run() -> None:
    # page_config はアプリ本体より先（他の st呼び出し前）
    _safe_page_config()
    st.session_state["_ui_ready"] = True

    _ensure_local_data()
    from app import main

    main()


try:
    _run()
except Exception as exc:
    try:
        _boot_error(exc)
    except Exception:
        raise SystemExit(f"boot failed: {exc}") from exc
