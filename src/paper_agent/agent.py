"""Pydantic AI agents for summarizing AI + biodiversity conservation papers."""

from dataclasses import dataclass, field

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from paper_agent.models import Paper, PaperSummary, HighlightsSummary


@dataclass
class AgentSkill:
    """
    Configuration for a single named agent skill, loaded from the `agents`
    section of config.yaml.

    Each skill maps to one agent in the pipeline. Skills can override model
    settings (temperature, max_tokens) independently of each other.
    """

    instructions: str
    model_settings: ModelSettings = field(default_factory=ModelSettings)


def skill_from_config(cfg: dict) -> AgentSkill:
    """
    Build an AgentSkill from a raw config dict (one entry under `agents:`).

    Supported keys:
        instructions (str)   - System prompt for the agent. Required.
        temperature  (float) - Sampling temperature override (0.0 – 1.0).
        max_tokens   (int)   - Maximum tokens to generate.

    Example config entry::

        agents:
          paper_summarizer:
            instructions: |
              You are a research assistant ...
            temperature: 0.2
            max_tokens: 512
    """
    # Only include model settings keys that are explicitly set in config,
    # so we don't override model defaults with None.
    model_settings_kwargs: dict = {}
    if (temp := cfg.get("temperature")) is not None:
        model_settings_kwargs["temperature"] = temp
    if (max_tok := cfg.get("max_tokens")) is not None:
        model_settings_kwargs["max_tokens"] = max_tok

    return AgentSkill(
        instructions=cfg.get("instructions", ""),
        model_settings=ModelSettings(**model_settings_kwargs),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_model(base_url: str, model_name: str, api_key: str) -> OpenAIChatModel:
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------

def create_paper_agent(
    base_url: str,
    model_name: str,
    api_key: str,
    skill: AgentSkill,
) -> Agent[None, PaperSummary]:
    """Agent that summarizes a single paper using the paper_summarizer skill."""
    return Agent(
        _make_model(base_url, model_name, api_key),
        output_type=PaperSummary,
        retries={"tools": 1, "output": 0},
        instructions=skill.instructions,
        model_settings=skill.model_settings,
    )


def create_highlights_agent(
    base_url: str,
    model_name: str,
    api_key: str,
    skill: AgentSkill,
) -> Agent[None, HighlightsSummary]:
    """Agent that picks highlights using the highlighter skill."""
    return Agent(
        _make_model(base_url, model_name, api_key),
        output_type=HighlightsSummary,
        instructions=skill.instructions,
        model_settings=skill.model_settings,
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_paper_prompt(paper: Paper, max_chars: int) -> str:
    """Build a concise prompt for a single paper."""
    abstract = paper.abstract
    if len(abstract) > max_chars:
        abstract = abstract[:max_chars].rsplit(" ", 1)[0] + "..."

    authors = ", ".join(paper.authors[:5])
    if len(paper.authors) > 5:
        authors += " et al."

    return (
        f"Title: {paper.title}\n"
        f"Authors: {authors}\n"
        f"Source: {paper.source} ({paper.published_date})\n"
        f"Paper ID: {paper.paper_id}\n"
        f"Abstract: {abstract}"
    )


def build_highlights_prompt(summaries: list[PaperSummary]) -> str:
    """Build a prompt for the highlights call from collected summaries."""
    lines = [
        f"Here are summaries of {len(summaries)} recent papers on AI and biodiversity conservation.",
        "Pick the 1-3 most noteworthy paper titles.",
        "",
    ]
    for s in summaries:
        lines.append(f"- {s.title}")
        lines.append(f"  Summary: {s.summary}")
        lines.append(f"  Methods: {', '.join(s.key_methods)}")
        lines.append(f"  Topics: {', '.join(s.conservation_topics)}")
        lines.append(f"  Relevance: {s.relevance_score:.2f}")
        lines.append("")

    return "\n".join(lines)
