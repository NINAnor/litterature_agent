#!/usr/bin/env python3
"""OpenAlex fetch engine for the literature-tracker skill.

Stdlib-only (no third-party dependencies) so it runs in any Python 3.9+
environment without an install step. Three modes:

  search  Resolve a journal name to its ISSN(s) via the OpenAlex /sources
          endpoint. Use this to confirm which journals to poll.

  topics  Resolve a topic phrase to OpenAlex topic ID(s) via the /topics
          endpoint. Best-effort: topic search is unreliable for arbitrary
          phrases, so treat misses as "just use keywords instead".

  fetch   Fetch recent works via the OpenAlex /works endpoint. Journals
          (--issn) and topics (--topic-id) are both optional: with neither,
          the search runs across all of OpenAlex, filtered by keywords, date,
          open access, abstract availability and work type. Results are
          printed as JSON for the calling model to summarize.

Output is always JSON on stdout so the host model can read it directly.

Examples:
  python openalex.py search --query "Methods in Ecology"
  python openalex.py topics --query "camera trap ecology"
  python openalex.py fetch --keywords "camera trap" bioacoustics \
      --exclude review survey --days 14 --max 40
  python openalex.py fetch --issn 2041-210X --keywords "deep learning" \
      --sort date --no-open-access
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

OPENALEX_BASE_URL = "https://api.openalex.org"
USER_AGENT = "literature-tracker-skill/1.0"


@dataclass
class Paper:
    """A single work fetched from OpenAlex."""

    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    source: str
    published_date: str
    categories: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _get(path: str, params: dict, mailto: str = "", timeout: float = 30.0) -> dict:
    """GET an OpenAlex endpoint and return the parsed JSON body."""
    if mailto:
        params = {**params, "mailto": mailto}
    query = urllib.parse.urlencode(params)
    url = f"{OPENALEX_BASE_URL}/{path}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Rebuild abstract text from OpenAlex's inverted-index format.

    OpenAlex stores abstracts as {"word": [positions, ...]}. This is the one
    piece of real logic a language model can't reliably do by hand.
    """
    if not inverted_index:
        return ""
    max_pos = -1
    for positions in inverted_index.values():
        for pos in positions:
            if pos > max_pos:
                max_pos = pos
    if max_pos < 0:
        return ""
    words = [""] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(w for w in words if w)


def _parse_work(work: dict, journal_name: str, abstract_max_chars: int) -> Paper | None:
    title = (work.get("title") or "").strip()
    if not title:
        return None

    doi = work.get("doi") or ""
    if doi and not doi.startswith("http"):
        doi = f"https://doi.org/{doi}"

    if doi:
        paper_id = f"doi:{doi.replace('https://doi.org/', '')}"
        url = doi
    else:
        oa_id = work.get("id", "")
        paper_id = f"openalex:{oa_id.rsplit('/', 1)[-1]}" if oa_id else oa_id
        url = oa_id

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in work.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]

    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    if abstract_max_chars and len(abstract) > abstract_max_chars:
        abstract = abstract[:abstract_max_chars].rsplit(" ", 1)[0] + "..."

    categories = [
        c.get("display_name", "")
        for c in (work.get("concepts") or [])[:5]
        if c.get("display_name")
    ]

    return Paper(
        paper_id=paper_id,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        source=journal_name,
        published_date=work.get("publication_date", ""),
        categories=categories,
    )


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------


def _quote_term(term: str) -> str:
    term = term.strip()
    return f'"{term}"' if " " in term else term


