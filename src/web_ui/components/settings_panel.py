"""Right column: the "Settings" container (Keywords, Journals, Save/Reload)."""

import streamlit as st

from web_ui.core.config_io import DQ, load_config, save_config
from web_ui.core.data import search_openalex_journals


def render_settings_panel(cfg: dict) -> tuple[int, bool]:
    """Render the Settings container. Returns (days, show_advanced)."""
    settings_cfg = cfg.get("settings", {})

    with st.container(border=True):
        st.subheader(":material/settings: Settings")
        days = st.number_input(
            "Days to look back",
            min_value=1,
            max_value=60,
            value=int(settings_cfg.get("default_days", 3)),
            key="run_days",
        )

        _render_keywords(cfg)
        _render_journals(cfg)

        show_advanced = st.checkbox(
            "Show advanced settings", key="show_advanced_settings"
        )

        save_col1, save_col2 = st.columns(2)
        with save_col1:
            if st.button(
                "Save", type="primary", icon=":material/save:", width="stretch"
            ):
                save_config(cfg)
                st.success("Saved!")
        with save_col2:
            if st.button("Reload", icon=":material/refresh:", width="stretch"):
                st.session_state.config = load_config()
                st.rerun()

    return days, show_advanced


def _render_keywords(cfg: dict) -> None:
    with st.expander("Keywords", expanded=True, icon=":material/label:"):
        cfg["keywords"] = st.multiselect(
            "Keywords",
            options=cfg.get("keywords", []),
            default=cfg.get("keywords", []),
            accept_new_options=True,
            placeholder="Type a keyword and press enter...",
            key="keywords_chips",
        )

        cfg["exclude_keywords"] = st.multiselect(
            "Exclude keywords",
            options=cfg.get("exclude_keywords", []),
            default=cfg.get("exclude_keywords", []),
            accept_new_options=True,
            placeholder="Type an exclude keyword and press enter...",
            key="exclude_keywords_chips",
        )


def _render_journals(cfg: dict) -> None:
    with st.expander("Journals", expanded=True, icon=":material/menu_book:"):
        st.caption("Search OpenAlex for a journal and add it to the list below.")
        search_query = st.text_input(
            "Search journals",
            placeholder="e.g. ecology, remote sensing...",
            key="journal_search",
        )
        if search_query:
            mailto = cfg.get("openalex", {}).get("mailto", "")
            search_results = search_openalex_journals(search_query, mailto)
            existing_issns = {j.get("issn") for j in cfg.get("journals", [])}

            if not search_results:
                st.caption("No matching journals found.")
            for r in search_results:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(
                        f"**{r['name']}**  \nISSN: `{r['issn']}` · {r['works_count']:,} works"
                    )
                with col2:
                    already_added = r["issn"] in existing_issns
                    if st.button(
                        "Added" if already_added else "Add",
                        key=f"add_journal_{r['issn']}",
                        disabled=already_added,
                        icon=":material/check:" if already_added else ":material/add:",
                        width="stretch",
                    ):
                        cfg.setdefault("journals", []).append(
                            {"name": r["name"], "issn": DQ(r["issn"])}
                        )
                        st.rerun()

        st.caption(f"Currently tracked ({len(cfg.get('journals', []))})")
        for idx, j in enumerate(cfg.get("journals", [])):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{j.get('name', '')}**  \nISSN: `{j.get('issn', '')}`")
            with col2:
                if st.button(
                    "Remove",
                    key=f"remove_journal_{idx}",
                    icon=":material/delete:",
                    width="stretch",
                ):
                    cfg["journals"].pop(idx)
                    st.rerun()
