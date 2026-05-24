# LLM YouTube Landscape Tracker — Report

**Live site:** https://uxxxx7.github.io/llm-yt-tracker/
**Repository:** this repo
**Author:** YMX
**Date:** 2026-05-24

---

## 1. Problem Statement

The LLM space moves faster than any individual can watch. Across a small set
of high-signal YouTube creators (Andrej Karpathy, Yannic Kilcher, DeepLearningAI,
AI Explained, sentdex, Two Minute Papers, Matthew Berman, AI Jason, AI Coffee
Break) tens of new videos appear every week. Two practical problems:

1. **Titles and thumbnails are unreliable signal.** YouTube optimises both
   for click-through, not for accurate description of what the creator
   actually says. A row like "DeepSeek's New AI Is A Game Changer" tells
   you almost nothing about whether the creator discusses architecture,
   benchmarks, or just hype.
2. **Cross-channel topic discovery is manual.** If creator A and creator B
   both spend a week on RLHF, there is no surface that shows that — you
   would have to subscribe to both and notice yourself.

**Goal:** build a self-updating public table where each row is grounded in
what the creator *actually said in the audio*, tagged with a controlled
vocabulary, with cross-channel topic relationships surfaced.

The deliverables in the brief translate into three concrete requirements:

- **D1.** A concise table categorising videos by speaker, topic, and inter-channel
  relationship.
- **D2.** Public hosting that stays current without manual intervention.
- **D3.** AI transcription/captioning so summaries reflect spoken content,
  not titles.

---

## 2. Methodology

### 2.1 Pipeline architecture

A five-stage pipeline runs every 6 hours via Windows Task Scheduler:

```
fetch_videos  →  transcribe  →  summarise  →  merge  →  publish
   (YouTube       (yt-dlp         (DeepSeek      (web/        (git push →
    Data API)      captions        chat API)      videos.json)  GitHub Pages)
                   ↓ Whisper
                   fallback)
```

Each stage is a focused module in `pipeline/`. State is persisted in
`pipeline/state.json` so each run only processes genuinely new videos.

### 2.2 Channel set (9 channels)

Selected to span the LLM creator spectrum: academic (Yannic Kilcher,
sentdex), educational (DeepLearningAI, AI Coffee Break, Andrej Karpathy),
news/explainer (AI Explained, Two Minute Papers, Matthew Berman), and
hands-on (AI Jason). The list lives in `channels.yaml` and is trivially
extensible.

### 2.3 Discovery (`fetch_videos.py`)

YouTube Data API v3 `search.list` with `order=date` per channel, capped at
10 results per channel per run (`MAX_VIDEOS_PER_CHANNEL_PER_RUN`). Videos
shorter than 90 seconds are rejected (`MIN_DURATION_SECONDS`) to filter
Shorts, which rarely contain substantive LLM commentary.

### 2.4 Transcription (`transcribe.py`)

Two-tier strategy, captions-first:

1. **yt-dlp auto-subs / human subs** — free, instant, available for ~80%
   of videos from these channels. VTT timestamps and HTML tags are stripped
   to plain text; near-duplicate consecutive lines are deduped.
2. **OpenAI Whisper fallback** — only if captions are missing or shorter
   than 1000 chars (`MIN_TRANSCRIPT_CHARS`). Audio is downloaded as mp3
   via yt-dlp + ffmpeg and posted to `/v1/audio/transcriptions`. Audio
   files are deleted immediately after the API response.

Cost discipline is built in: Whisper is ~$0.006/min at official rates,
and we only call it when captions truly fail.

### 2.5 Summarisation (`summarise.py`)

The single most load-bearing piece of the system. DeepSeek-V4
(`deepseek-chat`) is called with a strict prompt that forbids using the
title, thumbnail, or any outside knowledge — see `_build_prompt`.
The prompt requests strict JSON with four fields:

- `summary` — 2–3 Chinese sentences describing what the speaker actually said.
- `topic_tags` — 1–5 tags from a fixed controlled vocabulary (16 tags:
  RAG, fine-tuning, agents, evals, multimodal, MoE, reasoning,
  inference-optimization, prompting, alignment, open-source-models,
  benchmarks, scaling, interpretability, robotics, code-generation).
- `key_quotes` — 1–3 verbatim English quotes from the transcript.
- `related_channels` — up to 3 channel names from the known set that
  cover overlapping topics.

Three retries with exponential backoff handle transient API failures.
Empty responses and malformed JSON are detected separately and trigger
different recovery paths (retry vs. add corrective hint to the prompt).
`max_tokens=1500` accommodates a Chinese summary plus English quotes
without mid-string truncation.

### 2.6 Controlled vocabulary