def build_search(keywords: list[str], exclude_keywords: list[str]) -> str:
    """Build an OpenAlex `title_and_abstract.search` value.

    OpenAlex parses this field with Lucene-style boolean operators. Terms MUST
    be combined with uppercase ``OR`` / ``NOT`` and grouped with parentheses.

    Note: the ``|`` (OR) and ``!`` (NOT) operators used in *filter values*
    (e.g. ``type:a|b``) do NOT work here — inside a text search a leading
    ``!`` is silently dropped, turning an intended exclusion into a *required*
    term. That bug is exactly what this function avoids.
    """
    parts: list[str] = []
    if keywords:
        inc = " OR ".join(_quote_term(k) for k in keywords)
        parts.append(f"({inc})" if len(keywords) > 1 else inc)
    if exclude_keywords:
        exc = " OR ".join(_quote_term(k) for k in exclude_keywords)
        parts.append(f"NOT ({exc})" if len(exclude_keywords) > 1 else f"NOT {exc}")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def search_journals(query: str, mailto: str = "", per_page: int = 10) -> list[dict]:
    """Search OpenAlex /sources for journals matching `query`."""
    if not query.strip():
        return []
    data = _get(
        "sources",
        {
            "search": query,
            "per_page": per_page,
            "filter": "type:journal",
            "select": "display_name,issn_l,issn,works_count",
        },
        mailto=mailto,
    )
    results = []
    for r in data.get("results", []):
        name = r.get("display_name")
        issn = r.get("issn_l") or (r.get("issn") or [None])[0]
        if name and issn:
            results.append(
                {"name": name, "issn": issn, "works_count": r.get("works_count", 0)}
            )
    return results


def search_topics(query: str, mailto: str = "", per_page: int = 10) -> list[dict]:
    """Search OpenAlex /topics for topics matching `query`.

    Best-effort: OpenAlex topic search misses on many natural phrases, so an
    empty result just means "fall back to keyword search".
    """
    if not query.strip():
        return []
    data = _get(
        "topics",
        {
            "search": query,
            "per_page": per_page,
            "select": "id,display_name,description,works_count",
        },
        mailto=mailto,
    )
    results = []
    for r in data.get("results", []):
        oa_id = r.get("id", "")
        topic_id = oa_id.rsplit("/", 1)[-1] if oa_id else ""
        name = r.get("display_name")
        if topic_id and name:
            results.append(
                {
                    "topic_id": topic_id,
                    "name": name,
                    "works_count": r.get("works_count", 0),
                }
            )
    return results


