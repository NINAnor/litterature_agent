"""Streamlit UI for configuring, running, and reviewing the paper-agent.

Run locally from the repo root with:
    uv run streamlit run src/web_ui/app.py

Or via `uv run src/web_ui/main.py` (or the `paper-agent-ui` console script),
which launches this file under `streamlit run` (see main.py) — this is what
the Docker image's entrypoint uses.
"""

import io
import subprocess
from datetime import date
from pathlib import Path

import duckdb
import httpx
import streamlit as st
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

WEB_UI_DIR = Path(__file__).parent
REPO_ROOT = WEB_UI_DIR.parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
LOGO_PATH = WEB_UI_DIR / "assets" / "nina-logo.svg"

OPENALEX_BASE_URL = "https://api.openalex.org"

# NINA brand palette (teal + orange), matching pubstat.nina.no
CUSTOM_CSS = """
<style>
a { color: #87BFC4; }
a:hover { color: #5FB1BA; }

div[data-testid="stMetric"] {
    background-color: #ffffff;
    border: 1px solid rgba(38, 39, 48, 0.2);
    padding: 15px;
    border-radius: 0.5rem;
}

.footer {
    width: 100%;
    background-color: #f5f5f5;
    color: #666;
    text-align: center;
    padding: 10px 0;
    margin-top: 20px;
    font-size: 0.85em;
    border-top: 1px solid #ddd;
}

.footer a {
    color: #87BFC4;
    text-decoration: none;
}

.footer a:hover {
    text-decoration: underline;
}

/* Left-align the sidebar nav buttons (Runs menu) and keep padding
   consistent between selected (primary) and unselected (tertiary) items,
   so text doesn't shift horizontally depending on selection state. */
[data-testid="stSidebar"] div[data-testid="stButton"] button {
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 0.25rem 0.75rem !important;
    border-radius: 0.4rem !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] button > div {
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"]:hover {
    background-color: rgba(0, 0, 0, 0.05) !important;
}

/* Highlight the Highlights box in NINA teal */
.st-key-highlights_box {
    background-color: rgba(135, 191, 196, 0.15) !important;
    border: 1px solid rgba(135, 191, 196, 0.6) !important;
}
</style>
"""


yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096  # avoid wrapping long instruction strings


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f)


def dump_config_str(cfg: dict) -> str:
    buf = io.StringIO()
    yaml.dump(cfg, buf)
    return buf.getvalue()


@st.cache_data(ttl=5)
def load_summaries(data_dir: str):
    """Join summaries.parquet with papers.parquet (by paper_id) via DuckDB."""
    data_path = Path(data_dir)
    summaries_path = data_path / "summaries.parquet"
    papers_path = data_path / "papers.parquet"

    if not summaries_path.exists():
        return None

    con = duckdb.connect()
    try:
        if papers_path.exists():
            df = con.execute(
                f"""
                SELECT s.*, p.authors, p.url, p.source, p.published_date
                FROM '{summaries_path}' s
                LEFT JOIN '{papers_path}' p USING (paper_id)
                ORDER BY s.run_date DESC, s.relevance_score DESC
            """
            ).df()
        else:
            df = con.execute(
                f"""
                SELECT * FROM '{summaries_path}'
                ORDER BY run_date DESC, relevance_score DESC
            """
            ).df()
        return df
    finally:
        con.close()


@st.cache_data(ttl=5)
def load_highlights(data_dir: str):
    """Load highlights.parquet, grouped by run day."""
    highlights_path = Path(data_dir) / "highlights.parquet"
    if not highlights_path.exists():
        return None

    con = duckdb.connect()
    try:
        return con.execute(
            f"""
            SELECT * FROM '{highlights_path}' ORDER BY run_date DESC
        """
        ).df()
    finally:
        con.close()


