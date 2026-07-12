"""Apple HIG デザインシステム"""

from __future__ import annotations

from pathlib import Path

THEME_CSS_PATH = Path(__file__).resolve().parent.parent / "web" / "apple_theme.css"
ULTRA_CSS_PATH = Path(__file__).resolve().parent.parent / "web" / "ultra_smooth.css"
STREAMLIT_CSS_PATH = Path(__file__).resolve().parent.parent / "web" / "streamlit_theme.css"


def load_apple_css() -> str:
    """HTML版用フルテーマ"""
    parts: list[str] = []
    if THEME_CSS_PATH.exists():
        parts.append(THEME_CSS_PATH.read_text(encoding="utf-8"))
    if ULTRA_CSS_PATH.exists():
        parts.append(ULTRA_CSS_PATH.read_text(encoding="utf-8"))
    return "\n".join(parts)


def load_streamlit_css() -> str:
    """Streamlit用軽量テーマ（WebSocket RangeError 対策）"""
    if STREAMLIT_CSS_PATH.exists():
        return STREAMLIT_CSS_PATH.read_text(encoding="utf-8")
    return load_apple_css()


def inject_apple_theme() -> None:
    import streamlit as st

    try:
        css = load_streamlit_css()
        if not css:
            return
        # 大きなHTMLはWebSocketで RangeError を起こすため st.html を使用
        if hasattr(st, "html"):
            st.html(f"<style>{css}</style>", unsafe_allow_javascript=False)
        else:
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except Exception:
        pass


def render_hero(*, cloud: bool = False) -> None:
    import streamlit as st

    badge = "クラウド常時稼働" if cloud else "リアルタイム監視"
    subtitle = (
        "いつでもどこからでも — PCの電源が切れていても使えます"
        if cloud
        else "過去の当選データを分析して予想番号を表示"
    )
    body = (
        f'<div class="hero-wrap">'
        f'<div class="hero-badge">● {badge}</div>'
        f'<h1 class="main-title">ロト6 予想番号</h1>'
        f'<p class="hero-subtitle">{subtitle}</p>'
        f"</div>"
    )
    try:
        if hasattr(st, "html"):
            st.html(body, unsafe_allow_javascript=False)
        else:
            st.markdown(body, unsafe_allow_html=True)
    except Exception:
        st.title("ロト6 予想番号")
        st.caption(subtitle)
