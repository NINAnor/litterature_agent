"""Cached data loaders: parquet summaries/highlights and OpenAlex journal search."""

from pathlib import Path

import duckdb
import httpx
import streamlit as st

from web_ui.core.constants import OPENALEX_BASE_URL


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
