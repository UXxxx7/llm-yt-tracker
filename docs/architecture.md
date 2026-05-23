# Architecture

## Data flow

```
Windows Task Scheduler  ──┐
OpenClaw skill (manual)  ─┴──►  uv run python -m pipeline.run
                                      │
                  ┌───────────────────┼────────────────────┐
                  ▼                   ▼                    ▼
              fetch_videos       transcribe            summarise
              (YouTube API)   (yt-dlp / Whisper)   (DeepSeek-V4)
                  │                   │                    │
                  └─────────► run.py ◄┴──────────► build_table
                                                       │
                                                       ▼
                                      web/videos.json + pipeline/state.json
                                                       │
                                                       ▼
                                                    publish (git push)
                                                       │
                                                       ▼
                                               GitHub Pages → Live URL
```

## Why these choices

- **Captions first, Whisper fallback.** ~80% of LLM channels publish auto-captions.
  Defaulting to Whisper would 10×+ the cost with little quality gain.
- **DeepSeek-V4 over GPT/Claude.** ~10× cheaper for equivalent summary quality on
  this size of input. OpenAI-compatible API means zero SDK migration cost.
- **JSON file, no database.** At one row per video and ~9 channels, JSON is
  ~hundreds of KB even after a year. Git history doubles as audit log.
- **Skill is a thin shell.** Real logic lives in Python files so each can be
  debugged with `uv run python -m pipeline.<name>` and the cron path doesn't
  depend on the OpenClaw runtime being online.
- **uv for env management.** Single tool for Python version pin, venv, and
  locked deps. `uv sync` is reproducible; `uv run` always uses the project venv.

## Field invariants

- `transcript_source ∈ {"captions", "whisper"}` — never derived from
  title/description.
- `transcript_excerpt_chars ≥ 1000` — videos below this are dropped (likely
  Shorts/music).
- `topic_tags ⊆ controlled vocabulary` — see `pipeline/tags.py`.

## Review walkthrough mapping

- (A) Live URL → open the GitHub Pages link.
- (B) Three pipelines → walk `fetch_videos.py`, `transcribe.py`, `summarise.py`;
  show prompt forbidding title use; pick a row in `videos.json` and put
  `transcript_excerpt` next to `summary` to prove grounding.
- (C) Stays current → show Task Scheduler entry, `logs/cron.log`, and the
  recent `data: refresh ...` commits on GitHub.
