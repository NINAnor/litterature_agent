"""Fetch papers from academic journals via the OpenAlex API."""

import asyncio
import httpx
from datetime import date, datetime, timedelta

from paper_agent.models import Paper


OPENALEX_BASE_URL = "https://api.openalex.org"


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """
    OpenAlex stores abstracts as inverted indexes: {"word": [positions...]}.
    Reconstruct the original abstract text from this format.
    """
    if not inverted_index:
        return ""

    # Find total length
    max_pos = 0
    for positions in inverted_index.values():
        if positions:
            max_pos = max(max_pos, max(positions))

    # Rebuild text
    words = [""] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word

    return " ".join(w for w in words if w)


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _matches_excluded_keywords(text: str, exclude_keywords: list[str]) -> bool:
    """Check if text contains any excluded keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in exclude_keywords)


def _parse_works(works: list[dict], journal_name: str) -> list[Paper]:
    """Parse a list of OpenAlex work dicts into Paper objects."""
    papers: dict[str, Paper] = {}
    for work in works:
        abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
        title = work.get("title", "")

        if not title:
            continue

        doi = work.get("doi", "")
        if doi and doi.startswith("https://doi.org/"):
            doi_id = doi
        elif doi:
            doi_id = f"https://doi.org/{doi}"
        else:
            doi_id = work.get("id", "")

        authors = []
        for authorship in work.get("authorships", []):
            name = authorship.get("author", {}).get("display_name", "")
            if name:
                authors.append(name)

        pub_date_str = work.get("publication_date", "")
        try:
            pub_date = date.fromisoformat(pub_date_str)
        except (ValueError, TypeError):
            pub_date = date.today()

        concepts = [c.get("display_name", "") for c in work.get("concepts", [])[:5]]

        paper_id = (
            f"doi:{doi.replace('https://doi.org/', '')}"
            if doi
            else f"openalex:{work.get('id', '').split('/')[-1]}"
        )

        paper = Paper(
            paper_id=paper_id,
            title=title.strip(),
            authors=authors,
            abstract=abstract,
            url=doi_id,
            source=journal_name,
            published_date=pub_date,
            categories=concepts,
            fetched_at=datetime.now(),
        )
        papers[paper.paper_id] = paper

    return list(papers.values())


async def _fetch_one_journal(
    client: httpx.AsyncClient,
    journal: dict,
    keywords: list[str],
    exclude_keywords: list[str],
    from_date: str,
    params_base: dict,
) -> list[Paper]:
    """Fetch and keyword-filter papers for a single journal."""
    issn = journal["issn"]
    journal_name = journal["name"]
    filter_str = f"primary_location.source.issn:{issn},from_publication_date:{from_date}"
    params = {
        **params_base,
        "filter": filter_str,
        "sort": "publication_date:desc",
        "select": "id,doi,title,authorships,abstract_inverted_index,publication_date,concepts,primary_location",
    }
    try:
        response = await client.get(f"{OPENALEX_BASE_URL}/works", params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, Exception) as e:
        print(f"  Warning: Failed to fetch from OpenAlex for {journal_name}: {e}")
        return []

    results = data.get("results", [])
    # Keyword filter
    matching = [
        w for w in results
        if _matches_keywords(f"{w.get('title', '')} {_reconstruct_abstract(w.get('abstract_inverted_index'))}", keywords)
        and not _matches_excluded_keywords(
            f"{w.get('title', '')} {_reconstruct_abstract(w.get('abstract_inverted_index'))}",
            exclude_keywords,
        )
    ]
    return _parse_works(matching, journal_name)


async def fetch_journal_papers(
    journals: list[dict],
    keywords: list[str],
    exclude_keywords: list[str] | None = None,
    days: int = 3,
    mailto: str = "",
) -> list[Paper]:
    """
    Fetch recent papers from all specified journals concurrently via OpenAlex,
    filtered by AI/ML keywords in title or abstract.

    Args:
        journals: List of dicts with 'name' and 'issn' keys
        keywords: AI/ML keywords to filter papers by
        exclude_keywords: Keywords that, if present, cause a paper to be excluded
        days: How many days back to look
        mailto: Email for OpenAlex polite pool (faster rate limits)

    Returns:
        List of Paper objects matching the criteria (deduplicated by paper_id)
    """
    exclude_keywords = exclude_keywords or []
    cutoff_date = date.today() - timedelta(days=days)
    from_date = cutoff_date.isoformat()

    params_base: dict = {"per_page": "50"}
    if mailto:
        params_base["mailto"] = mailto

    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_one_journal(client, journal, keywords, exclude_keywords, from_date, params_base)
            for journal in journals
        ]
        results = await asyncio.gather(*tasks)

    # Flatten and deduplicate by paper_id
    seen: dict[str, Paper] = {}
    for batch in results:
        for paper in batch:
            seen[paper.paper_id] = paper

    return list(seen.values())
