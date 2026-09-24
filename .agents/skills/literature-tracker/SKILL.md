---
name: literature-tracker
description: >-
  Find and summarize recent open-access papers by keyword and research topic,
  using the OpenAlex API. Use when the user describes their research interests
  and wants to track, monitor, review, or catch up on recent scientific
  literature — across all journals or scoped to specific ones — or asks
  "what's new" in their field.
license: MIT
---

# Literature Tracker

Help the user discover and digest recent papers. The user describes their
interests in plain language (e.g. *"I work on deep learning for camera-trap and
bioacoustic data — catch me up on the last two weeks"*). You infer the search
criteria, show them for the user to refine, run a bundled script to fetch papers
from OpenAlex, then summarize and rank the results yourself.

The bundled script (`scripts/openalex.py`) is stdlib-only Python 3.9+ — no
installation or dependencies are required. It only fetches data; **you** do all
the reading, summarizing, scoring, and highlighting.

## Workflow

### 1. Interpret the request

From whatever the user says, infer:

- **Keywords** — the concepts to match. Expand the user's phrasing with obvious
  synonyms and spelling variants (e.g. "passive acoustic monitoring",
  "bioacoustics"). A paper matches if it contains *any* keyword.
- **Exclude keywords** — terms that should drop a paper (e.g. `review`,
  `survey`, `editorial`). Optional.
- **Days back** — parse natural phrases ("last two weeks" → 14). Default 7.
- **Journals** — only if the user names or clearly implies specific journals.
  Otherwise leave empty and search across all open-access literature.
- **Relevance threshold** (0.0–1.0) below which to drop papers. Default 0.5.

### 2. Propose the criteria and let the user refine them

Before calling the API, show the user an editable summary and ask them to adjust
anything. This is the one required confirmation step. For example:

```
Here's what I inferred — edit anything before I search:

Keywords:  camera trap, bioacoustics, "deep learning", passive acoustic monitoring
Exclude:   review, survey
Journals:  (none — searching all open-access literature)
           optional, if you'd like to scope: Methods in Ecology and Evolution,
           Remote Sensing in Ecology and Conservation
Window:    last 14 days   |   Sort: relevance   |   Open access only: yes
```

Let the user add/remove keywords, accept or reject any suggested journals, or
change the window/threshold. Only fetch once they're happy.

### 3. (Optional) Resolve journals to ISSNs

Only if the user wants to scope to journals. For each journal name:

```bash
python scripts/openalex.py search --query "<journal name>"
```

This prints `[{"name": ..., "issn": ..., "works_count": ...}]`. Confirm the
correct ISSN with the user, then collect the confirmed ISSNs.

You may also try resolving a topic phrase to OpenAlex topic IDs:

```bash
python scripts/openalex.py topics --query "camera trap ecology"
```

Topic search is unreliable for arbitrary phrases — if it returns nothing, just
rely on keywords. Only use a returned `topic_id` to *narrow* results.

### 4. Fetch papers

Journal-less by default (searches all open-access literature):

```bash
python scripts/openalex.py fetch \
  --keywords "camera trap" bioacoustics "deep learning" \
  --exclude review survey \
  --days 14 \
  --max 40
```

Scope to journals and/or topics when the user asked for it:

```bash
python scripts/openalex.py fetch \
  --issn 2041-210X 2056-3485 \
  --topic-id T10199 \
  --keywords "camera trap" bioacoustics \
  --days 14
```

Useful flags (all optional):

- `--sort relevance` (default; ranks by match to keywords) or `--sort date`
  (newest first).
- `--no-open-access` to include paywalled works (open access is on by default).
- `--no-require-abstract` to include works without abstracts (you'll have less
  to summarize).
- `--types article review` to change work types (default: `article`; pass
  `--types` with nothing to allow all types).
- `--mailto <email>` to use OpenAlex's faster "polite pool".

Output is a JSON array of papers, each with: `paper_id`, `title`, `authors`,
`abstract`, `url`, `source`, `published_date`, `categories`.

If the array is empty, tell the user and suggest broadening keywords, dropping
journal scoping, or increasing `--days`. If it hits `--max`, mention results may
be truncated and offer to narrow the keywords.

### 5. Summarize each paper

For every returned paper, produce:

- **summary** — 2–3 precise sentences on the key contribution. Be technical and
  specific; avoid vague language.
- **relevance_score** — a float 0.0–1.0 for how relevant the paper is to the
  user's interests (0 = irrelevant, 1 = highly relevant).
- **methods** — key methods or techniques (specific models, experimental
  designs, analyses).
- **topics** — research topics/subfields/application areas addressed.

Base these only on the title and abstract provided. Do not invent findings. If a
paper has no abstract, say so and score conservatively.

### 6. Curate and highlight

- Drop any paper below the user's relevance threshold (note how many you drop).
- From what remains, pick the **1–3 most noteworthy** papers as highlights
  (most novel or impactful for the user's interests).

### 7. Present the report

Output clean Markdown:

```markdown
# Literature Summary — <date>
**Papers reviewed:** <count>  |  **Dropped below threshold:** <n>

## Highlights
- <title of standout paper 1> — <one-line reason it stands out>
- <title of standout paper 2> — <one-line reason>

## Papers
### <title>
**Source:** <source> | **Date:** <published_date> | **Relevance:** <score>
**Authors:** <first few authors, then "et al.">
**URL:** <url>

<summary>

**Methods:** <comma-separated>
**Topics:** <comma-separated>
```

Sort papers by relevance (highest first). Flag any paper whose abstract was
missing or truncated. Offer to save the report to a file and/or export BibTeX
for the highlights.

### 8. Refine

After the report, offer to iterate: broaden or narrow keywords, change the day
window, adjust the threshold, toggle open-access, or add/remove journals — then
re-run from step 4.

## Notes

- Keyword matching, exclusions, open-access, abstract availability and work type
  are all enforced server-side by OpenAlex, so the returned set already matches
  — but always apply your own judgment when scoring relevance.
- Keep the corpus manageable: if the criteria are very broad, suggest tightening
  keywords or scoping to journals so summaries stay high quality.
