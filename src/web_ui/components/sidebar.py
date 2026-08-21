"""Sidebar: logo, title, and the Runs nav menu."""

import streamlit as st

from web_ui.core.constants import LOGO_PATH


def render_sidebar(summaries_df) -> str:
    """Render the sidebar and return the selected run key ("All" or an ISO date)."""
    if LOGO_PATH.exists():
        col1, col2, col3 = st.sidebar.columns([1, 2, 1])
        with col2:
            st.image(str(LOGO_PATH), width=150)

    st.sidebar.title("Paper Agent")
    st.sidebar.caption("Track and summarize academic literature on your research topic")

    st.sidebar.divider()
    st.sidebar.subheader(":material/history: Runs")

    if summaries_df is None or summaries_df.empty:
        st.sidebar.caption("No summaries generated yet.")
        return "All"

    summaries_df["run_day"] = summaries_df["run_date"].dt.date
    counts = summaries_df.groupby("run_day").size().sort_index(ascending=False)
    run_dates = list(counts.index)

    if "selected_run_key" not in st.session_state:
        st.session_state["selected_run_key"] = "All"

    nav_items = [("All", f"All ({len(summaries_df)})", ":material/list:")]
    for d in run_dates:
        nav_items.append(
            (
                d.isoformat(),
                f"{d.strftime('%d/%m/%Y')} ({counts[d]})",
                ":material/description:",
            )
        )

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
