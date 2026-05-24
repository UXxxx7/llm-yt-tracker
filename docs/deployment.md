# Deployment runbook

One-time setup, in order. Steps marked **(skip if done)** can be reused later.

## 1. API keys

- **YouTube Data API v3**: Google Cloud Console → APIs & Services → Enable
  "YouTube Data API v3" → Create credentials → API key. Copy.
- **DeepSeek**: platform.deepseek.com → API Keys → Create. Copy.
- **OpenAI** (Whisper fallback only): platform.openai.com → API Keys → Create.

`cp .env.example .env` and paste the three values.

### Using a domestic API proxy (optional)

If the host machine can't reach `api.openai.com` / `api.deepseek.com` directly,
route through any OpenAI-compatible proxy by setting these in `.env`:

```
DEEPSEEK_BASE_URL=https://your-proxy.example.com/v1
OPENAI_BASE_URL=https://your-proxy.example.com/v1
```

`DEEPSEEK_API_KEY` and `OPENAI_API_KEY` then become whatever credentials the
proxy expects (often the same key for both). Leave the URLs unset to use the
official endpoints.

## 2. uv + deps

Install uv (one-time, system-wide): https://docs.astral.sh/uv/getting-started/installation/

Then from the project root:

```bash
uv sync                       # creates .venv, installs locked deps
uv run yt-dlp --version       # verify yt-dlp is callable through the venv
```

## 3. Verify pipeline end-to-end

```bash
uv run python -m pipeline.run --dry-run --limit 1
```

Expected: log line "found N new videos", at least one "processed 1/1 videos
successfully", and "--dry-run: skipping write and publish".

## 4. GitHub repo + Pages

```bash
git remote add origin https://github.com/<USER>/llm-yt-tracker.git
git push -u origin main
```

In GitHub repo settings → Pages:
- Source: Deploy from a branch
- Branch: `main`, folder: `/web`
- Save. Wait ~1 min, open `https://<USER>.github.io/llm-yt-tracker/`.

The empty `web/videos.json` will render an empty table with "0 videos". After
the first real run, refresh and the table populates.

## 5. First real run

```bash
uv run python -m pipeline.run
```

Expect a new `data: refresh ...` commit on GitHub. Within ~1 min the live URL
shows the new rows.

## 6. Register Windows Task Scheduler

Open PowerShell **as Administrator**:

```powershell
cd D:\YMX\llm-yt-tracker
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

The script discovers `uv` via `Get-Command uv` and registers a scheduled task
that runs `uv run python -m pipeline.run` from the project root every 6 hours
and on logon.

Verify with:

```powershell
Get-ScheduledTask -TaskName "LLM-YT-Tracker-Refresh"
Start-ScheduledTask -TaskName "LLM-YT-Tracker-Refresh"   # manual fire
```

## 7. (Optional) OpenClaw skill manual trigger

The skill at `~/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md` lets you
trigger a refresh interactively: type "刷新 LLM 表格" or "refresh llm tracker"
to OpenClaw and it will execute the same command.