Free-form LLM tagging produces drift ("RAG" vs "rag" vs "retrieval augmented
generation") within a few days. A fixed 16-tag vocabulary keeps the UI
filter usable and makes related-video grouping meaningful. Tag normalisation
in `pipeline/tags.py` maps case variations to canonical form; unknown tags
become `uncategorized`.

### 2.7 Publishing

`pipeline/publish.py` merges new rows into `web/videos.json` (deduplicated
by `video_id`, newest first), then `git commit` + `git push` to main. A
GitHub Actions workflow (`.github/workflows/pages.yml`) deploys the `web/`
directory to GitHub Pages on every push that touches `web/**`.

### 2.8 Front-end (`web/`)

Vanilla HTML + JS + Tailwind CDN. No build step, no framework, no backend
— `videos.json` is the entire data layer. Features:

- Full-text search across title, channel, summary
- Channel dropdown filter
- Tag chip filter (click to toggle)
- Sortable columns (published date, channel)
- Click-through row expansion showing summary, key quotes, related channels

This minimalism is intentional: static hosting on GitHub Pages costs $0
and has no moving parts to break.

### 2.9 Automation

Two layers of triggering:

- **Windows Task Scheduler** — `scripts/register_task.ps1` registers a
  task that runs `uv run python -m pipeline.run` on logon and every 6h
  thereafter. The script requires admin elevation and self-verifies via
  `Get-ScheduledTask` after registration.
- **OpenClaw skill** — `~/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md`
  lets the user say "刷新 LLM 表格" or "refresh llm tracker" to trigger
  an ad-hoc refresh between scheduled runs.

### 2.10 Proxy and model configuration

API access goes through a domestic OpenAI-compatible proxy (wolfai.top in
this deployment) configured via `.env`:

```
DEEPSEEK_BASE_URL=https://wolfai.top/v1
OPENAI_BASE_URL=https://wolfai.top/v1
DEEPSEEK_MODEL=<proxy-specific id>
WHISPER_MODEL=whisper-1
```

The model IDs are env-overridable because proxies routinely expose the
same model under non-standard names (e.g. `deepseek-v3` instead of
`deepseek-chat`). Defaults match the official API names.

---

## 3. Evaluation Dataset

This is a real-world pipeline, not a closed benchmark. The "dataset"
under evaluation is the live stream of YouTube videos from the 9 seed
channels. As of the time of this report, the production `web/videos.json`
contains **65 videos** spanning multiple weeks of content, with the
most recent refresh at `2026-05-24T07:52Z`.

For each video the pipeline records:

- Provenance: `video_id`, `channel`, `published_at`, `url`, `duration_seconds`
- Transcript metadata: `transcript_source` (`captions` or `whisper`),
  `transcript_excerpt_chars`, `transcript_excerpt` (first 500 chars,
  kept for spot-check auditability)
- LLM output: `summary`, `topic_tags`, `key_quotes`, `related_channels`
- Run metadata: `processed_at`, `pipeline_version`

Storing `transcript_excerpt` makes the system **auditable** — a reviewer
can spot-check that a given summary actually corresponds to the speaker's
words, not the title.

---

## 4. Evaluation Methods

### 4.1 Automated (`tests/`, 32 tests)

The test suite covers each pipeline stage in isolation with mocked
externals:

- `test_fetch_videos.py` — YouTube API response shapes, pagination,
  duration filtering, state-incremental discovery.
- `test_transcribe.py` — VTT parsing edge cases (timestamps, HTML tags,
  near-duplicate dedup), captions-first/Whisper-fallback decision logic,
  short-transcript rejection.
- `test_summarise.py` — JSON extraction from markdown-fenced and prose-wrapped
  responses, retry behaviour on parse failures and empty responses,
  tag normalisation and unknown-tag handling, controlled-vocabulary
  enforcement.
- `test_publish.py` — merge-by-id deduplication, sort order, idempotent
  re-runs.
- `test_state.py` — self-healing on missing/corrupt state.json.

All 32 tests pass at the current commit. Tests use `pytest-mock` to avoid
hitting any external APIs.

### 4.2 Manual spot-checks

Because the summary quality is the actual product (not a metric the test
suite can assert against), evaluation is also continuous and manual:

- Open the live site, pick a row, expand the summary, then open the video.
  Read the first minute of the transcript and verify the summary
  reflects what the speaker actually said in the body of the video,
  not what the title promised.
- Inspect `topic_tags` for sanity — does an "evals"-tagged video genuinely
  discuss evals?
- Audit `related_channels` against intuition — does the suggested
  cross-reference make sense topic-wise?

The `transcript_excerpt` field in `videos.json` enables this audit
without re-running the pipeline.

### 4.3 Operational evaluation

The pipeline has been run end-to-end through Windows Task Scheduler and
manual invocation. Observed behaviours under partial failure:

- YouTube API per-minute quota exceeded for one channel → that channel
  is skipped this cycle, others continue, no crash.
- yt-dlp audio download fails for one video → that video is dropped with
  a warning, others continue.
- Whisper proxy returns 503 → openai SDK retries with exponential backoff;
  if all retries fail the video is dropped, run continues.
- DeepSeek returns malformed JSON → three retries with corrective hint
  added to the prompt before giving up.
- DeepSeek returns empty response → treated as transient API failure,
  not as a parse error.

No single video failure can poison a run.

---

## 5. Experimental Results

### 5.1 Quantitative

| Metric | Value |
|---|---|
| Channels tracked | 9 |
| Videos in `web/videos.json` | 65 |
| Controlled tag vocabulary size | 16 + `uncategorized` |
| Test count, all passing | 32 |
| Refresh cadence | every 6h + on-logon + manual |
| Transcript sources observed | `captions` (majority), `whisper` (fallback) |
| Avg transcript length (sampled rows) | ~13,000–27,000 chars |
| Live site update latency (commit → visible) | ~60–90s via GitHub Actions |
| Cost per refresh, observed | dominated by DeepSeek chat calls; Whisper rarely triggered |

### 5.2 Qualitative — summary grounding

Sampled rows confirm the prompt constraint holds. Examples from the live
data:

- *"AI Dev 26 x SF | Ara Khan: Evals Are Broken Use Them Anyway"* —
  title says only "evals broken". The pipeline summary identifies the
  speaker's three concrete heuristics: don't trust lab evals, stay
  current but don't chase, use evals targeted at your own problem.
  None of this is in the title or thumbnail.
- *"AI Dev 26 x SF | Andi Partovi: Why Every Agent Needs a Simulation
  Sandbox"* — summary extracts the actual argument (non-determinism +
  interactivity + dynamic labels break gold-dataset evaluation) and the
  proposed solution (simulation environments with five named components).
