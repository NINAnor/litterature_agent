"""Fetch papers from Arxiv matching AI categories + biodiversity/conservation keywords."""

import re
from datetime import date, datetime, timedelta

import arxiv

from paper_agent.models import Paper


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _matches_excluded_keywords(text: str, exclude_keywords: list[str]) -> bool:
    """Check if text contains any excluded keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in exclude_keywords)


def fetch_arxiv_papers(
    categories: list[str],
    keywords: list[str],
    exclude_keywords: list[str] | None = None,
    days: int = 3,
    max_results: int = 200,
) -> list[Paper]:
    """
    Search Arxiv for recent papers in the given categories that match
    biodiversity/conservation keywords in their title or abstract.

    Args:
        categories: Arxiv categories to search (e.g. ['cs.AI', 'cs.LG'])
        keywords: Keywords to filter by (e.g. ['biodiversity', 'conservation'])
        exclude_keywords: Keywords that, if present, cause a paper to be excluded
        days: How many days back to look
        max_results: Maximum results to fetch from Arxiv API per category

    Returns:
        List of Paper objects matching the criteria
    """
    exclude_keywords = exclude_keywords or []
    cutoff_date = date.today() - timedelta(days=days)
    papers: dict[str, Paper] = {}  # Deduplicate by arxiv ID

    # Build query: search across all categories
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    # Also add keyword terms to the query to narrow results from the API side
    keyword_query = " OR ".join(f'abs:"{kw}"' for kw in keywords[:5])  # Limit to avoid overly long queries
    query = f"({cat_query}) AND ({keyword_query})"

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    for result in client.results(search):
        # Check publication date
        pub_date = result.published.date()
        if pub_date < cutoff_date:
            continue

        # Double-check keyword match in title or abstract
        combined_text = f"{result.title} {result.summary}"
        if not _matches_keywords(combined_text, keywords):
            continue
        if exclude_keywords and _matches_excluded_keywords(combined_text, exclude_keywords):
            continue

        arxiv_id = result.entry_id.split("/abs/")[-1]

        paper = Paper(
            paper_id=f"arxiv:{arxiv_id}",
            title=result.title.strip().replace("\n", " "),
            authors=[a.name for a in result.authors],
            abstract=result.summary.strip().replace("\n", " "),
            url=result.entry_id,
            source="arxiv",
            published_date=pub_date,
            categories=[c for c in result.categories],
            fetched_at=datetime.now(),
        )
        papers[paper.paper_id] = paper

    return list(papers.values())
