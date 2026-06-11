"""DuckDB + Parquet storage for tracking papers and summaries."""

from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd

from paper_agent.models import Paper, PaperSummary


class PaperStorage:
    """Manages paper and summary persistence using DuckDB and Parquet files."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "summaries_md").mkdir(exist_ok=True)

        self.papers_path = self.data_dir / "papers.parquet"
        self.summaries_path = self.data_dir / "summaries.parquet"

    def get_seen_paper_ids(self) -> set[str]:
        """Return the set of paper IDs already stored."""
        if not self.papers_path.exists():
            return set()

        con = duckdb.connect()
        try:
            result = con.execute(
                f"SELECT paper_id FROM '{self.papers_path}'"
            ).fetchall()
            return {row[0] for row in result}
        finally:
            con.close()

    def filter_new_papers(self, papers: list[Paper]) -> list[Paper]:
        """Return only papers that haven't been seen before."""
        seen_ids = self.get_seen_paper_ids()
        return [p for p in papers if p.paper_id not in seen_ids]

    def store_papers(self, papers: list[Paper]) -> None:
        """Append new papers to the parquet file."""
        if not papers:
            return

        new_df = pd.DataFrame([p.model_dump() for p in papers])
        # Convert date/datetime columns for parquet compatibility
        new_df["published_date"] = pd.to_datetime(new_df["published_date"])
        new_df["fetched_at"] = pd.to_datetime(new_df["fetched_at"])

        con = duckdb.connect()
        try:
            if self.papers_path.exists():
                existing = con.execute(
                    f"SELECT * FROM '{self.papers_path}'"
                ).df()
                combined = pd.concat([existing, new_df], ignore_index=True)
                combined = combined.drop_duplicates(subset=["paper_id"], keep="last")
            else:
                combined = new_df

            con.execute(
                f"COPY combined TO '{self.papers_path}' (FORMAT PARQUET)"
            )
        finally:
            con.close()

    def store_summaries(self, summaries: list[PaperSummary], run_date: datetime) -> None:
        """Append new summaries to the summaries parquet file."""
        if not summaries:
            return

        records = []
        for s in summaries:
            record = s.model_dump()
            record["run_date"] = run_date
            records.append(record)

        new_df = pd.DataFrame(records)
        new_df["run_date"] = pd.to_datetime(new_df["run_date"])

        con = duckdb.connect()
        try:
            if self.summaries_path.exists():
                existing = con.execute(
                    f"SELECT * FROM '{self.summaries_path}'"
                ).df()
                combined = pd.concat([existing, new_df], ignore_index=True)
            else:
                combined = new_df

            con.execute(
                f"COPY combined TO '{self.summaries_path}' (FORMAT PARQUET)"
            )
        finally:
            con.close()

    def get_recent_summaries(self, days: int = 7) -> pd.DataFrame:
        """Query recent summaries from parquet."""
        if not self.summaries_path.exists():
            return pd.DataFrame()

        con = duckdb.connect()
        try:
            return con.execute(f"""
                SELECT * FROM '{self.summaries_path}'
                WHERE run_date >= CURRENT_DATE - INTERVAL '{days} days'
                ORDER BY run_date DESC, relevance_score DESC
            """).df()
        finally:
            con.close()

    def get_paper_count(self) -> int:
        """Return total number of papers tracked."""
        if not self.papers_path.exists():
            return 0

        con = duckdb.connect()
        try:
            result = con.execute(
                f"SELECT COUNT(*) FROM '{self.papers_path}'"
            ).fetchone()
            return result[0] if result else 0
        finally:
            con.close()
