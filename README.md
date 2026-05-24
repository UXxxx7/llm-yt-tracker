<<<<<<< HEAD
# LLM YouTube Landscape Tracker

Auto-updating, transcript-grounded landscape of LLM YouTube content.

**Live URL:** https://<your-github-user>.github.io/llm-yt-tracker/

## Quick start

1. Install [uv](https://docs.astral.sh/uv/) (Python project & venv manager).
2. `uv sync` — creates `.venv` and installs all deps (incl. `yt-dlp`).
3. Verify `uv run yt-dlp --version` works.
4. `cp .env.example .env` and fill in API keys (YouTube Data v3, DeepSeek, OpenAI).
5. `uv run python -m pipeline.run --dry-run --limit 1` to verify the pipeline end-to-end.
6. `uv run python -m pipeline.run` for a real cycle (writes `web/videos.json`, pushes to GitHub).
7. Open `web/index.html` locally, or push and open the GitHub Pages URL.

## How it stays current

Windows Task Scheduler runs `uv run python -m pipeline.run` every 6 hours (plus
on logon). The OpenClaw skill at `~/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md`
documents the same workflow and can be triggered interactively via OpenClaw
("刷新 LLM 表格" or "refresh llm tracker").

See `docs/architecture.md` for the data flow and `docs/deployment.md` for the
one-time setup runbook.

## Repository layout

- `pipeline/` — Python modules; each can be run as `uv run python -m pipeline.<name>`
- `web/` — static frontend (Tailwind CDN, vanilla JS, reads `videos.json`)
- `channels.yaml` — monitored channels
- `scripts/register_task.ps1` — one-shot Windows scheduler registration
- `tests/` — pytest suite (run `uv run pytest`)
- `docs/specs/` — design spec
- `docs/plans/` — implementation plan (this build)
- `pyproject.toml` + `uv.lock` — dependency manifest
=======
# llm-yt-tracker
>>>>>>> 4664e4059c09ed91f37d0cd10d08a73fd3c65310