def fetch_papers(
    keywords: list[str],
    exclude_keywords: list[str],
    days: int,
    max_results: int,
    abstract_max_chars: int,
    issns: list[str] | None = None,
    topic_ids: list[str] | None = None,
    open_access: bool = True,
    require_abstract: bool = True,
    types: list[str] | None = None,
    sort: str = "relevance",
    mailto: str = "",
) -> list[Paper]:
    """Fetch recent works from OpenAlex /works.

    Journals (`issns`) and topics (`topic_ids`) are optional scoping filters.
    With neither, the search spans all of OpenAlex. Keyword filtering is done
    on the OpenAlex side via `title_and_abstract.search` (see `build_search`).
    """
    issns = issns or []
    topic_ids = topic_ids or []
    # None -> default to articles; an explicit empty list means "all types".
    types = ["article"] if types is None else types

    from_date = (date.today() - timedelta(days=days)).isoformat()
    filters = [f"from_publication_date:{from_date}"]

    if issns:
        filters.append(f"primary_location.source.issn:{'|'.join(issns)}")
    if topic_ids:
        filters.append(f"topics.id:{'|'.join(topic_ids)}")
    if open_access:
        filters.append("is_oa:true")
    if require_abstract:
        filters.append("has_abstract:true")
    if types:
        filters.append(f"type:{'|'.join(types)}")

    search_value = build_search(keywords, exclude_keywords)
    if search_value:
        filters.append(f"title_and_abstract.search:{search_value}")

    # relevance_score is only populated when a text search is present.
    if sort == "relevance" and search_value:
        sort_param = "relevance_score:desc"
    else:
        sort_param = "publication_date:desc"

    data = _get(
        "works",
        {
            "filter": ",".join(filters),
            "sort": sort_param,
            "per_page": min(max(max_results, 1), 200),
            "select": (
                "id,doi,title,authorships,abstract_inverted_index,"
                "publication_date,concepts,primary_location"
            ),
        },
        mailto=mailto,
    )

    papers: dict[str, Paper] = {}
    for work in data.get("results", []):
        loc = work.get("primary_location") or {}
        src = loc.get("source") or {}
        journal_name = src.get("display_name") or "Unknown journal"

        paper = _parse_work(work, journal_name, abstract_max_chars)
        if paper is None:
            continue
        papers[paper.paper_id] = paper
        if len(papers) >= max_results:
            break

    return list(papers.values())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_json(payload) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openalex.py",
        description="Fetch journals, topics and papers from OpenAlex for the literature-tracker skill.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    def _add_mailto(p):
        p.add_argument("--mailto", default="", help="Email for the OpenAlex polite pool")

    p_search = sub.add_parser("search", help="Resolve a journal name to ISSN(s)")
    p_search.add_argument("--query", required=True, help="Journal name to search for")
    p_search.add_argument("--max", type=int, default=10, dest="max_results")
    _add_mailto(p_search)

    p_topics = sub.add_parser("topics", help="Resolve a topic phrase to topic ID(s)")
    p_topics.add_argument("--query", required=True, help="Topic phrase to search for")
    p_topics.add_argument("--max", type=int, default=10, dest="max_results")
    _add_mailto(p_topics)

    p_fetch = sub.add_parser("fetch", help="Fetch recent papers from OpenAlex")
    p_fetch.add_argument(
        "--issn",
        nargs="*",
        default=[],
        help="Optional journal ISSNs to scope to (omit to search all journals)",
    )
    p_fetch.add_argument(
        "--topic-id",
        nargs="*",
        default=[],
        dest="topic_ids",
        help="Optional OpenAlex topic IDs (e.g. T10199) to scope to",
    )
    p_fetch.add_argument(
        "--keywords",
        nargs="*",
        default=[],
        help="Keywords (a paper must match at least one); OpenAlex-side OR filter",
    )
    p_fetch.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        dest="exclude_keywords",
        help="Keywords that exclude a paper if present (server-side NOT)",
    )
    p_fetch.add_argument("--days", type=int, default=7, help="How many days back to look")
    p_fetch.add_argument(
        "--max", type=int, default=40, dest="max_results", help="Max papers to return"
    )
    p_fetch.add_argument(
        "--sort",
        choices=["relevance", "date"],
        default="relevance",
        help="Sort by relevance to keywords (default) or publication date",
    )
    p_fetch.add_argument(
        "--open-access",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restrict to open-access works (default: on; use --no-open-access to disable)",
    )
    p_fetch.add_argument(
        "--require-abstract",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only return works that have an abstract (default: on)",
    )
    p_fetch.add_argument(
        "--types",
        nargs="*",
        default=["article"],
        help="OpenAlex work types to include (default: article; pass nothing to allow all)",
    )
    p_fetch.add_argument(
        "--abstract-max-chars",
        type=int,
        default=1500,
        help="Truncate abstracts to protect the host model's context (0 = no limit)",
    )
    _add_mailto(p_fetch)

    args = parser.parse_args(argv)

    try:
        if args.mode == "search":
            results = search_journals(args.query, mailto=args.mailto, per_page=args.max_results)
            _print_json(results)
        elif args.mode == "topics":
            results = search_topics(args.query, mailto=args.mailto, per_page=args.max_results)
            _print_json(results)
        elif args.mode == "fetch":
            papers = fetch_papers(
                keywords=args.keywords,
                exclude_keywords=args.exclude_keywords,
                days=args.days,
                max_results=args.max_results,
                abstract_max_chars=args.abstract_max_chars,
                issns=args.issn,
                topic_ids=args.topic_ids,
                open_access=args.open_access,
                require_abstract=args.require_abstract,
                types=args.types,
                sort=args.sort,
                mailto=args.mailto,
            )
            _print_json([asdict(p) for p in papers])
    except urllib.error.HTTPError as e:
        print(f"OpenAlex HTTP error {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Network error contacting OpenAlex: {e.reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
