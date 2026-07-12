"""Streamlit Cloud 用エントリーポイント"""

from __future__ import annotations

import traceback

import streamlit as st


def _boot_error(exc: BaseException) -> None:
    try:
        st.set_page_config(page_title="ロト6 予想番号", page_icon="🎱", layout="wide")
    except Exception:
        pass
    st.error("アプリの起動に失敗しました。30秒ほど待ってから再読み込みしてください。")
    st.caption(
        "Streamlit Cloud のメインファイルは **streamlit_app.py** に設定してください。"
        " 改善しない場合は share.streamlit.io で Reboot app を実行してください。"
    )
    with st.expander("エラー詳細（開発者向け）"):
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


try:
    from app import main

    main()
except Exception as exc:
    _boot_error(exc)
