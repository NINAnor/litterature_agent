"""Fake login: a username field + Login button, standing in for FEIDE.

This is a stand-in for FEIDE login: for the demo, users just type a name/id
and get their own isolated config + summaries in S3
(`s3://<bucket>/<prefix>/<user_id>/...`). Swap this out for real FEIDE SSO
later without touching the rest of the app — everything downstream only
needs a `user_id` string.
"""

import streamlit as st

from paper_agent.s3_storage import sanitize_user_id


def render_login_form() -> str:
    """Render the username + "Logg inn" button on the main page (shown before
    any user is signed in this session). Returns the sanitized user_id once
    the form is submitted with a non-empty username, otherwise "".
    """
    with st.form("login_form", border=False):
        raw_user_id = st.text_input(
            "Username",
            placeholder="e.g. taheera.ahmed",
            help="Stand-in for FEIDE login (demo only) — separates"
            "keywords/journals/summaries in S3 from other users.",
        )
        submitted = st.form_submit_button(
            "Logg inn", type="primary", icon=":material/login:", width="stretch"
        )

    if submitted and raw_user_id.strip():
        return sanitize_user_id(raw_user_id)

    return ""


def render_signed_in_sidebar(user_id: str) -> None:
    """Small "signed in as ..." indicator + Log out button in the sidebar,
    shown once a user is signed in.
    """
    st.sidebar.divider()
    st.sidebar.caption(f":material/person: Signed in as **{user_id}**")
    if st.sidebar.button("Log out", icon=":material/logout:", width="stretch"):
        for key in ("current_user_id", "config", "selected_run_key"):
            st.session_state.pop(key, None)
        st.rerun()
