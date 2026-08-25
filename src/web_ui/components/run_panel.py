"""Right column: the Run button that shells out to `uv run paper-agent`."""

import subprocess
import tempfile
from pathlib import Path

import streamlit as st

from web_ui.core.config_io import dump_config_str, save_user_config
from web_ui.core.constants import REPO_ROOT
from web_ui.core.data import load_summaries, load_highlights


def render_run_panel(days: int, source: str | None, user_id: str, cfg: dict) -> None:
    source = source or st.session_state.get("run_source", "all")
    run_clicked = st.button(
        "Run paper-agent", type="primary", icon=":material/play_arrow:", width="stretch"
    )

    if run_clicked:
        # Persist current in-memory edits so the CLI run picks them up, and
        # so they survive even if the user navigates away before clicking Save.
        save_user_config(user_id, cfg)

        # The CLI reads `--config` from local disk, so materialize this
        # user's config to a scratch file; the config's `settings.data_dir`
        # (an s3:// URI) is what actually isolates their papers/summaries.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(dump_config_str(cfg))
            tmp_config_path = tmp.name

        try:
            cmd = [
                "uv",
                "run",
                "paper-agent",
                "--days",
                str(days),
                "--source",
                source,
                "--config",
                tmp_config_path,
            ]
            with st.spinner(f"Running: `{' '.join(cmd)}`"):
                result = subprocess.run(
                    cmd, cwd=REPO_ROOT, capture_output=True, text=True
                )
        finally:
            Path(tmp_config_path).unlink(missing_ok=True)

        st.session_state["last_run_result"] = {
            "cmd": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        load_summaries.clear()
        load_highlights.clear()
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
