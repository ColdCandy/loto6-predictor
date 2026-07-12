"""Streamlit Cloud 用エントリーポイント"""

from __future__ import annotations

import traceback

try:
    from app import main

    main()
except Exception:
    import streamlit as st

    st.error("アプリの起動中にエラーが発生しました")
    st.code(traceback.format_exc())
