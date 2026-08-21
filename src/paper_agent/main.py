"""CLI entrypoint for the paper agent — a configurable literature tracker."""

import argparse
import asyncio
import sys
from datetime import datetime, date
from pathlib import Path

import yaml

from paper_agent.agent import (
    create_paper_agent,
    create_highlights_agent,
    build_paper_prompt,
    build_highlights_prompt,
    skill_from_config,
)
from paper_agent.models import Paper, PaperSummary, DailySummary
from paper_agent.sources.openalex import fetch_journal_papers
from paper_agent.storage import PaperStorage


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    with open(path) as f:
        return yaml.safe_load(f)


def write_markdown_summary(
    summary: DailySummary,
    papers: list[Paper],
    output_dir: Path,
    run_date: date,
    report_title: str = "Literature Summary",
) -> Path:
    """Write the summary as a markdown file with Obsidian-friendly formatting."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{run_date.isoformat()}.md"

    paper_lookup = {p.paper_id: p for p in papers}

    lines = [
        "---",
        f"date: {run_date.isoformat()}",
        f"papers_reviewed: {len(summary.papers)}",
        "tags: [research, literature_summary, paper_agent]",
        "---",
        "",
        f"# \U0001f4c4 {report_title}",
        f"**\U0001f4c5 Date:** {run_date.isoformat()}",
        f"**\U0001f4ca Papers reviewed:** {len(summary.papers)}",
        "",
    ]

    if summary.highlights:
        lines += ["## \U0001f31f Highlights", ""]
        for highlight in summary.highlights:
            lines.append(f"- {highlight}")
        lines.append("")

    lines += ["## \U0001f4d6 Paper Summaries", ""]

    for ps in sorted(summary.papers, key=lambda p: p.relevance_score, reverse=True):
        paper_meta = paper_lookup.get(ps.paper_id)
        lines.append(f"### \U0001f4c4 {ps.title}")
        lines.append("")
        if paper_meta:
            lines.append(
                f"**\U0001f310 Source:** {paper_meta.source} | **\U0001f4c5 Date:** {paper_meta.published_date}"
            )
            authors = ", ".join(paper_meta.authors[:5])
            if len(paper_meta.authors) > 5:
                authors += " et al."
            lines.append(f"**\u270d\ufe0f Authors:** {authors}")
            lines.append(f"**\U0001f517 URL:** {paper_meta.url}")
        lines.append(f"**\U0001f3af Relevance:** {ps.relevance_score:.2f}")
        lines.append("")
        lines.append(ps.summary)
        lines.append("")
        if ps.methods:
            lines.append(f"**\U0001f6e0\ufe0f Methods:** {', '.join(ps.methods)}")
        if ps.topics:
            lines.append(f"**\U0001f33f Topics:** {', '.join(ps.topics)}")
        lines += ["", "---", ""]

    if filepath.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        filepath = output_dir / f"{run_date.isoformat()}_{timestamp}.md"

    filepath.write_text("\n".join(lines))
    return filepath


async def run(args: argparse.Namespace) -> None:
    """Main execution logic (async to support per-paper timeouts)."""
    config = load_config(args.config)

    settings = config.get("settings", {})
    agents_cfg = config.get("agents", {})
    data_dir = settings.get("data_dir", "data")
    days = args.days or settings.get("default_days", 3)
    timeout = args.timeout or settings.get("paper_timeout_seconds", 120)
    max_chars = settings.get("abstract_max_chars", 800)
    min_relevance = (
        args.min_relevance
        if args.min_relevance is not None
        else settings.get("min_relevance_score", 0.0)
    )

    storage = PaperStorage(data_dir=data_dir)

    print(f"Fetching papers from the last {days} days...")
    print(f"Total papers tracked so far: {storage.get_paper_count()}")
    print()

    # --- Fetch papers ---
    all_papers: list[Paper] = []

    # Shared keywords across both sources
    shared_keywords = config.get("keywords", [])
    shared_exclude_keywords = config.get("exclude_keywords", [])

    if args.source in ("all", "journals"):
        print("Searching journals via OpenAlex...")
        oa_cfg = config.get("openalex", {})
        journal_papers = await fetch_journal_papers(
            journals=config.get("journals", []),
            keywords=shared_keywords,
            exclude_keywords=shared_exclude_keywords,
            days=days,
            mailto=oa_cfg.get("mailto", ""),
        )
        print(f"  Found {len(journal_papers)} matching papers from journals")
        all_papers.extend(journal_papers)

    if not all_papers:
        print("\nNo papers found matching your criteria.")
        return

    # --- Deduplicate against storage ---
    if args.force:
        new_papers = all_papers
        print(
            f"\n--force: processing all {len(new_papers)} papers (including previously seen)"
        )
    else:
        new_papers = storage.filter_new_papers(all_papers)
        print(f"\n{len(new_papers)} new papers (out of {len(all_papers)} total found)")

    if not new_papers:
        print("No new papers to summarize. Use --force to re-process.")
        return

    # --- Summarize papers one by one with timeout ---
    model_cfg = config.get("model", {})
    model_kwargs = dict(
        base_url=model_cfg.get("base_url", "http://localhost:8087/v1"),
        model_name=model_cfg.get("model_name", "gemma4"),
        api_key=model_cfg.get("api_key", "not-needed"),
    )

    paper_agent = create_paper_agent(
        **model_kwargs,
        skill=skill_from_config(agents_cfg.get("paper_summarizer", {})),
    )
    highlights_agent = create_highlights_agent(
        **model_kwargs,
        skill=skill_from_config(agents_cfg.get("highlighter", {})),
    )

    print(f"\nSummarizing {len(new_papers)} papers (timeout: {timeout}s each)...")

    paper_summaries: list[PaperSummary] = []
    skipped = 0

    for i, paper in enumerate(new_papers, 1):
        title_preview = (
            paper.title[:65] + "..." if len(paper.title) > 65 else paper.title
        )
        print(f"  [{i}/{len(new_papers)}] {title_preview}", end="", flush=True)
        try:
            result = await asyncio.wait_for(
                paper_agent.run(build_paper_prompt(paper, max_chars)),
                timeout=timeout,
            )
            summary = result.output
            summary.paper_id = paper.paper_id
            paper_summaries.append(summary)
            print(f" (relevance: {summary.relevance_score:.2f})")
        except asyncio.TimeoutError:
            print(f" [timed out after {timeout}s, skipping]")
            skipped += 1
        except Exception as e:
            print(f" [failed: {e}]")
            skipped += 1

    if skipped:
        print(f"\n  {skipped} paper(s) skipped.")

    if not paper_summaries:
        print("No summaries generated.")
        return

    # --- Filter by relevance threshold ---
    if min_relevance > 0.0:
        before = len(paper_summaries)
        paper_summaries = [
            s for s in paper_summaries if s.relevance_score >= min_relevance
        ]
        dropped = before - len(paper_summaries)
        if dropped:
            print(
                f"\n  {dropped} paper(s) dropped below relevance threshold ({min_relevance:.2f})."
            )

    if not paper_summaries:
        print(
            "No summaries met the relevance threshold. Lower --min-relevance or adjust config."
        )
        return

    # --- Highlights call ---
    print("\nGenerating highlights...", end="", flush=True)
    try:
        highlights_result = await asyncio.wait_for(
            highlights_agent.run(build_highlights_prompt(paper_summaries)),
            timeout=timeout,
        )
        highlights = highlights_result.output.highlights
        print(" done.")
    except asyncio.TimeoutError:
        print(" [timed out, skipping]")
        highlights = []
    except Exception as e:
        print(f" [failed: {e}]")
        highlights = []

    merged_summary = DailySummary(
        papers=paper_summaries,
        highlights=highlights,
    )

    # --- Persist ---
    run_date = datetime.now()
    storage.store_papers(new_papers)
    storage.store_summaries(merged_summary.papers, run_date)
    storage.store_highlights(merged_summary.highlights, run_date)

    md_dir = Path(data_dir) / "summaries_md"
    report_title = settings.get("report_title", "Literature Summary")
    md_path = write_markdown_summary(
        merged_summary, new_papers, md_dir, run_date.date(), report_title
    )

    print(f"\nDone! Summary written to: {md_path}")
    print(f"Papers summarized: {len(paper_summaries)} / {len(new_papers)}")
    print(f"Total papers in database: {storage.get_paper_count()}")

    if merged_summary.highlights:
        print("\nHighlights:")
        for h in merged_summary.highlights:
            print(f"  - {h}")


def main():
    """Parse CLI arguments and run."""
    parser = argparse.ArgumentParser(
        prog="paper-agent",
        description="Configurable literature tracker for academic journals",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of days to look back (default: from config, usually 3)",
    )
    parser.add_argument(
        "--source",
        choices=["all", "journals"],
        default="all",
        help="Which sources to query (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process papers even if already seen",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Per-paper timeout in seconds (default: from config, usually 120)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=None,
        dest="min_relevance",
        help="Minimum relevance score to include in output (0.0-1.0, default: from config)",
    )
    parser.add_argument(
        "--list-journals",
        action="store_true",
        help="List monitored journals and exit",
    )

    args = parser.parse_args()

    if args.list_journals:
        config = load_config(args.config)
        print("Monitored journals:")
        for j in config.get("journals", []):
            print(f"  - {j['name']} (ISSN: {j['issn']})")
        return

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
