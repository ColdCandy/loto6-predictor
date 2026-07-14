"""招待制パスワード認証（Streamlit）

secrets.toml または Streamlit Cloud の Secrets に招待ユーザーを置く。
パスワードは平文または SHA-256 ハッシュで設定可能。
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import streamlit as st

SESSION_AUTH = "auth_user"
SESSION_FAILS = "auth_failures"


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _as_plain_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    try:
        return {k: obj[k] for k in obj}  # type: ignore[index]
    except Exception:
        return {}


def _auth_section() -> dict[str, Any]:
    try:
        if "auth" not in st.secrets:
            return {}
        return _as_plain_dict(st.secrets["auth"])
    except Exception:
        return {}


def get_invites() -> list[dict[str, str]]:
    cfg = _auth_section()
    raw = cfg.get("invites", [])
    invites: list[dict[str, str]] = []
    try:
        items = list(raw)
    except Exception:
        items = []
    for item in items:
        d = _as_plain_dict(item)
        user = str(d.get("username", "")).strip()
        if not user:
            continue
        invites.append({
            "username": user,
            "password": str(d.get("password", "")),
            "password_hash": str(d.get("password_hash", "")),
            "label": str(d.get("label") or user),
        })
    return invites


def auth_enabled() -> bool:
    cfg = _auth_section()
    if "enabled" in cfg:
        return bool(cfg.get("enabled"))
    return bool(get_invites())


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_AUTH))


def current_user() -> dict[str, str] | None:
    return st.session_state.get(SESSION_AUTH)


def logout() -> None:
    st.session_state.pop(SESSION_AUTH, None)


def _check_password(invite: dict[str, str], password: str) -> bool:
    ph = invite.get("password_hash") or ""
    if ph:
        return hmac.compare_digest(password_hash(password), ph)
    plain = invite.get("password") or ""
    if not plain:
        return False
    return hmac.compare_digest(password_hash(plain), password_hash(password))


def try_login(username: str, password: str) -> tuple[bool, str]:
    user = username.strip()
    if not user or not password:
        return False, "招待IDとパスワードを入力してください"

    fails = int(st.session_state.get(SESSION_FAILS, 0))
    max_fails = int(_auth_section().get("max_failures", 8) or 8)
    if fails >= max_fails:
        return False, "失敗が多すぎます。ページを閉じて時間をおいてから再試行してください"

    for inv in get_invites():
        if inv["username"] == user and _check_password(inv, password):
            st.session_state[SESSION_AUTH] = {
                "username": inv["username"],
                "label": inv["label"],
            }
            st.session_state[SESSION_FAILS] = 0
            return True, ""

    st.session_state[SESSION_FAILS] = fails + 1
    left = max(0, max_fails - fails - 1)
    return False, f"招待IDまたはパスワードが違います（残り {left} 回）"


def render_login_page() -> None:
    title = str(_auth_section().get("app_title") or "ロト6予想（招待制）")
    st.title(title)
    st.info("このアプリは **招待制** です。発行された招待IDとパスワードでログインしてください。")

    invites = get_invites()
    if not invites:
        st.error(
            "招待ユーザーが設定されていません。管理者は "
            "`.streamlit/secrets.toml` または Streamlit Cloud の Secrets に "
            "auth.invites を設定してください。"
        )
        st.code(
            """[auth]
enabled = true

[[auth.invites]]
username = "family1"
password = "ここにパスワード"
label = "家族1"
""",
            language="toml",
        )
        return

    with st.form("invite_login"):
        username = st.text_input("招待ID", autocomplete="username")
        password = st.text_input("パスワード", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("ログイン", type="primary", use_container_width=True)
        if submitted:
            ok, msg = try_login(username, password)
            if ok:
                st.success("ログインしました")
                st.rerun()
            else:
                st.error(msg)

    st.caption("URLを知っていても、招待された人以外は入れません。")


def require_login() -> bool:
    """未ログインならログイン画面を出して False。認証済みなら True。"""
    cfg = _auth_section()
    if cfg.get("enabled") is False:
        return True

    if not auth_enabled():
        render_login_page()
        return False

    if is_authenticated():
        return True

    render_login_page()
    return False


def render_sidebar_account() -> None:
    user = current_user()
    if not user:
        return
    st.markdown("### 👤 ログイン中")
    st.caption(f"{user.get('label')}（{user.get('username')}）")
    if st.button("ログアウト", use_container_width=True):
        logout()
        st.rerun()
