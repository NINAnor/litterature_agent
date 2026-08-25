"""Shared Save-button + auto-dismissing confirmation banner.

Used by both the main Settings panel and the Advanced settings panel so
"Saved!" behaves consistently everywhere: it spans the full width of its
container (not just the button's column) and disappears on its own after a
few seconds.
"""

import time

import streamlit as st

from web_ui.core.config_io import save_user_config

_CONFIRM_SECONDS = 3


def render_save_button(
    cfg: dict, user_id: str, key: str, label: str = "Save", width: str = "stretch"
) -> None:
    """Render the Save button itself. Safe to call inside a narrow column —
    pair it with `render_save_confirmation(key)` rendered at full width
    afterwards (e.g. below a `st.columns(...)` block).
    """
    if st.button(label, type="primary", icon=":material/save:", width=width, key=key):
        save_user_config(user_id, cfg)
        st.session_state[f"{key}__saved_until"] = time.time() + _CONFIRM_SECONDS


def render_save_confirmation(key: str) -> None:
    """Show a full-width "Saved!" banner for a few seconds after `key`'s Save
    button was clicked, then auto-dismiss it (no manual close needed).
    """
    banner_key = f"{key}__saved_until"
    remaining = st.session_state.get(banner_key, 0) - time.time()

    if remaining <= 0:
        return

    with st.container(key=f"{key}_banner"):
        st.success("Saved!", icon=":material/check_circle:")

    time.sleep(min(remaining, _CONFIRM_SECONDS))
    st.rerun()
