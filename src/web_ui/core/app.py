"""Streamlit UI for configuring, running, and reviewing the paper-agent.

Run locally from the repo root with:
    uv run streamlit run src/web_ui/core/app.py

Or via `uv run src/web_ui/main.py` (or the `paper-agent-ui` console script),
which launches this file under `streamlit run` (see ../main.py) — this is
what the Docker image's entrypoint uses.

This module is intentionally thin: it just loads config/data and composes
the panels defined under `web_ui/components/`.
"""

import streamlit as st

from web_ui.components.advanced_panel import render_advanced_panel
from web_ui.components.run_panel import render_run_panel
from web_ui.components.settings_panel import render_settings_panel
from web_ui.components.sidebar import render_sidebar
from web_ui.components.summaries_panel import render_summaries_panel
from web_ui.components.user_panel import render_user_selector
from web_ui.core.config_io import load_user_config
from web_ui.core.constants import LOGO_PATH
from web_ui.core.data import load_highlights, load_summaries
from web_ui.core.styles import CUSTOM_CSS

st.set_page_config(
    page_title="Paper Agent",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "\U0001f4da",
    layout="wide",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

user_id = render_user_selector()

if not user_id:
    st.title("Paper Agent")
    st.info(
        "Enter a username in the sidebar to continue "
        "(stand-in for FEIDE login — this keeps your keywords, journals, "
        "and summaries separate from other users)."
    )
    st.stop()

if st.session_state.get("current_user_id") != user_id:
    # User switched (or first load): drop any cached config/data so we don't
    # leak the previous user's state, and (re)fetch this user's config.
    st.session_state.current_user_id = user_id
    st.session_state.config = load_user_config(user_id)
    st.session_state.pop("selected_run_key", None)
    load_summaries.clear()
    load_highlights.clear()

cfg = st.session_state.config
settings_cfg = cfg.get("settings", {})
data_dir = settings_cfg.get("data_dir", "")

summaries_df = load_summaries(data_dir)
highlights_df = load_highlights(data_dir)

selected = render_sidebar(summaries_df)

st.title("Paper Agent")
st.caption(f":material/person: Signed in as **{user_id}**")

# ---------------------------------------------------------------------------
# Main layout: summaries | settings
# ---------------------------------------------------------------------------
middle, right = st.columns([2, 1.4])

with middle:
    render_summaries_panel(summaries_df, highlights_df, selected, data_dir)

with right:
    days, show_advanced = render_settings_panel(cfg, user_id)

    source = None
    if show_advanced:
        source = render_advanced_panel(cfg, user_id)

    render_run_panel(days, source, user_id, cfg)
