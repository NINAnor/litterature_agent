# Literature Tracker 📄🌱

An **Agent Skill** that helps an AI assistant find and summarize recent
open-access papers on the research topics you care about, using the
[OpenAlex](https://openalex.org) API.

No server, no database, no model to host. It's a single
[`SKILL.md`](skills/literature-tracker/SKILL.md) plus a small stdlib-only
Python script. You describe your interests in plain language, and your
assistant infers keywords/journals, fetches matching papers, and writes a
Markdown summary report — all reasoning happens in your assistant, the script
only talks to OpenAlex.

## Install

### OpenCode

```bash
# Project-local
mkdir -p .opencode/skills
ln -s "$PWD/skills/literature-tracker" .opencode/skills/literature-tracker

# ...or global, available in every project
mkdir -p ~/.config/opencode/skills
ln -s "$PWD/skills/literature-tracker" ~/.config/opencode/skills/literature-tracker
```

### Claude Code

```bash
# Project-local
mkdir -p .claude/skills
ln -s "$PWD/skills/literature-tracker" .claude/skills/literature-tracker

# ...or global, available in every project
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/literature-tracker" ~/.claude/skills/literature-tracker
```

For **claude.ai** (web), zip `skills/literature-tracker/` and upload it under
Settings.

### ChatGPT / Codex

For **local discovery** (Codex CLI, ChatGPT desktop app editing this repo),
symlink into `.agents/skills/`, the same way as above:

```bash
mkdir -p .agents/skills
ln -s "$PWD/skills/literature-tracker" .agents/skills/literature-tracker
```

For **ChatGPT's plugin upload UI**, it needs an installable package, not a
bare skill folder — build one from `plugin.json` + `skills/` (already at the
repo root):

```bash
zip -r literature-tracker-plugin.zip plugin.json skills/
```

Upload `literature-tracker-plugin.zip` via ChatGPT's plugin install UI.
(GitHub's "Code → Download ZIP" button also produces a valid package, since
this repo has no symlinks committed.)

## Usage

Once installed, just ask your assistant something like:

> *"Track recent deep-learning papers in Methods in Ecology and Evolution
> from the last two weeks."*

## Development

```bash
python3 -m pytest tests -v
```

The tests stub all HTTP, so they run offline.