- *"AI Dev 26 x SF | João Moura: Building Recurring, Governed, and
  Embedded Enterprise Workflows"* — `related_channels` correctly
  identifies `Matthew Berman` and `AI Jason` as agent-focused channels.

### 5.3 Failure modes encountered and resolved

| Failure | Root cause | Resolution |
|---|---|---|
| `Client.__init__() got an unexpected keyword argument 'proxies'` | openai 1.55.0 + httpx 0.28 ABI break | Pinned openai to 1.58.1 |
| DeepSeek responses truncated mid-string | `max_tokens=600` insufficient for Chinese summary + English quotes | Raised to 1500; logged raw response on parse failure for diagnosis |
| Proxy returns `model_not_found` for `deepseek-chat` | Proxy uses non-standard model IDs | Made `DEEPSEEK_MODEL` and `WHISPER_MODEL` env-overridable |
| Whisper 503 `under group default` | API key in wrong proxy group tier | Switched key to svip group on proxy console |
| `Register-ScheduledTask` silent failure | Script ran from non-elevated PowerShell; `$ErrorActionPreference=Stop` doesn't catch CIM exceptions | Added explicit admin-role check + post-registration `Get-ScheduledTask` verification |
| yt-dlp postprocessing fails | ffmpeg/ffprobe missing on host | Documented `winget install Gyan.FFmpeg` in deployment runbook |
| GitHub Pages "Deploy from a branch" only offers `/(root)` and `/docs` | UI hardcoded to two folder choices, can't see `web/` | Switched to GitHub Actions deployment with `upload-pages-artifact` pointed at `web/` |

### 5.4 Live-site demonstration

The page at `https://uxxxx7.github.io/llm-yt-tracker/` shows the table
with all the deliverables visible at once: 65 rows, channel filter,
controlled-tag chip filter, full-text search, sortable columns, and a
visible last-refresh timestamp in the header confirming auto-update is
working.

---

## 6. Conclusion

The system satisfies the three deliverables in the brief:

- **D1 (categorising table):** ✅ `web/videos.json` with channel,
  controlled tags, and cross-channel relationships, rendered as a
  filterable table.
- **D2 (public hosting, stays current):** ✅ GitHub Pages live URL, fed
  by a 6-hourly Windows Scheduled Task with manual OpenClaw trigger as
  a fallback.
- **D3 (AI transcription/captioning):** ✅ yt-dlp captions first, OpenAI
  Whisper as fallback, both feeding a DeepSeek prompt that explicitly
  forbids using titles or thumbnails.

The Assessment requirement ("walk us through the live site: show how the
data is collected, how summaries are produced, how the table stays
current") can be answered end-to-end from this report, the live URL, the
`docs/architecture.md` companion document, and the codebase.