@st.cache_data(ttl=300)
def search_openalex_journals(query: str, mailto: str = ""):
    """Search OpenAlex's `sources` endpoint for journals matching `query`."""
    if not query:
        return []

    params = {"search": query, "per_page": 10, "filter": "type:journal"}
    if mailto:
        params["mailto"] = mailto

    try:
        resp = httpx.get(f"{OPENALEX_BASE_URL}/sources", params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception:
        return []

    return [
        {
            "name": r.get("display_name", ""),
            "issn": r.get("issn_l") or (r.get("issn") or [""])[0],
            "works_count": r.get("works_count", 0),
        }
        for r in results
        if r.get("display_name") and (r.get("issn_l") or r.get("issn"))
    ]


st.set_page_config(
    page_title="Paper Agent",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "\U0001f4da",
    layout="wide",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "config" not in st.session_state:
    st.session_state.config = load_config()

cfg = st.session_state.config
settings_cfg = cfg.get("settings", {})
data_dir = settings_cfg.get("data_dir", str(REPO_ROOT / "paper_summaries"))

if LOGO_PATH.exists():
    col1, col2, col3 = st.sidebar.columns([1, 2, 1])
    with col2:
        st.image(str(LOGO_PATH), width=150)

st.sidebar.title("Paper Agent")
st.sidebar.caption("Configurable literature tracker for NINA researchers")

summaries_df = load_summaries(data_dir)
highlights_df = load_highlights(data_dir)

# --- Sidebar: list of runs (grouped by date), from summaries.parquet ---
st.sidebar.divider()
st.sidebar.subheader(":material/history: Runs")

if summaries_df is None or summaries_df.empty:
    st.sidebar.caption("No summaries generated yet.")
    run_dates = []
    selected = "All"
else:
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

    selected = st.session_state["selected_run_key"]

st.title("Paper Agent")

# ---------------------------------------------------------------------------
# Main layout: summaries | settings
# ---------------------------------------------------------------------------
middle, right = st.columns([2, 1.4])

# --- Middle: render summaries for the selected run ---
with middle:
    if summaries_df is None or summaries_df.empty:
        st.subheader(":material/inbox: No summaries yet")
        st.caption(f"Run the agent to populate `{data_dir}/summaries.parquet`.")
    else:
        if selected == "All":
            day_df = summaries_df
            st.subheader(f":material/description: All summaries ({len(day_df)})")
        else:
            selected_day = date.fromisoformat(selected)
            day_df = summaries_df[summaries_df["run_day"] == selected_day]
            st.subheader(
                f":material/description: {selected_day.strftime('%d/%m/%Y')} ({len(day_df)} papers)"
            )

        # --- Highlights for the selected run(s) ---
        if highlights_df is not None and not highlights_df.empty:
            if selected == "All":
                day_highlights = highlights_df
            else:
                day_highlights = highlights_df[
                    highlights_df["run_date"].dt.date == selected_day
                ]
            if not day_highlights.empty:
                with st.container(border=True, key="highlights_box"):
                    st.markdown("##### :material/star: Highlights")
                    for h in day_highlights["highlight"]:
                        st.markdown(f"- {h}")

        search = st.text_input(
            "Search title or summary",
            key="search_query",
            placeholder="Filter by keyword...",
        )
        if search:
            mask = day_df["title"].str.contains(search, case=False, na=False) | day_df[
                "summary"
            ].str.contains(search, case=False, na=False)
            day_df = day_df[mask]

        for _, row in day_df.iterrows():
            with st.container(border=True):
                if row.get("url"):
                    st.markdown(f"#### [{row['title']}]({row['url']})")
                else:
                    st.markdown(f"#### {row['title']}")

                meta_bits = [
                    f":material/target: Relevance: {row['relevance_score']:.2f}"
                ]
                if row.get("source"):
                    meta_bits.append(f":material/public: Journal: {row['source']}")
                st.caption("  •  ".join(meta_bits))

                second_row = []
                if row.get("published_date") is not None:
                    pub_date = row["published_date"]
                    pub_date_str = (
                        pub_date.strftime("%d/%m/%Y")
                        if hasattr(pub_date, "strftime")
                        else str(pub_date)
                    )
                    second_row.append(f":material/calendar_month: Date: {pub_date_str}")

                authors = row.get("authors")
                if authors is not None and len(authors) > 0:
                    authors_str = ", ".join(authors[:5])
                    if len(authors) > 5:
                        authors_str += " et al."
                    second_row.append(f":material/group: {authors_str}")

                if second_row:
                    st.caption("  •  ".join(second_row))

                st.write(row["summary"])

                if row.get("methods") is not None and len(row["methods"]) > 0:
                    st.caption(
                        f":material/build: **Methods:** {', '.join(row['methods'])}"
                    )
                if row.get("topics") is not None and len(row["topics"]) > 0:
                    st.caption(
                        f":material/sell: **Topics:** {', '.join(row['topics'])}"
                    )

# --- Right: run controls + settings accordion ---
with right:
    with st.container(border=True):
        st.subheader(":material/settings: Settings")
        days = st.number_input(
            "Days to look back",
            min_value=1,
            max_value=60,
            value=int(settings_cfg.get("default_days", 3)),
            key="run_days",
        )

        # Keywords
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

        # Journals
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
                            icon=(
                                ":material/check:"
                                if already_added
                                else ":material/add:"
                            ),
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

    if show_advanced:
        with st.container(border=True):
            st.subheader(":material/tune: Advanced settings")
            source = st.selectbox("Source", ["all", "journals"], key="run_source")
            # OpenAlex
            with st.expander("OpenAlex", expanded=False, icon=":material/public:"):
                openalex_cfg = cfg.setdefault("openalex", {})
                openalex_cfg["mailto"] = DQ(
                    st.text_input(
                        "Mailto (polite pool)",
                        value=openalex_cfg.get("mailto", ""),
                        key="openalex_mailto",
                    )
                )

            # Model
            with st.expander("Model", expanded=False, icon=":material/smart_toy:"):
                model_cfg = cfg.setdefault("model", {})
                model_cfg["base_url"] = DQ(
                    st.text_input(
                        "Base URL",
                        value=model_cfg.get("base_url", ""),
                        key="model_base_url",
                    )
                )
                model_cfg["model_name"] = DQ(
                    st.text_input(
                        "Model name",
                        value=model_cfg.get("model_name", ""),
                        key="model_name",
                    )
                )
                model_cfg["api_key"] = DQ(
                    st.text_input(
                        "API key",
                        value=model_cfg.get("api_key", ""),
                        type="password",
                        key="model_api_key",
                    )
                )

                if st.button(
                    "Test connection",
                    key="test_connection",
                    icon=":material/wifi_tethering:",
                ):
                    import httpx

                    base = model_cfg.get("base_url", "").rstrip("/")
                    try:
                        resp = httpx.get(
                            f"{base}/models",
                            headers={
                                "Authorization": f"Bearer {model_cfg.get('api_key', '')}"
                            },
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            st.success(f"Connected! HTTP {resp.status_code}")
                        else:
                            st.error(f"HTTP {resp.status_code}: {resp.text[:300]}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")

            # Settings
            with st.expander("Run settings", expanded=False, icon=":material/build:"):
                settings_cfg = cfg.setdefault("settings", {})
                settings_cfg["default_days"] = st.number_input(
                    "Default days to look back",
                    min_value=1,
                    max_value=30,
                    value=int(settings_cfg.get("default_days", 3)),
                    key="default_days",
                )
                settings_cfg["data_dir"] = DQ(
                    st.text_input(
                        "Data directory",
                        value=settings_cfg.get("data_dir", ""),
                        key="data_dir",
                    )
                )
                settings_cfg["paper_timeout_seconds"] = st.number_input(
                    "Paper timeout (seconds)",
                    min_value=5,
                    max_value=600,
                    value=int(settings_cfg.get("paper_timeout_seconds", 60)),
                    key="paper_timeout",
                )
                settings_cfg["abstract_max_chars"] = st.number_input(
                    "Abstract max chars sent to model",
                    min_value=100,
                    max_value=5000,
                    value=int(settings_cfg.get("abstract_max_chars", 800)),
                    key="abstract_max_chars",
                )
                settings_cfg["min_relevance_score"] = st.slider(
                    "Minimum relevance score to keep",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(settings_cfg.get("min_relevance_score", 0.7)),
                    step=0.05,
                    key="min_relevance",
                )

            # Agents
            with st.expander("Agents", expanded=False, icon=":material/psychology:"):
                agents_cfg = cfg.setdefault("agents", {})

                for name in list(agents_cfg.keys()):
                    skill = agents_cfg[name]
                    st.markdown(f"**{name}**")
                    skill["instructions"] = st.text_area(
                        "Instructions",
                        value=skill.get("instructions", ""),
                        height=200,
                        key=f"{name}_instructions",
                    )
                    has_temp = st.checkbox(
                        "Set temperature",
                        value="temperature" in skill,
                        key=f"{name}_has_temp",
                    )
                    if has_temp:
                        skill["temperature"] = st.slider(
                            "Temperature",
                            0.0,
                            1.0,
                            float(skill.get("temperature", 0.5)),
                            0.05,
                            key=f"{name}_temp",
                        )
                    elif "temperature" in skill:
                        del skill["temperature"]

                    has_max_tok = st.checkbox(
                        "Set max_tokens",
                        value="max_tokens" in skill,
                        key=f"{name}_has_maxtok",
                    )
                    if has_max_tok:
                        skill["max_tokens"] = st.number_input(
                            "Max tokens",
                            min_value=1,
                            max_value=8192,
                            value=int(skill.get("max_tokens", 512)),
                            key=f"{name}_maxtok",
                        )
                    elif "max_tokens" in skill:
                        del skill["max_tokens"]

                    if st.button(
                        f"Delete '{name}'",
                        key=f"{name}_delete",
                        icon=":material/delete:",
                    ):
                        del agents_cfg[name]
                        st.rerun()

            # Raw YAML
            with st.expander("Raw YAML", expanded=False, icon=":material/code:"):
                st.code(dump_config_str(cfg), language="yaml")

    source = st.session_state.get("run_source", "all")
    run_clicked = st.button(
        "Run paper-agent", type="primary", icon=":material/play_arrow:", width="stretch"
    )

    if run_clicked:
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
