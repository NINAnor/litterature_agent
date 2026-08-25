"""Top-of-sidebar username input.

This is a stand-in for FEIDE login: for the demo, users just type a name/id
and get their own isolated config + summaries in S3
(`s3://<bucket>/<prefix>/<user_id>/...`). Swap this out for real FEIDE SSO
later without touching the rest of the app — everything downstream only
needs a `user_id` string.
"""

import streamlit as st

from paper_agent.s3_storage import sanitize_user_id


def render_user_selector() -> str:
    """Render the username input. Returns the sanitized user_id, or "" if
    none has been entered yet.
    """
    st.sidebar.text_input(
        "Username",
        key="raw_user_id",
        placeholder="e.g. taheera.ahmed",
        help="Stand-in for FEIDE login (demo only) — separates your "
        "keywords/journals/summaries in S3 from other users.",
    )
    raw_user_id = st.session_state.get("raw_user_id", "").strip()

    if not raw_user_id:
        return ""

    return sanitize_user_id(raw_user_id)
