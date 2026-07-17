# Paper Agent 📄🌱

An AI-powered agent designed to automatically track and summarize the latest scientific literature at the intersection of **Artificial Intelligence** and **Biodiversity Conservation**.

Built with [Pydantic AI](https://ai.pydantic.dev/), this agent performs targeted searches on **Open Access journals** (via OpenAlex) to deliver structured, high-quality research summaries.

## 🔄 Workflow

The agent follows a robust pipeline to ensure high-quality, low-noise research reports:

1.  **Discovery**: The agent queries Open Access journals (via OpenAlex API) for recent publications.
2.  **Deduplication**: It compares discovered papers against the local `papers.parquet` database to ensure only new, unseen research is processed.
3.  **Summarization**: For every new paper, an AI agent analyzes the abstract to produce a structured summary and assigns a relevance score.
4.  **Curation**: Papers with relevance scores below your configured threshold are filtered out to maintain a high signal-to-noise ratio.
5.  **Synthesis**: A secondary agent reviews the curated summaries to extract high-level research trends and key highlights.
6.  **Reporting**: The final results are persisted in columnar Parquet format and a human-readable Markdown report is generated.

## ✨ Features

- 🤖 **Local-First AI**: Optimized to run against local LLMs (like Gemma 4 via llama.cpp) using OpenAI-compatible APIs.
- 🔍 **OpenAlex Search**: Monitors high-impact journals (e.g., *Methods in Ecology and Evolution*) using the OpenAlex API.
- ⚡ **High Performance**: Uses `uv` for lightning-fast environment management and dependency resolution.
- 📊 **Structured Data**: Stores all discovered papers and summaries in **DuckDB + Parquet** for fast, columnar analysis.
- ⏱️ **Resilient Execution**: Includes per-paper timeouts to prevent a single slow LLM response from stalling the entire process.
- 📝 **Clean Reporting**: Generates beautifully formatted Markdown summaries with trends and research highlights.

## 📂 Project Structure

```text
.
├── config.yaml          # Central configuration for models, agents, and search criteria
├── data/                # Local storage for papers, summaries, and generated reports
│   ├── papers.parquet    # Metadata for all discovered papers
│   ├── summaries.parquet # LLM-generated summaries and scores
│   └── summaries_md/   # Human-readable Markdown reports
└── src/paper_agent/     # Main source code
    ├── main.py          # CLI entrypoint and workflow orchestration
    ├── agent.py         # AI agent definitions and skill loading
    ├── models.py         # Data models (Pydantic)
    ├── storage.py       # Local data persistence (DuckDB/Parquet)
    └── sources/         # Data fetching logic (OpenAlex)
```

## 🛠️ Installation

### Prerequisites

- [Python 3.10+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (recommended package manager)
- A local LLM server (e.g., [llama.cpp](https://github.com/ggerganov/llama.cpp) or Ollama) running an OpenAI-compatible API.

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

3.  Configure your local model in `config.yaml` (see Configuration below).

## 🚀 Usage

The agent is a CLI tool. You can run it using `uv run`.

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

You can easily adapt this agent to any research area (e.g., **Fish Conservation**, **Climate Modeling**, etc.) by modifying `config.yaml`:

- **Keywords**: Update `keywords` with domain-specific terms.
- **Journals**: Add relevant journals to the `journals` list with their ISSNs.
- **Agent Expertise**: If you want the AI to adopt a specific persona or focus on specific nuances of a new field, update the `instructions` in the `agents` block.

## ⚙️ Configuration

All settings are managed in `config.yaml`.

```yaml
journals:
  - name: Methods in Ecology and Evolution
    issn: "2041-210X"
  - name: Ecological Informatics
    issn: "1574-9541"

openalex:
  mailto: "your-email@example.com" # Recommended for OpenAlex polite pool

model:
  base_url: "http://localhost:8087/v1"
  model_name: "gemma4"
  api_key: "not-needed"

settings:
  default_days: 3
  data_dir: "data"
  paper_timeout_seconds: 120 # Max time to wait per paper summary
  abstract_max_chars: 800    # Truncate abstracts sent to the model
  min_relevance_score: 0.7   # Drop papers below this score from the report

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

To add new journals, simply append them to the `journals` list in `config.yaml` using their ISSN.

## Notes  

- **Choose a model with strong function calling**: pydantic-ai uses OpenAI-style **tool/function calling** to extract structured summaries (JSON with specific fields like `relevance_score`, `key_methods`, etc.). The model must respond with a valid `tool_calls` payload, not just plain text. Many models (especially quantized ones) struggle with this format — they may return wrong types (string instead of number for `relevance_score`), omit required fields, or produce malformed JSON. Each failure triggers an automatic retry, which can lead to timeouts and skipped papers. Models from the **Qwen** (3/3.5) and **DeepSeek** families are known for reliable function calling even at low quantization levels. Here we use `Qwen3-8B-Q4_K_M` with `--temp 0.3` for deterministic output.

- **Use a low temperature for structured output**: Function calling is inherently deterministic and the model should pick from a constrained set of fields and types. A high temperature (`--temp 1.0`) makes the model more "creative," which often means it invents field names, returns unexpected types, or ignores the tool schema entirely. For reliable structured output, keep `--temp ≤ 0.3` on the server side. The agent-side `temperature: 0.2` in `config.yaml` only controls pydantic-ai's request — it doesn't override the server flag if you pass `--temp 1.0` at launch.
