"""Streamlit Cloud / ローカル共通エントリーポイント（Main file = streamlit_app.py）"""

from __future__ import annotations

import traceback

import streamlit as st

PAGES_URL = "https://coldcandy.github.io/loto6-predictor/"


def _boot_error(exc: BaseException) -> None:
    try:
        st.set_page_config(page_title="ロト6 予想番号", page_icon="🎱", layout="wide")
    except Exception:
        pass
    st.title("ロト6 予想番号")
    st.error("アプリの起動に失敗しました。")
    st.info(
        "招待制アプリです。Secrets（auth.invites）を確認するか、"
        "いったん公開サイトをご利用ください。"
    )
    st.link_button("公開サイト（予想のみ）を開く", PAGES_URL)
    with st.expander("エラー詳細（管理者向け）"):
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _ensure_cloud_data() -> None:
    try:
        from loto6_predictor.cloud import is_cloud_hosted
        from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv

        if is_cloud_hosted() or not DEFAULT_DATA_PATH.exists():
            download_csv(DEFAULT_DATA_PATH)
    except Exception:
        pass


def _run() -> None:
    _ensure_cloud_data()
    from app import main

    main()


try:
    _run()
except Exception as exc:
    try:
        _boot_error(exc)
    except Exception:
        # Streamlit 自体が壊れているときの最終手段
        raise SystemExit(f"boot failed: {exc}") from exc
