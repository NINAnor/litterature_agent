"""Right column: the Run button that shells out to `uv run paper-agent`."""

import subprocess

import streamlit as st

from web_ui.core.constants import REPO_ROOT
from web_ui.core.data import load_summaries


def render_run_panel(days: int, source: str | None) -> None:
    source = source or st.session_state.get("run_source", "all")
    run_clicked = st.button(
        "Run paper-agent", type="primary", icon=":material/play_arrow:", width="stretch"
    )

    if not run_clicked:
        return

    cmd = ["uv", "run", "paper-agent", "--days", str(days), "--source", source]
    st.info(f"Running: `{' '.join(cmd)}`")
    with st.spinner("Running paper-agent..."):
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    if result.stdout:
        with st.expander("Output", expanded=result.returncode != 0):
            st.code(result.stdout, language="text")

    if result.returncode != 0:
        st.error(f"Exited with code {result.returncode}")
        if result.stderr:
            st.code(result.stderr, language="text")
    else:
        st.success("Done!")
        load_summaries.clear()
        st.session_state.pop("selected_run_key", None)
        st.rerun()
