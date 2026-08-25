"""Sidebar: logo, title, and the Runs nav menu."""

import streamlit as st

from web_ui.core.constants import LOGO_PATH


def render_sidebar(summaries_df) -> str:
    """Render the sidebar and return the selected run key (an ISO date), or
    an empty string if no summaries exist yet.
    """
    if LOGO_PATH.exists():
        _, logo_col, _ = st.sidebar.columns([1, 2, 1])
        with logo_col:
            st.image(str(LOGO_PATH), width=150)

    st.sidebar.title("Paper Agent")
    st.sidebar.caption("Track and summarize academic literature on your research topic")

    st.sidebar.divider()
    st.sidebar.subheader(":material/history: Runs")

    if summaries_df is None or summaries_df.empty:
        st.sidebar.caption("No summaries generated yet.")
        return ""

    summaries_df["run_day"] = summaries_df["run_date"].dt.date
    counts = summaries_df.groupby("run_day").size().sort_index(ascending=False)
    run_dates = list(counts.index)

    if "selected_run_key" not in st.session_state or st.session_state[
        "selected_run_key"
    ] not in [d.isoformat() for d in run_dates]:
        st.session_state["selected_run_key"] = run_dates[0].isoformat()

    nav_items = [
        (
            d.isoformat(),
            f"{d.strftime('%d/%m/%Y')} ({counts[d]})",
            ":material/description:",
        )
        for d in run_dates
    ]

    for key_val, label, icon in nav_items:
        is_active = st.session_state["selected_run_key"] == key_val
        if st.sidebar.button(
            label,
            key=f"run_nav_{key_val}",
            type="primary" if is_active else "tertiary",
            icon=icon,
            width="stretch",
        ):
            st.session_state["selected_run_key"] = key_val
            st.rerun()

    return st.session_state["selected_run_key"]
