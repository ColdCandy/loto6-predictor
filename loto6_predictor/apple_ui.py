"""Apple HIG デザインシステム"""

from __future__ import annotations

from pathlib import Path

THEME_CSS_PATH = Path(__file__).resolve().parent.parent / "web" / "apple_theme.css"


def load_apple_css() -> str:
    if THEME_CSS_PATH.exists():
        return THEME_CSS_PATH.read_text(encoding="utf-8")
    return ""


def inject_apple_theme() -> None:
    import streamlit as st

    css = load_apple_css()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hero(*, cloud: bool = False) -> None:
    import streamlit as st

    badge = "クラウド常時稼働" if cloud else "リアルタイム監視"
    subtitle = (
        "いつでもどこからでも — PCの電源が切れていても使えます"
        if cloud
        else "過去の当選データを分析して予想番号を表示"
    )
    st.markdown(
        f"""
        <div class="hero-wrap">
          <div class="hero-badge">● {badge}</div>
          <h1 class="main-title">ロト6 予想番号</h1>
          <p class="hero-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
