# Paper Agent 📄🌱

An AI-powered agent that automatically tracks and summarizes the latest scientific literature for any research topic. Point it at your own keywords, journals, and prompts to track whatever field you're interested in — no code changes required.

Built with [Pydantic AI](https://ai.pydantic.dev/), this agent performs targeted searches on **Open Access journals** (via OpenAlex) to deliver structured, high-quality research summaries. It ships with a **Streamlit web UI** for configuring, running, and browsing results, in addition to the CLI.

## 🔄 Workflow

The agent follows a robust pipeline to ensure high-quality, low-noise research reports:

1.  **Discovery**: The agent queries Open Access journals (via OpenAlex API) for recent publications.
2.  **Deduplication**: It compares discovered papers against the local `papers.parquet` database to ensure only new, unseen research is processed.
3.  **Summarization**: For every new paper, an AI agent analyzes the abstract to produce a structured summary and assigns a relevance score.
4.  **Curation**: Papers with relevance scores below your configured threshold are filtered out to maintain a high signal-to-noise ratio.
5.  **Synthesis**: A secondary agent reviews the curated summaries to extract high-level research trends and key highlights.
6.  **Reporting**: The final results are persisted in columnar Parquet format and a human-readable Markdown report is generated.

## ✨ Features

- 🌍 **Fully Configurable**: Not tied to any one research domain — set your own keywords, journals, and agent prompts in `config.yaml`.
- 🖥️ **Web UI**: A Streamlit app to configure keywords/journals/model settings, trigger runs, and browse summaries and highlights — no need to touch YAML directly.
- 🤖 **Local-First AI**: Optimized to run against local LLMs (e.g. via [llama.cpp](https://github.com/ggerganov/llama.cpp) or [OpenWebUI](https://github.com/open-webui/open-webui)) using OpenAI-compatible APIs.
- 🔍 **OpenAlex Search**: Monitors journals of your choice, with an in-app journal search (by name) to find ISSNs and add them with one click.
- ⚡ **High Performance**: Uses `uv` for lightning-fast environment management and dependency resolution.
- 📊 **Structured Data**: Stores all discovered papers, summaries, and run highlights in **DuckDB + Parquet** for fast, columnar analysis.
- ⏱️ **Resilient Execution**: Includes per-paper timeouts to prevent a single slow LLM response from stalling the entire process.
- 📝 **Clean Reporting**: Generates beautifully formatted Markdown summaries with trends and research highlights.
- 🐳 **Docker-ready**: Ships with a `Dockerfile` and `docker-compose.yml` for both the web UI and a local `llama.cpp` GPU inference server.

## 📂 Project Structure

```text
.
├── config.yaml            # Your personal configuration (gitignored - not committed)
├── config.example.yaml    # Template to copy to config.yaml when setting up
├── .streamlit/
│   └── config.toml         # Streamlit theme (colors, branding)
├── paper_summaries/        # Local storage for papers, summaries, and generated reports
│   ├── papers.parquet       # Metadata for all discovered papers
│   ├── summaries.parquet    # LLM-generated summaries and scores
│   ├── highlights.parquet   # Per-run highlight selections
│   └── summaries_md/        # Human-readable Markdown reports
├── src/paper_agent/        # CLI agent source code
│   ├── main.py               # CLI entrypoint and workflow orchestration
│   ├── agent.py              # AI agent definitions and skill loading
│   ├── models.py             # Data models (Pydantic)
│   ├── storage.py            # Local data persistence (DuckDB/Parquet)
│   └── sources/               # Data fetching logic (OpenAlex)
└── src/web_ui/              # Streamlit web UI
    ├── app.py                 # Main UI (Settings, Run, summaries browser)
    ├── main.py                # Launcher (`uv run paper-agent-ui`)
    ├── assets/                # Logo/branding assets
    ├── Dockerfile
    └── docker-compose.yml     # Web UI + local llama.cpp GPU server
```

## 🛠️ Installation

### Prerequisites

- [Python 3.10+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (recommended package manager)
- A local LLM server (e.g., [llama.cpp](https://github.com/ggerganov/llama.cpp) or any OpenAI-compatible endpoint like [OpenWebUI](https://github.com/open-webui/open-webui))

### Setup

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd paper-agent
    ```

2.  Install the package and dependencies:
    ```bash
    uv sync
    ```

3.  Copy the example config and customize it for your research topic:
    ```bash
    cp config.example.yaml config.yaml
    ```
    `config.yaml` is gitignored — it's your personal config (keywords, journals, model endpoint) and won't be committed. See [Configuration](#️-configuration) below.

## 🖥️ Web UI

The easiest way to configure and run the agent is via the Streamlit UI:

```bash
uv run paper-agent-ui
```

This starts a local server at `http://localhost:8501` where you can:

- **Browse summaries**: pick a run from the sidebar (or "All") to see its papers, highlights, methods, and topics
- **Search journals**: look up journals by name via OpenAlex and add them with one click (no need to know ISSNs)
- **Edit keywords**: add/remove keywords and exclude-keywords as chips
- **Configure the model**: point at any OpenAI-compatible endpoint, with a built-in "Test connection" button
- **Trigger runs**: run the agent directly from the UI and see its output inline

Alternatively, run it directly with Streamlit:
```bash
uv run streamlit run src/web_ui/app.py
```

### Running with Docker

```bash
docker compose -f src/web_ui/docker-compose.yml up
```

This starts both the web UI (port `8501`) and a local GPU-accelerated `llama.cpp` server (port `8087`) that the agent can use as its model backend — see `src/web_ui/docker-compose.yml` to change the model or GPU settings.

## 🚀 CLI Usage

The agent is also a CLI tool. You can run it using `uv run`.

### Basic Run

Summarize papers from the last 3 days (default):
```bash
uv run paper-agent
```

### Customizing the Search

```bash
# Look back further (e.g., last 7 days)
uv run paper-agent --days 7

# Search only Open Access journals
uv run paper-agent --source journals

# Re-process papers even if already seen (useful for testing)
uv run paper-agent --force

# Only include papers with relevance score >= 0.8
uv run paper-agent --min-relevance 0.8
```

### Managing Journals

To see which journals the agent is currently monitoring:
```bash
uv run paper-agent --list-journals
```

## 🌍 Customizing for Different Domains

This agent isn't tied to any single research domain. To adapt it to your own field (e.g. **Fish Conservation**, **Climate Modeling**, **Publication Statistics**, etc.), either use the web UI's Settings panel, or edit `config.yaml` directly:

- **Keywords**: Update `keywords` with terms relevant to your topic. Papers must match at least one to be considered.
- **Exclude keywords**: Terms that, if present, cause a paper to be dropped even if it matched a keyword above (e.g. `review`, `survey`, `tutorial`).
- **Journals**: Add relevant journals to the `journals` list with their ISSNs — use the web UI's journal search to find these easily, or add them manually.
- **Agent prompts**: If you want the AI to adopt a specific persona or focus on nuances of your field, update the `instructions` in the `agents` block. The default prompts are already domain-agnostic (they reference "the research topic described by the keywords in this configuration" rather than any specific field).

See `config.example.yaml` for a ready-to-copy template with placeholder values.

## ⚙️ Configuration

All settings are managed in `config.yaml` (copy `config.example.yaml` to get started — see [Installation](#️-installation)).

```yaml
keywords:
  - your keyword here
  - another keyword

exclude_keywords:
  - review
  - survey
  - tutorial

journals:
  - name: Methods in Ecology and Evolution
    issn: "2041-210X"
  - name: Ecological Informatics
    issn: "1574-9541"

openalex:
  mailto: "your-email@example.com" # Recommended for OpenAlex polite pool

model:
  base_url: "http://localhost:8087/v1"
  model_name: "your-model-name"
  api_key: "not-needed"  # pragma: allowlist secret

settings:
  default_days: 3
  data_dir: "./paper_summaries/"
  paper_timeout_seconds: 60  # Max time to wait per paper summary
  abstract_max_chars: 800    # Truncate abstracts sent to the model
  min_relevance_score: 0.7   # Drop papers below this score from the report
  report_title: "Literature Summary"  # Title shown in the generated markdown report

agents:
  paper_summarizer:
    instructions: |
      You are a research assistant ...  # full system prompt
    temperature: 0.2    # low for consistent factual summaries
    # max_tokens: 512   # optional

  highlighter:
    instructions: |
      You are a research assistant ...  # highlight selection prompt
    temperature: 0.5    # slightly higher for discernment
```

Agent behaviour is fully configured in `config.yaml` under the `agents` block — no code changes needed. To add a new agent skill, add a new key under `agents` and wire it up in `agent.py` using `skill_from_config`.

## 🛠️ Development

To run tests:
```bash
uv run pytest
```

To run linting/formatting/dependency checks (same checks as CI):
```bash
uvx prek run --all-files
```

To add new journals, either use the web UI's journal search, or append them to the `journals` list in `config.yaml` using their ISSN.

## Notes

- **Choose a model with strong function calling**: pydantic-ai uses OpenAI-style **tool/function calling** to extract structured summaries (JSON with specific fields like `relevance_score`, `methods`, `topics`). The model must respond with a valid `tool_calls` payload, not just plain text. Many models (especially quantized ones) struggle with this format — they may return wrong types (string instead of number for `relevance_score`), omit required fields, or produce malformed JSON. Each failure triggers an automatic retry, which can lead to timeouts and skipped papers. Models from the **Qwen** and **DeepSeek** families are known for reliable function calling even at low quantization levels.

- **Use a low temperature for structured output**: Function calling is inherently deterministic and the model should pick from a constrained set of fields and types. A high temperature (`--temp 1.0`) makes the model more "creative," which often means it invents field names, returns unexpected types, or ignores the tool schema entirely. For reliable structured output, keep `--temp ≤ 0.3` on the server side. The agent-side `temperature: 0.2` in `config.yaml` only controls pydantic-ai's request — it doesn't override the server flag if you pass `--temp 1.0` at launch.
