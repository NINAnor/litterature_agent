# Literature Tracker 📄🌱

An **Agent Skill** that helps an AI assistant find and summarize recent
open-access papers on the research topics you care about, using the
[OpenAlex](https://openalex.org) API.

There is no server, no database, no model to host, and no dependencies to
install. The skill is a single [`SKILL.md`](skills/literature-tracker/SKILL.md)
plus one small, stdlib-only Python script. Your AI host (OpenCode, Claude, or
ChatGPT desktop / Codex) reads the instructions, interprets your interests from
plain language, runs the script to fetch papers from OpenAlex, and does all the
summarizing, relevance scoring, and highlighting itself.

## How it works

1. You describe your interests in plain language (e.g. *"deep learning for
   camera-trap and bioacoustic data — catch me up on the last two weeks"*).
2. The assistant infers **keywords**, **exclude keywords**, a **time window**,
   and any **journals** you named, then shows the list for you to refine.
3. It runs `scripts/openalex.py fetch` to pull recent, open-access,
   keyword-matched papers — across all of OpenAlex by default, or scoped to
   specific journals (`scripts/openalex.py search` resolves journal names to
   ISSNs) or topics (`scripts/openalex.py topics`).
4. It reads the returned JSON and writes a Markdown report: a 2–3 sentence
   summary, relevance score, methods, and topics per paper, plus 1–3
   highlights.

The only thing the script does is talk to OpenAlex and reconstruct abstracts —
all the reasoning happens in your assistant.

## Repository layout

```text
.
├── plugin.json                    # Portable Agent Plugins manifest (for ChatGPT plugin upload)
├── skills/literature-tracker/     # Canonical skill location
│   ├── SKILL.md                   # Instructions the host model follows
│   ├── agents/openai.yaml         # Optional ChatGPT-desktop UI metadata
│   └── scripts/openalex.py        # Stdlib-only OpenAlex fetch engine (Python 3.9+)
├── .agents/skills/literature-tracker  # Symlink -> ../../skills/literature-tracker
│                                       # (for hosts that discover .agents/skills/)
├── tests/
│   └── test_openalex.py           # Unit tests (mocked HTTP)
└── README.md
```

`skills/literature-tracker/` is the single source of truth — always edit it
there. `.agents/skills/literature-tracker` is a symlink kept for hosts that
discover skills under `.agents/skills/` (OpenCode, Codex, Claude Code local
discovery); it isn't a separate copy.

> **Note:** if you ever clone this repo on Windows with `core.symlinks=false`,
> the symlink will check out as a plain text file instead of a real symlink.
> Re-create it manually in that case:
> `ln -s ../../skills/literature-tracker .agents/skills/literature-tracker`.

## Installation

The skill uses the open [Agent Skills standard](https://agentskills.io), so the
same folder works across hosts. Copy or symlink
`skills/literature-tracker/` into the location your host discovers:

| Host | Skill location |
|------|----------------|
| **OpenCode** | `.opencode/skills/` (project) or `~/.config/opencode/skills/` (global) — it also reads `.agents/skills/` |
| **ChatGPT desktop / Codex** | `.agents/skills/` (project) or `~/.agents/skills/` (global) for local discovery — or install `plugin.json` as a plugin (see below) |
| **Claude Code** | `.claude/skills/` (project) or `~/.claude/skills/` (global) |
| **claude.ai** | Settings → upload the folder as a zip |

For example, to make it available globally in OpenCode and Codex:

```bash
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/literature-tracker" ~/.agents/skills/literature-tracker
```

Then just ask your assistant something like *"track recent deep-learning papers
in Methods in Ecology and Evolution from the last two weeks."*

## Package as a ChatGPT plugin

ChatGPT's plugin **upload** flow expects an installable package, not a bare
skill folder — its archive validator looks for a `plugin.json` manifest plus a
top-level `skills/` directory (this repo already has both at the root). Either
of these works:

```bash
# Manual archive (always safe)
zip -r literature-tracker-plugin.zip plugin.json skills/

# ...or use GitHub's own "Code → Download ZIP" button on the repo.
# .gitattributes marks the .agents/skills/literature-tracker symlink as
# export-ignore, so GitHub's archive omits it and only ships plugin.json +
# skills/ (symlinks aren't valid archive members for ChatGPT's uploader).
```

Upload the resulting zip via ChatGPT's plugin install UI. This is separate
from local skill discovery (the `.agents/skills/` symlink above) — use the
plugin package specifically when ChatGPT's *upload* flow is what's asking for
a zip.

## Using the script directly

You don't need to — the assistant runs it for you — but it's a normal CLI:

```bash
# Find a journal's ISSN (only needed if you want to scope to journals)
python3 skills/literature-tracker/scripts/openalex.py \
  search --query "Methods in Ecology and Evolution"

# Fetch recent open-access matching papers across all of OpenAlex
python3 skills/literature-tracker/scripts/openalex.py \
  fetch --keywords "camera trap" bioacoustics --exclude review --days 14 --max 40

# ...or scope to specific journals
python3 skills/literature-tracker/scripts/openalex.py \
  fetch --issn 2041-210X --keywords "deep learning" --days 14 --max 40
```

Add `--mailto you@example.com` to use OpenAlex's faster "polite pool".

## Requirements

- Python 3.9+ (standard library only — no `pip install` needed)
- Network access to `api.openalex.org` from wherever the skill runs

## Development

```bash
python3 -m pytest tests -v
```

The tests stub all HTTP, so they run offline.
