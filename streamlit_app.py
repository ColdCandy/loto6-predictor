"""Streamlit Cloud 用エントリーポイント（メインファイルは必ずこれ）"""

from __future__ import annotations

import traceback

import streamlit as st


def _boot_error(exc: BaseException) -> None:
    try:
        st.set_page_config(page_title="ロト6 予想番号", page_icon="🎱", layout="wide")
    except Exception:
        pass
    st.title("ロト6 予想番号")
    st.error("アプリの起動に失敗しました。")
    st.markdown(
        """
**すぐ使える代替URL（PCオフでもOK）**  
https://coldcandy.github.io/loto6-predictor/

**Streamlit版を直す手順**
1. https://share.streamlit.io/ を開く
2. アプリの設定で **Main file path** を `streamlit_app.py` にする
3. **Reboot app** を押す
4. 1分待ってから https://loto6-predictor-nmrmsaoqhebs2wxvbs6oin.streamlit.app/ を開く
        """
    )
    with st.expander("エラー詳細"):
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


try:
    from app import main

    main()
except Exception as exc:
    _boot_error(exc)
