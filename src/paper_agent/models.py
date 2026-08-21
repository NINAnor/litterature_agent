"""Pydantic models for papers and summaries."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Paper(BaseModel):
    """A paper fetched from a journal via OpenAlex."""

    paper_id: str = Field(description="Unique identifier (DOI or OpenAlex ID)")
    title: str
    authors: list[str]
    abstract: str
    url: str = Field(description="Link to the paper (DOI URL)")
    source: str = Field(description="Where the paper was found: journal name")
    published_date: date
    categories: list[str] = Field(
        default_factory=list, description="Journal subject areas"
    )
    fetched_at: datetime = Field(default_factory=datetime.now)


class PaperSummary(BaseModel):
    """LLM-generated summary for a single paper."""

    paper_id: str = ""
    title: str
    summary: str = Field(description="2-3 sentence summary of the paper's contribution")
    relevance_score: float = Field(
        ge=0,
        le=1,
        description="How relevant this paper is to the configured research topic (0=not relevant, 1=highly relevant)",
    )
    methods: list[str] = Field(
        default_factory=list, description="Key methods or techniques used in the paper"
    )
    topics: list[str] = Field(
        default_factory=list, description="Research topics addressed by the paper"
    )


class HighlightsSummary(BaseModel):
    """LLM-generated highlights across a batch of papers."""

    highlights: list[str] = Field(
        description="1-3 paper titles that stand out as particularly noteworthy"
    )


class DailySummary(BaseModel):
    """Complete summary for a run: individual paper summaries + highlights."""

    papers: list[PaperSummary]
    highlights: list[str] = Field(default_factory=list)
