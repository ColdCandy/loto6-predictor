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
    st.success(f"代替（すぐ使える・ログイン不要）: {PAGES_URL}")
    st.link_button("GitHub Pages版を開く", PAGES_URL, type="primary")
    st.markdown(
        """
**Streamlit版を直す場合**
1. https://share.streamlit.io/ でアプリを開く
2. ⋮ メニュー → **Settings** → **Sharing** を **Public** にする
3. Main file path を `streamlit_app.py` にする
4. **Reboot app**
        """
    )
    with st.expander("エラー詳細"):
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _ensure_cloud_data() -> None:
    """クラウド起動時にデータが無いケースを防ぐ"""
    try:
        from loto6_predictor.cloud import is_cloud_hosted
        from loto6_predictor.data import DEFAULT_DATA_PATH, download_csv

        if is_cloud_hosted() or not DEFAULT_DATA_PATH.exists():
            download_csv(DEFAULT_DATA_PATH)
    except Exception:
        pass


try:
    _ensure_cloud_data()
    from app import main

    main()
except Exception as exc:
    _boot_error(exc)
