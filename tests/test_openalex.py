"""Offline tests for the literature-tracker OpenAlex engine.

The script lives inside the skill bundle and is stdlib-only, so we load it by
path via importlib and stub the single HTTP entry point (`_get`) — no network,
no third-party deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".agents"
    / "skills"
    / "literature-tracker"
    / "scripts"
    / "openalex.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("openalex_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses resolve the module correctly.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


oa = _load_module()


class Recorder:
    """Callable that records the params of the last _get call and returns a canned body."""

    def __init__(self, body=None):
        self.body = body or {"results": []}
        self.calls = []

    def __call__(self, path, params, mailto="", timeout=30.0):
        self.calls.append({"path": path, "params": params, "mailto": mailto})
        return self.body

    @property
    def last(self):
        return self.calls[-1]

    def filter_str(self):
        return self.last["params"]["filter"]


@pytest.fixture
def rec(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(oa, "_get", recorder)
    return recorder


# ---------------------------------------------------------------------------
# build_search — the bug fix
# ---------------------------------------------------------------------------


def test_build_search_uses_boolean_not_pipe_bang():
    value = oa.build_search(["deep learning", "segmentation"], ["review", "survey"])
    assert value == '("deep learning" OR segmentation) NOT (review OR survey)'
    # The old, broken filter-value operators must not appear.
    assert "|" not in value
    assert "!" not in value


def test_build_search_single_terms_no_parens():
    assert oa.build_search(["segmentation"], ["review"]) == "segmentation NOT review"


def test_build_search_keywords_only():
    assert oa.build_search(["a", "b"], []) == "(a OR b)"


def test_build_search_excludes_only():
    assert oa.build_search([], ["review"]) == "NOT review"


def test_build_search_empty():
    assert oa.build_search([], []) == ""


# ---------------------------------------------------------------------------
# fetch_papers — filter assembly
# ---------------------------------------------------------------------------


def test_fetch_default_quality_filters_and_no_issn(rec):
    oa.fetch_papers(
        keywords=["camera trap"],
        exclude_keywords=["review"],
        days=14,
        max_results=40,
        abstract_max_chars=1500,
    )
    filt = rec.filter_str()
    assert "is_oa:true" in filt
    assert "has_abstract:true" in filt
    assert "type:article" in filt
    assert "from_publication_date:" in filt
    # No journal scoping requested -> no ISSN filter.
    assert "primary_location.source.issn" not in filt
    # Exclusion is a server-side NOT, not the broken bang form.
    assert 'title_and_abstract.search:"camera trap" NOT review' in filt


def test_fetch_scopes_to_issn_and_topic(rec):
    oa.fetch_papers(
        keywords=["bioacoustics"],
        exclude_keywords=[],
        days=7,
        max_results=10,
        abstract_max_chars=1500,
        issns=["2041-210X", "2056-3485"],
        topic_ids=["T10199"],
    )
    filt = rec.filter_str()
    assert "primary_location.source.issn:2041-210X|2056-3485" in filt
    assert "topics.id:T10199" in filt


def test_fetch_toggles_disable_quality_filters(rec):
    oa.fetch_papers(
        keywords=["x"],
        exclude_keywords=[],
        days=7,
        max_results=10,
        abstract_max_chars=1500,
        open_access=False,
        require_abstract=False,
        types=[],
    )
    filt = rec.filter_str()
    assert "is_oa:true" not in filt
    assert "has_abstract:true" not in filt
    assert "type:" not in filt


# ---------------------------------------------------------------------------
# fetch_papers — sort selection
# ---------------------------------------------------------------------------


def test_relevance_sort_with_keywords(rec):
    oa.fetch_papers(
        keywords=["x"], exclude_keywords=[], days=7, max_results=5,
        abstract_max_chars=1500, sort="relevance",
    )
    assert rec.last["params"]["sort"] == "relevance_score:desc"


def test_relevance_sort_falls_back_to_date_without_search(rec):
    oa.fetch_papers(
        keywords=[], exclude_keywords=[], days=7, max_results=5,
        abstract_max_chars=1500, sort="relevance",
    )
    assert rec.last["params"]["sort"] == "publication_date:desc"


def test_explicit_date_sort(rec):
    oa.fetch_papers(
        keywords=["x"], exclude_keywords=[], days=7, max_results=5,
        abstract_max_chars=1500, sort="date",
    )
    assert rec.last["params"]["sort"] == "publication_date:desc"


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------


def test_reconstruct_abstract():
    inverted = {"Hello": [0], "world": [1], "again": [2]}
    assert oa.reconstruct_abstract(inverted) == "Hello world again"


def test_reconstruct_abstract_empty():
    assert oa.reconstruct_abstract(None) == ""


def test_parse_work_builds_paper_and_truncates_abstract():
    work = {
        "id": "https://openalex.org/W123",
        "doi": "10.1/abc",
        "title": "A Title",
        "authorships": [{"author": {"display_name": "Jane Doe"}}],
        "abstract_inverted_index": {"one": [0], "two": [1], "three": [2]},
        "publication_date": "2025-06-01",
        "concepts": [{"display_name": "Ecology"}],
    }
    paper = oa._parse_work(work, "Some Journal", abstract_max_chars=7)
    assert paper.paper_id == "doi:10.1/abc"
    assert paper.url == "https://doi.org/10.1/abc"
    assert paper.authors == ["Jane Doe"]
    assert paper.abstract.endswith("...")
    assert paper.source == "Some Journal"
    assert paper.categories == ["Ecology"]


def test_parse_work_drops_untitled():
    assert oa._parse_work({"title": "  "}, "J", 1500) is None


# ---------------------------------------------------------------------------
# topics mode
# ---------------------------------------------------------------------------


def test_search_topics_shapes_results(monkeypatch):
    body = {
        "results": [
            {
                "id": "https://openalex.org/T10199",
                "display_name": "Wildlife Ecology and Conservation",
                "works_count": 165192,
            }
        ]
    }
    monkeypatch.setattr(oa, "_get", Recorder(body))
    out = oa.search_topics("camera trap ecology")
    assert out == [
        {
            "topic_id": "T10199",
            "name": "Wildlife Ecology and Conservation",
            "works_count": 165192,
        }
    ]


def test_search_topics_empty_query_short_circuits(monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        return {"results": []}

    monkeypatch.setattr(oa, "_get", boom)
    assert oa.search_topics("   ") == []
    assert called["n"] == 0
