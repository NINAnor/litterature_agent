"""DuckDB + Parquet storage for tracking papers and summaries.

`data_dir` may be a local filesystem path, or an `s3://bucket/prefix` URI —
in the latter case, parquet files are read/written directly on S3 via
DuckDB's `httpfs` extension (see `paper_agent.s3_storage`).
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from paper_agent.models import Paper, PaperSummary
from paper_agent.s3_storage import connect, is_s3_uri, join, object_exists


class PaperStorage:
    """Manages paper and summary persistence using DuckDB and Parquet files."""

    def __init__(self, data_dir: str = "data"):
        self.is_s3 = is_s3_uri(data_dir)
        self.data_dir = str(data_dir).rstrip("/") if self.is_s3 else Path(data_dir)

        if not self.is_s3:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            (self.data_dir / "summaries_md").mkdir(exist_ok=True)
            self.papers_path = self.data_dir / "papers.parquet"
            self.summaries_path = self.data_dir / "summaries.parquet"
            self.highlights_path = self.data_dir / "highlights.parquet"
        else:
            self.papers_path = join(self.data_dir, "papers.parquet")
            self.summaries_path = join(self.data_dir, "summaries.parquet")
            self.highlights_path = join(self.data_dir, "highlights.parquet")

    def _connect(self):
        return connect(str(self.data_dir))

    def _exists(self, path) -> bool:
        return object_exists(str(path))

    def _append_parquet(
        self, path, new_df: pd.DataFrame, dedupe_subset: list[str] | None = None
    ) -> None:
        """Append `new_df` to the parquet file at `path` (creating it if it
        doesn't exist yet), optionally dropping duplicates on `dedupe_subset`.
        """
        con = self._connect()
        try:
            if self._exists(path):
                existing = con.execute(f"SELECT * FROM '{path}'").df()
                combined = pd.concat([existing, new_df], ignore_index=True)
                if dedupe_subset:
                    combined = combined.drop_duplicates(
                        subset=dedupe_subset, keep="last"
                    )
            else:
                combined = new_df  # noqa: F841 - referenced by name in the SQL string below

            con.execute(f"COPY combined TO '{path}' (FORMAT PARQUET)")
        finally:
            con.close()

    def get_seen_paper_ids(self) -> set[str]:
        """Return the set of paper IDs already stored."""
        if not self._exists(self.papers_path):
            return set()

        con = self._connect()
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
        """Append new papers to the parquet file, deduplicated by paper_id."""
        if not papers:
            return

        new_df = pd.DataFrame([p.model_dump() for p in papers])
        # Convert date/datetime columns for parquet compatibility
        new_df["published_date"] = pd.to_datetime(new_df["published_date"])
        new_df["fetched_at"] = pd.to_datetime(new_df["fetched_at"])

        self._append_parquet(self.papers_path, new_df, dedupe_subset=["paper_id"])

    def store_summaries(
        self, summaries: list[PaperSummary], run_date: datetime
    ) -> None:
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

        self._append_parquet(self.summaries_path, new_df)

    def store_highlights(self, highlights: list[str], run_date: datetime) -> None:
        """Append this run's highlights to the highlights parquet file."""
        if not highlights:
            return

        new_df = pd.DataFrame({"highlight": highlights})
        new_df["run_date"] = pd.to_datetime(run_date)

        self._append_parquet(self.highlights_path, new_df)

    def get_paper_count(self) -> int:
        """Return total number of papers tracked."""
        if not self._exists(self.papers_path):
            return 0

        con = self._connect()
        try:
            result = con.execute(
                f"SELECT COUNT(*) FROM '{self.papers_path}'"
            ).fetchone()
            return result[0] if result else 0
        finally:
            con.close()
