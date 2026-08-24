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

    if run_clicked:
        cmd = ["uv", "run", "paper-agent", "--days", str(days), "--source", source]
        with st.spinner(f"Running: `{' '.join(cmd)}`"):
            result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

        st.session_state["last_run_result"] = {
            "cmd": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        load_summaries.clear()
        st.session_state.pop("selected_run_key", None)
        st.rerun()

    _render_last_run_result()


def _render_last_run_result() -> None:
    """Show the outcome of the last run, persisted in session_state so it
    survives the st.rerun() triggered right after the run completes.
    """
    last = st.session_state.get("last_run_result")
    if not last:
        return

    st.caption(f"Last run: `{' '.join(last['cmd'])}`")

    if last["returncode"] != 0:
        st.error(f"Exited with code {last['returncode']}")
        if last["stderr"]:
            st.code(last["stderr"], language="text")
    elif "no papers found" in last["stdout"].lower():
        st.warning("No new papers found matching your criteria.")
    else:
        st.success("Done!")

    if last["stdout"]:
        with st.expander("Output", expanded=last["returncode"] != 0):
            st.code(last["stdout"], language="text")
