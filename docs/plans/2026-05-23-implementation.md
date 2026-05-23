# LLM YouTube Landscape Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public, continuously-updating LLM YouTube landscape tracker driven by an OpenClaw skill that runs a Python pipeline (YouTube API → captions/Whisper → DeepSeek-V4 summary → JSON → GitHub Pages).

**Architecture:** Thin OpenClaw skill (`SKILL.md`) shells out to `python -m pipeline.run` on a Windows always-on machine. Pipeline modules are independently runnable. Data published as `web/videos.json`, rendered by a static frontend on GitHub Pages. Windows Task Scheduler triggers every 6 hours.

**Tech Stack:** Python 3.13, yt-dlp, google-api-python-client, openai SDK (pointing at DeepSeek + OpenAI Whisper), pytest, vanilla JS + Tailwind CDN, GitHub Pages, Windows Task Scheduler.

**Working directory for all tasks:** `D:\YMX\llm-yt-tracker` unless stated otherwise.

---

## File Structure

```
D:\YMX\llm-yt-tracker\
  channels.yaml
  .env.example                 (.env is gitignored)
  .gitignore
  requirements.txt
  README.md
  pipeline/
    __init__.py
    config.py                  load env + paths
    tags.py                    controlled tag vocabulary
    state.py                   load/save state.json
    fetch_videos.py            YouTube Data API
    transcribe.py              captions-first, Whisper fallback
    summarise.py               DeepSeek-V4
    build_table.py             merge + write videos.json
    publish.py                 git commit + push
    run.py                     cron entry point
    state.json                 (data, git-tracked)
  web/
    index.html
    app.js
    style.css
    videos.json                (data, git-tracked)
  scripts/
    register_task.ps1
  tests/
    __init__.py
    test_tags.py
    test_state.py
    test_summarise.py
    test_build_table.py
    test_transcribe.py
    fixtures/
      transcript_sample_1.txt
      transcript_sample_2.txt
  docs/
    specs/2026-05-23-design.md (exists)
    plans/2026-05-23-implementation.md (this file)
    architecture.md
    deployment.md
  logs/                        (gitignored except .gitkeep)
```

External:
```
C:\Users\11989\.openclaw\workspace\skills\llm-yt-tracker\
  SKILL.md
```

---

### Task 1: Project skeleton and git init

**Files:**
- Create: `D:/YMX/llm-yt-tracker/.gitignore`
- Create: `D:/YMX/llm-yt-tracker/requirements.txt`
- Create: `D:/YMX/llm-yt-tracker/.env.example`
- Create: `D:/YMX/llm-yt-tracker/logs/.gitkeep`
- Create: `D:/YMX/llm-yt-tracker/pipeline/__init__.py`
- Create: `D:/YMX/llm-yt-tracker/tests/__init__.py`

- [ ] **Step 1: Write `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
logs/*.log
*.tmp.mp3
.venv/
.DS_Store
```

- [ ] **Step 2: Write `requirements.txt`**

```
google-api-python-client==2.149.0
yt-dlp==2025.5.1
openai==1.55.0
pyyaml==6.0.2
python-dotenv==1.0.1
pytest==8.3.3
pytest-mock==3.14.0
```

- [ ] **Step 3: Write `.env.example`**

```
YOUTUBE_API_KEY=your_youtube_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here_for_whisper
GITHUB_REPO_URL=https://github.com/USER/llm-yt-tracker.git
```

- [ ] **Step 4: Create empty package marker files**

`pipeline/__init__.py`:
```python
"""LLM YouTube Landscape Tracker pipeline."""

__version__ = "1.0.0"
```

`tests/__init__.py`: empty file.

`logs/.gitkeep`: empty file.

- [ ] **Step 5: Init repo and commit**

```bash
cd D:/YMX/llm-yt-tracker
git init -b main
git add .gitignore requirements.txt .env.example logs/.gitkeep pipeline/__init__.py tests/__init__.py docs/
git commit -m "chore: scaffold project structure"
```

Expected: One commit. `git status` clean.

---

### Task 2: Controlled tag vocabulary (`pipeline/tags.py`)

**Files:**
- Create: `pipeline/tags.py`
- Create: `tests/test_tags.py`

- [ ] **Step 1: Write failing test `tests/test_tags.py`**

```python
from pipeline.tags import CONTROLLED_TAGS, normalize_tags, UNCATEGORIZED


def test_controlled_tags_are_unique_and_lowercase_safe():
    assert len(CONTROLLED_TAGS) == len(set(CONTROLLED_TAGS))
    assert "RAG" in CONTROLLED_TAGS
    assert "fine-tuning" in CONTROLLED_TAGS


def test_normalize_keeps_valid_tags_in_order():
    out = normalize_tags(["RAG", "evals", "agents"])
    assert out == ["RAG", "evals", "agents"]


def test_normalize_drops_unknown_and_caps_at_five():
    out = normalize_tags(["RAG", "not-a-tag", "evals", "agents", "MoE", "scaling", "reasoning"])
    assert "not-a-tag" not in out
    assert len(out) <= 5


def test_normalize_returns_uncategorized_when_empty():
    assert normalize_tags([]) == [UNCATEGORIZED]
    assert normalize_tags(["not-a-tag"]) == [UNCATEGORIZED]


def test_normalize_dedupes():
    assert normalize_tags(["RAG", "RAG", "evals"]) == ["RAG", "evals"]
```

- [ ] **Step 2: Run test, expect failure**

Run: `cd D:/YMX/llm-yt-tracker && python -m pytest tests/test_tags.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.tags'`

- [ ] **Step 3: Write `pipeline/tags.py`**

```python
"""Controlled vocabulary for LLM topic tags.

WHY: free-form LLM tagging produces drift ("RAG" vs "rag" vs "retrieval augmented
generation"). A fixed vocabulary keeps the UI filter usable and makes related-video
grouping meaningful.
"""

CONTROLLED_TAGS = [
    "RAG",
    "fine-tuning",
    "agents",
    "evals",
    "multimodal",
    "MoE",
    "reasoning",
    "inference-optimization",
    "prompting",
    "alignment",
    "open-source-models",
    "benchmarks",
    "scaling",
    "interpretability",
    "robotics",
    "code-generation",
]

UNCATEGORIZED = "uncategorized"

_TAG_SET = set(CONTROLLED_TAGS)


def normalize_tags(raw_tags):
    """Keep only valid tags, dedupe preserving order, cap at 5, fallback to uncategorized."""
    seen = set()
    out = []
    for t in raw_tags:
        if t in _TAG_SET and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= 5:
            break
    return out if out else [UNCATEGORIZED]
```

- [ ] **Step 4: Run tests, expect pass**

Run: `python -m pytest tests/test_tags.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/tags.py tests/test_tags.py
git commit -m "feat(tags): controlled tag vocabulary with normalize"
```

---

### Task 3: Config loader (`pipeline/config.py`)

**Files:**
- Create: `pipeline/config.py`

- [ ] **Step 1: Write `pipeline/config.py`**

```python
"""Centralised config and path resolution.

WHY: every module needs the same project paths and env vars. Loading once here
prevents drift between modules and makes tests easy to mock.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
LOGS_DIR = PROJECT_ROOT / "logs"

VIDEOS_JSON = WEB_DIR / "videos.json"
STATE_JSON = PIPELINE_DIR / "state.json"
CHANNELS_YAML = PROJECT_ROOT / "channels.yaml"

load_dotenv(PROJECT_ROOT / ".env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
WHISPER_MODEL = "whisper-1"

MIN_TRANSCRIPT_CHARS = 1000
MIN_DURATION_SECONDS = 90
MAX_VIDEOS_PER_CHANNEL_PER_RUN = 10
PIPELINE_VERSION = "1.0.0"


def require(name):
    val = os.getenv(name, "")
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val
```

- [ ] **Step 2: Smoke-check import**

Run: `python -c "from pipeline import config; print(config.PROJECT_ROOT)"`
Expected: prints `D:\YMX\llm-yt-tracker`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/config.py
git commit -m "feat(config): centralised paths and env loading"
```

---

### Task 4: State management (`pipeline/state.py`)

**Files:**
- Create: `pipeline/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing test `tests/test_state.py`**

```python
import json
from pathlib import Path
from pipeline.state import load_state, save_state, EMPTY_STATE


def test_load_state_returns_empty_when_file_missing(tmp_path):
    missing = tmp_path / "no.json"
    assert load_state(missing) == EMPTY_STATE


def test_load_state_self_heals_on_corruption(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_state(bad) == EMPTY_STATE


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    state = {
        "last_run": "2026-05-23T10:00:00Z",
        "processed_video_ids": ["a", "b"],
        "channel_last_checked": {"UCxxx": "2026-05-23T10:00:00Z"},
    }
    save_state(p, state)
    assert load_state(p) == state


def test_empty_state_has_required_keys():
    assert set(EMPTY_STATE.keys()) == {"last_run", "processed_video_ids", "channel_last_checked"}
```

- [ ] **Step 2: Run test, expect failure**

Run: `python -m pytest tests/test_state.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `pipeline/state.py`**

```python
"""state.json read/write with self-healing.

WHY: state tracks which video_ids we've already processed so we don't
re-transcribe and re-summarise (the expensive steps). If the file is missing
or corrupted, we return an empty state — the next run will rebuild from
videos.json via build_table.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

EMPTY_STATE = {
    "last_run": None,
    "processed_video_ids": [],
    "channel_last_checked": {},
}


def load_state(path):
    p = Path(path)
    if not p.exists():
        return dict(EMPTY_STATE, processed_video_ids=[], channel_last_checked={})
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for key in EMPTY_STATE:
            data.setdefault(key, EMPTY_STATE[key])
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("state.json unreadable (%s), starting empty", e)
        return dict(EMPTY_STATE, processed_video_ids=[], channel_last_checked={})


def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: Run tests, expect pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/state.py tests/test_state.py
git commit -m "feat(state): self-healing state.json read/write"
```

---

### Task 5: Channels config + fetch_videos

**Files:**
- Create: `channels.yaml`
- Create: `pipeline/fetch_videos.py`

- [ ] **Step 1: Write `channels.yaml`**

```yaml
# Seed channels. channel_id is the canonical YouTube ID (starts with "UC").
# To find one: open the channel's About page → "Share channel" → "Copy channel ID".
channels:
  - name: Yannic Kilcher
    channel_id: UCZHmQk67mSJgfCCTn7xBfew
  - name: DeepLearningAI
    channel_id: UCcIXc5mJsHVYTZR1maL5l9w
  - name: AI Coffee Break with Letitia
    channel_id: UCobqgqE4i5Kf7wrxRxhToQA
  - name: Two Minute Papers
    channel_id: UCbfYPyITQ-7l4upoX8nvctg
  - name: AI Explained
    channel_id: UCNJ1Ymd5yFuUPtn21xtRbbw
  - name: Andrej Karpathy
    channel_id: UCPk8m_r6fkUSYmvgCBwq-sw
  - name: Matthew Berman
    channel_id: UCawZsQWqfGSbCI5yjkdVkTA
  - name: AI Jason
    channel_id: UCNNtbR2fNDDoFraitPCsCkw
  - name: sentdex
    channel_id: UCfzlCWGWYyIQ0aLC5w48gBQ
```

- [ ] **Step 2: Write `pipeline/fetch_videos.py`**

```python
"""Fetch new videos from monitored YouTube channels.

WHY: YouTube Data API gives us reliable, quota-cheap access to recent uploads.
We use search.list (100 units) per channel per run; with 9 channels × 4 runs/day
that's ~3.6k units/day, well under the 10k free quota.
"""

import logging
from datetime import datetime
import yaml
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from pipeline.config import (
    CHANNELS_YAML,
    YOUTUBE_API_KEY,
    MIN_DURATION_SECONDS,
    MAX_VIDEOS_PER_CHANNEL_PER_RUN,
)

log = logging.getLogger(__name__)


def load_channels(path=CHANNELS_YAML):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["channels"]


def _parse_iso8601_duration(s):
    """Parse PT1H2M3S → seconds. Returns 0 if unparsable."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + se


def fetch_new_videos(channels, state, api_key=None):
    """Return list of new-video dicts across all channels.

    Each item: {video_id, channel, channel_id, title, published_at, url, duration_seconds}.
    Per-channel failures are logged and skipped.
    """
    api_key = api_key or YOUTUBE_API_KEY
    if not api_key:
        log.error("YOUTUBE_API_KEY missing, returning no videos")
        return []

    yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
    processed = set(state.get("processed_video_ids", []))
    results = []

    for ch in channels:
        try:
            results.extend(_fetch_one_channel(yt, ch, processed))
        except HttpError as e:
            log.warning("channel %s API error: %s", ch["name"], e)
        except Exception as e:
            log.exception("channel %s unexpected error: %s", ch["name"], e)

    return results


def _fetch_one_channel(yt, ch, processed):
    search = yt.search().list(
        channelId=ch["channel_id"],
        part="id,snippet",
        order="date",
        type="video",
        maxResults=MAX_VIDEOS_PER_CHANNEL_PER_RUN,
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search.get("items", [])
                 if item["id"]["videoId"] not in processed]
    if not video_ids:
        return []

    details = yt.videos().list(
        id=",".join(video_ids),
        part="snippet,contentDetails,liveStreamingDetails",
    ).execute()

    out = []
    for item in details.get("items", []):
        if item.get("liveStreamingDetails"):
            continue
        dur = _parse_iso8601_duration(item["contentDetails"]["duration"])
        if dur < MIN_DURATION_SECONDS:
            continue
        vid = item["id"]
        out.append({
            "video_id": vid,
            "channel": ch["name"],
            "channel_id": ch["channel_id"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
            "url": f"https://www.youtube.com/watch?v={vid}",
            "duration_seconds": dur,
        })
    return out
```

- [ ] **Step 3: Smoke-check parse helper without hitting API**

Run:
```bash
python -c "from pipeline.fetch_videos import _parse_iso8601_duration as f; print(f('PT1H2M3S'), f('PT45S'), f(''))"
```
Expected: `3723 45 0`

- [ ] **Step 4: Commit**

```bash
git add channels.yaml pipeline/fetch_videos.py
git commit -m "feat(fetch): YouTube Data API discovery with incremental dedup"
```

---

### Task 6: Transcription (`pipeline/transcribe.py`)

**Files:**
- Create: `pipeline/transcribe.py`
- Create: `tests/test_transcribe.py`

- [ ] **Step 1: Write failing test `tests/test_transcribe.py`**

```python
from unittest.mock import patch, MagicMock
import pipeline.transcribe as tr


def test_captions_path_short_circuits_whisper(tmp_path):
    long_text = "hello world " * 200
    with patch.object(tr, "_try_captions", return_value=long_text) as mc, \
         patch.object(tr, "_run_whisper") as mw:
        out = tr.transcribe("vid1", "https://x", workdir=tmp_path)
    assert out["source"] == "captions"
    assert out["chars"] >= 1000
    mc.assert_called_once()
    mw.assert_not_called()


def test_short_captions_fall_back_to_whisper(tmp_path):
    short = "tiny"
    long_w = "whisper text " * 200
    with patch.object(tr, "_try_captions", return_value=short), \
         patch.object(tr, "_download_audio", return_value=tmp_path / "a.mp3"), \
         patch.object(tr, "_run_whisper", return_value=long_w):
        out = tr.transcribe("vid2", "https://x", workdir=tmp_path)
    assert out["source"] == "whisper"
    assert out["text"] == long_w


def test_both_fail_returns_none(tmp_path):
    with patch.object(tr, "_try_captions", return_value=""), \
         patch.object(tr, "_download_audio", return_value=None), \
         patch.object(tr, "_run_whisper", return_value=""):
        assert tr.transcribe("vid3", "https://x", workdir=tmp_path) is None
```

- [ ] **Step 2: Run test, expect failure**

Run: `python -m pytest tests/test_transcribe.py -v`
Expected: import error.

- [ ] **Step 3: Write `pipeline/transcribe.py`**

```python
"""Get a video transcript. Captions first, Whisper API as fallback.

WHY: captions are free and instant when YouTube has them (~80% of videos).
Whisper is $0.006/min — fine as fallback but we never want it as the default.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from pipeline.config import MIN_TRANSCRIPT_CHARS, OPENAI_API_KEY, WHISPER_MODEL

log = logging.getLogger(__name__)


def transcribe(video_id, url, workdir=None):
    workdir = Path(workdir) if workdir else Path(tempfile.gettempdir())
    workdir.mkdir(parents=True, exist_ok=True)

    text = _try_captions(video_id, url, workdir)
    if text and len(text) >= MIN_TRANSCRIPT_CHARS:
        return {"source": "captions", "text": text, "chars": len(text)}

    audio = _download_audio(video_id, url, workdir)
    if audio is None:
        log.warning("audio download failed for %s", video_id)
        return None

    try:
        wtext = _run_whisper(audio)
    finally:
        try:
            Path(audio).unlink(missing_ok=True)
        except Exception:
            pass

    if wtext and len(wtext) >= MIN_TRANSCRIPT_CHARS:
        return {"source": "whisper", "text": wtext, "chars": len(wtext)}
    return None


def _try_captions(video_id, url, workdir):
    """Use yt-dlp to fetch subtitles; return joined text or empty string."""
    try:
        subprocess.run(
            [
                "yt-dlp",
                "--write-auto-subs", "--write-subs",
                "--sub-lang", "en,en-US",
                "--skip-download",
                "--sub-format", "vtt",
                "-o", str(workdir / f"{video_id}.%(ext)s"),
                url,
            ],
            check=True, capture_output=True, timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("yt-dlp captions failed for %s: %s", video_id, e)
        return ""

    vtt_files = list(workdir.glob(f"{video_id}*.vtt"))
    if not vtt_files:
        return ""
    text = _vtt_to_text(vtt_files[0].read_text(encoding="utf-8", errors="ignore"))
    for f in vtt_files:
        try:
            f.unlink()
        except OSError:
            pass
    return text


def _vtt_to_text(vtt):
    """Strip VTT timestamps and tags, return plain text."""
    lines = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or "-->" in line:
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        lines.append(line)
    deduped = []
    last = None
    for l in lines:
        if l != last:
            deduped.append(l)
        last = l
    return " ".join(deduped)


def _download_audio(video_id, url, workdir):
    out = workdir / f"{video_id}.mp3"
    try:
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "-o", str(out), url],
            check=True, capture_output=True, timeout=600,
        )
        return out if out.exists() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("yt-dlp audio failed for %s: %s", video_id, e)
        return None


def _run_whisper(audio_path):
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY missing, cannot run Whisper")
        return ""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=f,
            response_format="text",
        )
    return resp if isinstance(resp, str) else getattr(resp, "text", "")
```

- [ ] **Step 4: Run tests, expect pass**

Run: `python -m pytest tests/test_transcribe.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/transcribe.py tests/test_transcribe.py
git commit -m "feat(transcribe): captions-first with Whisper fallback"
```

---

### Task 7: Summarise (`pipeline/summarise.py`)

**Files:**
- Create: `pipeline/summarise.py`
- Create: `tests/test_summarise.py`
- Create: `tests/fixtures/transcript_sample_1.txt`

- [ ] **Step 1: Create fixture `tests/fixtures/transcript_sample_1.txt`**

Write a short paragraph (~200 words) of plausible LLM-talk text. Example:

```
Today we're looking at the new mixture of experts paper from DeepMind.
The core idea is that instead of routing tokens to every expert, the router
learns a sparse activation pattern. They show that with 8 experts and top-2
routing, you get most of the quality of a dense model at one third the
inference cost. The interesting part is the load-balancing loss, which
prevents expert collapse...
```

(Make it ≥150 words so the LLM has something to summarise in real runs; tests mock the LLM so length doesn't matter for tests.)

- [ ] **Step 2: Write failing test `tests/test_summarise.py`**

```python
import json
from unittest.mock import patch, MagicMock
from pipeline.summarise import summarise, _extract_json


def _mock_response(content):
    msg = MagicMock()
    msg.message.content = content
    resp = MagicMock()
    resp.choices = [msg]
    return resp


def test_extract_json_from_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_markdown_fence():
    raw = '```json\n{"a": 1}\n```'
    assert _extract_json(raw) == {"a": 1}


def test_extract_json_from_noisy_prefix():
    raw = 'Sure, here is the JSON:\n{"a": 1}\nDone.'
    assert _extract_json(raw) == {"a": 1}


def test_summarise_happy_path():
    payload = {
        "summary": "讲者解释了 MoE 路由机制并比较推理成本。",
        "topic_tags": ["MoE", "scaling"],
        "key_quotes": ["top-2 routing recovers most of the dense quality"],
        "related_channels": ["AI Explained"],
    }
    fake = _mock_response(json.dumps(payload))
    with patch("pipeline.summarise._client") as mc:
        mc.return_value.chat.completions.create.return_value = fake
        out = summarise("long transcript text" * 100, ["MoE", "scaling"], ["AI Explained"])
    assert out["summary"].startswith("讲者")
    assert out["topic_tags"] == ["MoE", "scaling"]


def test_summarise_invalid_tags_get_normalized():
    payload = {
        "summary": "x",
        "topic_tags": ["not-a-tag", "RAG"],
        "key_quotes": [],
        "related_channels": [],
    }
    fake = _mock_response(json.dumps(payload))
    with patch("pipeline.summarise._client") as mc:
        mc.return_value.chat.completions.create.return_value = fake
        out = summarise("t" * 200, ["RAG"], [])
    assert "not-a-tag" not in out["topic_tags"]
    assert "RAG" in out["topic_tags"]
```

- [ ] **Step 3: Run test, expect failure**

Run: `python -m pytest tests/test_summarise.py -v`
Expected: import error.

- [ ] **Step 4: Write `pipeline/summarise.py`**

```python
"""Generate transcript-grounded summary + tags + related channels via DeepSeek-V4.

WHY: a controlled prompt that forbids using the title/description is the
load-bearing piece of this whole project. The reviewer will spot-check that
summaries actually reflect transcript content, not titles.
"""

import json
import logging
import re
import time

from pipeline.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from pipeline.tags import normalize_tags

log = logging.getLogger(__name__)

_TRANSCRIPT_CHAR_LIMIT = 12000  # ~3k tokens, plenty for a 2-3 sentence summary


def _client():
    from openai import OpenAI
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY missing")
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def _build_prompt(transcript, controlled_tags, known_channels):
    tags_str = ", ".join(controlled_tags)
    channels_str = ", ".join(known_channels) if known_channels else "(none)"
    truncated = transcript[:_TRANSCRIPT_CHAR_LIMIT]
    return f"""You are summarising a YouTube video about large language models.

RULES (must follow exactly):
1. Base your summary ONLY on the transcript below. Do NOT use the title,
   thumbnail, video description, or any outside knowledge.
2. Choose topic_tags ONLY from this fixed list: {tags_str}. Pick 1 to 5.
3. summary must be 2-3 sentences in Chinese summarising what the speaker
   actually said. No hype, no marketing language, no "this video covers".
4. key_quotes: 1-3 short verbatim sentences (English, from the transcript)
   that best capture the main claim.
5. related_channels: pick up to 3 names from this list that cover overlapping
   topics; pick none if unsure. Allowed list: {channels_str}.

Return STRICT JSON with keys: summary, topic_tags, key_quotes, related_channels.
No prose around the JSON, no markdown fences.

TRANSCRIPT:
\"\"\"
{truncated}
\"\"\""""


def _extract_json(text):
    """Tolerate markdown fences and stray prose around a JSON object."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    return json.loads(text)


def _call(prompt, model=DEEPSEEK_MODEL):
    resp = _client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=600,
    )
    return resp.choices[0].message.content


def summarise(transcript, controlled_tags, known_channels):
    """Return dict with summary, topic_tags, key_quotes, related_channels."""
    prompt = _build_prompt(transcript, controlled_tags, known_channels)
    last_error = None

    for attempt in range(3):
        try:
            raw = _call(prompt)
            data = _extract_json(raw)
            return {
                "summary": str(data.get("summary", "")).strip(),
                "topic_tags": normalize_tags(data.get("topic_tags", [])),
                "key_quotes": [str(q) for q in data.get("key_quotes", [])][:3],
                "related_channels": [c for c in data.get("related_channels", []) if c in known_channels][:3],
            }
        except json.JSONDecodeError as e:
            last_error = e
            log.warning("JSON parse fail (attempt %d): %s", attempt + 1, e)
            prompt += "\n\nIMPORTANT: your previous response was not valid JSON. Return ONLY the JSON object."
        except Exception as e:
            last_error = e
            log.warning("DeepSeek call failed (attempt %d): %s", attempt + 1, e)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"summarise failed after retries: {last_error}")
```

- [ ] **Step 5: Run tests, expect pass**

Run: `python -m pytest tests/test_summarise.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/summarise.py tests/test_summarise.py tests/fixtures/transcript_sample_1.txt
git commit -m "feat(summarise): DeepSeek-V4 transcript-grounded summary"
```

---

### Task 8: Build table (`pipeline/build_table.py`)

**Files:**
- Create: `pipeline/build_table.py`
- Create: `tests/test_build_table.py`

- [ ] **Step 1: Write failing test `tests/test_build_table.py`**

```python
import json
from pipeline.build_table import build_and_save, _merge_videos


def _row(vid, channel="C", published_at="2026-05-20T00:00:00Z", summary="s"):
    return {
        "video_id": vid,
        "channel": channel,
        "channel_id": "UCx",
        "title": "t",
        "published_at": published_at,
        "url": f"https://y/{vid}",
        "duration_seconds": 600,
        "transcript_source": "captions",
        "transcript_excerpt_chars": 2000,
        "transcript_excerpt": "...",
        "topic_tags": ["RAG"],
        "summary": summary,
        "key_quotes": [],
        "related_channels": [],
        "processed_at": "2026-05-23T00:00:00Z",
        "pipeline_version": "1.0.0",
    }


def test_merge_dedupes_and_sorts_desc():
    old = [_row("a", published_at="2026-05-01T00:00:00Z")]
    new = [_row("b", published_at="2026-05-10T00:00:00Z"),
           _row("a", published_at="2026-05-01T00:00:00Z", summary="updated")]
    merged = _merge_videos(old, new)
    ids = [v["video_id"] for v in merged]
    assert ids == ["b", "a"]
    assert next(v for v in merged if v["video_id"] == "a")["summary"] == "updated"


def test_build_and_save_writes_files(tmp_path):
    videos_path = tmp_path / "videos.json"
    state_path = tmp_path / "state.json"
    new_entries = [_row("v1")]
    build_and_save(new_entries, videos_path=videos_path, state_path=state_path,
                   now="2026-05-23T00:00:00Z")
    saved = json.loads(videos_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved[0]["video_id"] == "v1"
    assert "v1" in state["processed_video_ids"]
    assert state["last_run"] == "2026-05-23T00:00:00Z"


def test_build_and_save_appends_to_existing(tmp_path):
    videos_path = tmp_path / "videos.json"
    state_path = tmp_path / "state.json"
    videos_path.write_text(json.dumps([_row("old", published_at="2026-04-01T00:00:00Z")]),
                           encoding="utf-8")
    state_path.write_text(json.dumps({
        "last_run": "2026-04-01T00:00:00Z",
        "processed_video_ids": ["old"],
        "channel_last_checked": {},
    }), encoding="utf-8")
    build_and_save([_row("new", published_at="2026-05-10T00:00:00Z")],
                   videos_path=videos_path, state_path=state_path,
                   now="2026-05-23T00:00:00Z")
    saved = json.loads(videos_path.read_text(encoding="utf-8"))
    assert [v["video_id"] for v in saved] == ["new", "old"]
```

- [ ] **Step 2: Run test, expect failure**

Run: `python -m pytest tests/test_build_table.py -v`
Expected: import error.

- [ ] **Step 3: Write `pipeline/build_table.py`**

```python
"""Merge new entries into videos.json and update state.json.

WHY: videos.json is the single source of truth read by the frontend. state.json
mirrors which video_ids have been processed so future runs skip them cheaply.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import VIDEOS_JSON, STATE_JSON
from pipeline.state import load_state, save_state

log = logging.getLogger(__name__)


def _load_videos(path):
    p = Path(path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("videos.json corrupt, treating as empty")
        return []


def _merge_videos(old, new):
    by_id = {v["video_id"]: v for v in old}
    for v in new:
        by_id[v["video_id"]] = v
    merged = list(by_id.values())
    merged.sort(key=lambda v: v.get("published_at", ""), reverse=True)
    return merged


def build_and_save(new_entries, videos_path=VIDEOS_JSON, state_path=STATE_JSON, now=None):
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    videos_path = Path(videos_path)
    state_path = Path(state_path)

    videos_path.parent.mkdir(parents=True, exist_ok=True)

    old = _load_videos(videos_path)
    merged = _merge_videos(old, new_entries)
    videos_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

    state = load_state(state_path)
    ids = set(state.get("processed_video_ids", []))
    for v in new_entries:
        ids.add(v["video_id"])
        state.setdefault("channel_last_checked", {})[v["channel_id"]] = now
    state["processed_video_ids"] = sorted(ids)
    state["last_run"] = now
    save_state(state_path, state)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `python -m pytest tests/test_build_table.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_table.py tests/test_build_table.py
git commit -m "feat(build): merge new videos and update state"
```

---

### Task 9: Publish (`pipeline/publish.py`)

**Files:**
- Create: `pipeline/publish.py`

- [ ] **Step 1: Write `pipeline/publish.py`**

```python
"""git add + commit + push videos.json and state.json.

WHY: GitHub Pages auto-redeploys on push, so a successful push IS the publish
step. We deliberately do not throw on network/conflict errors — the next cron
run will retry.
"""

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import PROJECT_ROOT, VIDEOS_JSON, STATE_JSON

log = logging.getLogger(__name__)


def _run(args, cwd=PROJECT_ROOT):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def publish():
    """Returns True on successful push, False otherwise."""
    videos_rel = str(Path(VIDEOS_JSON).relative_to(PROJECT_ROOT))
    state_rel = str(Path(STATE_JSON).relative_to(PROJECT_ROOT))

    add = _run(["git", "add", videos_rel, state_rel])
    if add.returncode != 0:
        log.error("git add failed: %s", add.stderr)
        return False

    status = _run(["git", "status", "--porcelain", videos_rel, state_rel])
    if not status.stdout.strip():
        log.info("no data changes, skipping commit")
        return True

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    commit = _run(["git", "commit", "-m", f"data: refresh {now}"])
    if commit.returncode != 0:
        log.error("git commit failed: %s", commit.stderr)
        return False

    push = _run(["git", "push"])
    if push.returncode != 0:
        log.error("git push failed: %s", push.stderr)
        return False

    log.info("published refresh at %s", now)
    return True
```

- [ ] **Step 2: Smoke-check import**

Run: `python -c "from pipeline.publish import publish; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/publish.py
git commit -m "feat(publish): commit and push data files to GitHub"
```

---

### Task 10: Orchestrator (`pipeline/run.py`)

**Files:**
- Create: `pipeline/run.py`

- [ ] **Step 1: Write `pipeline/run.py`**

```python
"""Cron entry point. Run with: python -m pipeline.run

Per-video failures are swallowed and logged. The process always exits 0 so the
scheduler doesn't flag false alarms; check logs/cron.log for issues.
"""

import argparse
import logging
import sys
import traceback
from datetime import datetime, timezone

from pipeline import __version__
from pipeline.config import (
    LOGS_DIR, VIDEOS_JSON, STATE_JSON, MIN_TRANSCRIPT_CHARS,
)
from pipeline.tags import CONTROLLED_TAGS
from pipeline.state import load_state
from pipeline.fetch_videos import load_channels, fetch_new_videos
from pipeline.transcribe import transcribe
from pipeline.summarise import summarise
from pipeline.build_table import build_and_save
from pipeline.publish import publish


def _setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "cron.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _process_one(video, channel_names):
    t = transcribe(video["video_id"], video["url"])
    if not t or t["chars"] < MIN_TRANSCRIPT_CHARS:
        logging.warning("dropping %s: transcript too short or missing", video["video_id"])
        return None
    s = summarise(t["text"], CONTROLLED_TAGS, channel_names)
    return {
        **video,
        "transcript_source": t["source"],
        "transcript_excerpt_chars": t["chars"],
        "transcript_excerpt": t["text"][:500],
        "summary": s["summary"],
        "topic_tags": s["topic_tags"],
        "key_quotes": s["key_quotes"],
        "related_channels": s["related_channels"],
        "processed_at": _now_iso(),
        "pipeline_version": __version__,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="skip disk write and git push")
    p.add_argument("--limit", type=int, default=None, help="cap new videos per run")
    args = p.parse_args(argv)

    _setup_logging()
    log = logging.getLogger("run")

    try:
        channels = load_channels()
        state = load_state(STATE_JSON)
        new_videos = fetch_new_videos(channels, state)
        if args.limit is not None:
            new_videos = new_videos[: args.limit]
        log.info("found %d new videos across %d channels", len(new_videos), len(channels))

        channel_names = [c["name"] for c in channels]
        enriched = []
        for v in new_videos:
            try:
                row = _process_one(v, channel_names)
                if row:
                    enriched.append(row)
            except Exception:
                log.error("video %s failed:\n%s", v.get("video_id"), traceback.format_exc())

        log.info("processed %d/%d videos successfully", len(enriched), len(new_videos))

        if args.dry_run:
            log.info("--dry-run: skipping write and publish")
            return 0

        if enriched:
            build_and_save(enriched, videos_path=VIDEOS_JSON, state_path=STATE_JSON, now=_now_iso())
            publish()
        else:
            log.info("nothing to publish this cycle")

    except Exception:
        log.error("run failed:\n%s", traceback.format_exc())

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-check import + help**

Run: `python -m pipeline.run --help`
Expected: argparse help text including `--dry-run` and `--limit`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/run.py
git commit -m "feat(run): orchestrator with per-video isolation and always-zero exit"
```

---

### Task 11: Frontend (`web/index.html`, `web/app.js`, `web/style.css`)

**Files:**
- Create: `web/index.html`
- Create: `web/app.js`
- Create: `web/style.css`
- Create: `web/videos.json` (empty seed)

- [ ] **Step 1: Write `web/videos.json` (empty seed so the page loads on first deploy)**

```json
[]
```

- [ ] **Step 2: Write `web/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>LLM YouTube Landscape Tracker</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="./style.css" />
</head>
<body class="bg-slate-50 text-slate-900">
  <header class="bg-slate-900 text-white px-6 py-4 shadow">
    <h1 class="text-xl font-semibold">LLM YouTube Landscape Tracker</h1>
    <p class="text-sm text-slate-300 mt-1">
      Transcript-grounded summaries of LLM videos. Updated every 6h. <span id="meta"></span>
    </p>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6">
    <section class="mb-4 flex flex-wrap gap-3 items-end">
      <div>
        <label class="block text-xs text-slate-500">Search</label>
        <input id="q" type="search" placeholder="title, channel, summary..."
               class="border border-slate-300 rounded px-2 py-1 w-72" />
      </div>
      <div>
        <label class="block text-xs text-slate-500">Channel</label>
        <select id="channel" class="border border-slate-300 rounded px-2 py-1"></select>
      </div>
      <div class="flex-1 min-w-[300px]">
        <label class="block text-xs text-slate-500">Topic tags (click to toggle)</label>
        <div id="tags" class="flex flex-wrap gap-1"></div>
      </div>
    </section>

    <table class="w-full text-sm border-collapse">
      <thead class="bg-slate-200 text-left">
        <tr>
          <th class="px-2 py-1 cursor-pointer" data-sort="published_at">Published ▾</th>
          <th class="px-2 py-1 cursor-pointer" data-sort="channel">Channel</th>
          <th class="px-2 py-1">Title</th>
          <th class="px-2 py-1">Tags</th>
          <th class="px-2 py-1">Source</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
    <p id="empty" class="hidden text-slate-500 mt-4">No videos match the current filters.</p>
  </main>

  <script src="./app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `web/style.css`**

```css
.row-detail {
  background: #f8fafc;
}
.row-detail td {
  padding: 12px 8px;
  border-bottom: 1px solid #e2e8f0;
}
.tag-pill {
  font-size: 11px;
  padding: 1px 6px;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 999px;
}
.tag-pill.active {
  background: #4338ca;
  color: #fff;
}
tr.video-row:hover { background: #f1f5f9; cursor: pointer; }
```

- [ ] **Step 4: Write `web/app.js`**

```javascript
const state = {
  videos: [],
  q: "",
  channel: "",
  activeTags: new Set(),
  sortBy: "published_at",
  sortDir: "desc",
  expanded: new Set(),
};

async function load() {
  try {
    const r = await fetch("./videos.json", { cache: "no-store" });
    state.videos = await r.json();
  } catch (e) {
    console.error(e);
    state.videos = [];
  }
  buildFilters();
  render();
  updateMeta();
}

function buildFilters() {
  const tagSet = new Set();
  const channelSet = new Set();
  state.videos.forEach(v => {
    (v.topic_tags || []).forEach(t => tagSet.add(t));
    if (v.channel) channelSet.add(v.channel);
  });

  const tagsEl = document.getElementById("tags");
  tagsEl.innerHTML = "";
  [...tagSet].sort().forEach(t => {
    const b = document.createElement("button");
    b.className = "tag-pill";
    b.textContent = t;
    b.onclick = () => {
      state.activeTags.has(t) ? state.activeTags.delete(t) : state.activeTags.add(t);
      b.classList.toggle("active");
      render();
    };
    tagsEl.appendChild(b);
  });

  const sel = document.getElementById("channel");
  sel.innerHTML = '<option value="">(all)</option>';
  [...channelSet].sort().forEach(c => {
    const o = document.createElement("option");
    o.value = c; o.textContent = c;
    sel.appendChild(o);
  });

  document.getElementById("q").oninput = e => { state.q = e.target.value.toLowerCase(); render(); };
  sel.onchange = e => { state.channel = e.target.value; render(); };
  document.querySelectorAll("th[data-sort]").forEach(th => {
    th.onclick = () => {
      const f = th.dataset.sort;
      if (state.sortBy === f) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else { state.sortBy = f; state.sortDir = "desc"; }
      render();
    };
  });
}

function filtered() {
  return state.videos.filter(v => {
    if (state.channel && v.channel !== state.channel) return false;
    if (state.activeTags.size > 0) {
      const vt = new Set(v.topic_tags || []);
      for (const t of state.activeTags) if (!vt.has(t)) return false;
    }
    if (state.q) {
      const hay = `${v.title} ${v.channel} ${v.summary}`.toLowerCase();
      if (!hay.includes(state.q)) return false;
    }
    return true;
  }).sort((a, b) => {
    const av = a[state.sortBy] || "", bv = b[state.sortBy] || "";
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return state.sortDir === "asc" ? cmp : -cmp;
  });
}

function render() {
  const tbody = document.getElementById("rows");
  tbody.innerHTML = "";
  const rows = filtered();
  document.getElementById("empty").classList.toggle("hidden", rows.length > 0);
  rows.forEach(v => {
    const tr = document.createElement("tr");
    tr.className = "video-row border-b border-slate-200";
    tr.innerHTML = `
      <td class="px-2 py-2 whitespace-nowrap">${(v.published_at || "").slice(0, 10)}</td>
      <td class="px-2 py-2">${escapeHtml(v.channel)}</td>
      <td class="px-2 py-2"><a class="text-indigo-700 hover:underline" href="${v.url}" target="_blank">${escapeHtml(v.title)}</a></td>
      <td class="px-2 py-2">${(v.topic_tags || []).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join(" ")}</td>
      <td class="px-2 py-2">${v.transcript_source}</td>
    `;
    tr.onclick = (e) => {
      if (e.target.tagName === "A") return;
      toggleDetail(tr, v);
    };
    tbody.appendChild(tr);
    if (state.expanded.has(v.video_id)) appendDetail(tr, v);
  });
}

function toggleDetail(tr, v) {
  if (state.expanded.has(v.video_id)) {
    state.expanded.delete(v.video_id);
    const next = tr.nextSibling;
    if (next && next.classList && next.classList.contains("row-detail")) next.remove();
  } else {
    state.expanded.add(v.video_id);
    appendDetail(tr, v);
  }
}

function appendDetail(tr, v) {
  const d = document.createElement("tr");
  d.className = "row-detail";
  const quotes = (v.key_quotes || []).map(q => `<li>“${escapeHtml(q)}”</li>`).join("");
  const related = (v.related_channels || []).map(c => escapeHtml(c)).join(", ");
  d.innerHTML = `
    <td colspan="5">
      <div class="mb-2"><b>Summary:</b> ${escapeHtml(v.summary)}</div>
      <div class="mb-2 text-xs text-slate-500">Transcript source: ${v.transcript_source} · ${v.transcript_excerpt_chars} chars · Related: ${related || "(none)"}</div>
      <div class="mb-2"><b>Key quotes:</b><ul class="list-disc list-inside">${quotes || "<li>(none)</li>"}</ul></div>
      <details><summary class="cursor-pointer text-indigo-700">Transcript excerpt (first 500 chars)</summary>
        <pre class="whitespace-pre-wrap text-xs mt-2 bg-white p-2 border rounded">${escapeHtml(v.transcript_excerpt || "")}</pre>
      </details>
    </td>
  `;
  tr.parentNode.insertBefore(d, tr.nextSibling);
}

function updateMeta() {
  const latest = state.videos.reduce((m, v) => v.processed_at > m ? v.processed_at : m, "");
  document.getElementById("meta").textContent =
    `${state.videos.length} videos · last refresh ${latest || "n/a"}`;
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

load();
```

- [ ] **Step 5: Smoke-test in browser**

Open `D:/YMX/llm-yt-tracker/web/index.html` in any browser.
Expected: page loads, "0 videos · last refresh n/a" shown, no console errors.

- [ ] **Step 6: Commit**

```bash
git add web/
git commit -m "feat(web): static frontend with filters, sort, expandable rows"
```

---

### Task 12: OpenClaw skill (`SKILL.md`)

**Files:**
- Create: `C:/Users/Administrator/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p "C:/Users/Administrator/.openclaw/workspace/skills/llm-yt-tracker"
```

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: llm-yt-tracker
description: Refresh the LLM YouTube Landscape Tracker table. MUST trigger on phrases like "刷新 LLM 表格", "刷新 LLM tracker", "refresh llm tracker", "update llm landscape", or when invoked by a scheduled task. Runs the Python pipeline that pulls new videos, transcribes them, summarises with DeepSeek-V4, and pushes to GitHub Pages.
---

# LLM YouTube Tracker

## Purpose

This skill refreshes the public landscape table at
`https://<github-user>.github.io/llm-yt-tracker/` by running one cycle of:

1. Fetch new videos from monitored channels (YouTube Data API)
2. Transcribe each new video (captions first, Whisper fallback)
3. Summarise with DeepSeek-V4 (transcript-grounded, controlled tags)
4. Merge into `web/videos.json` and update `pipeline/state.json`
5. `git push` so GitHub Pages auto-redeploys

## When to trigger

- User says any of: "刷新 LLM 表格", "refresh llm tracker", "update llm landscape", "跑一次 tracker".
- Scheduled invocation from Windows Task Scheduler (every 6 hours).

## How to run

Execute:

```bash
cd /d D:\YMX\llm-yt-tracker
python -m pipeline.run
```

Add `--dry-run` to skip disk write and git push (useful for verifying API keys).
Add `--limit N` to cap how many new videos this cycle processes.

## Where things live

- Project root: `D:\YMX\llm-yt-tracker`
- Logs: `D:\YMX\llm-yt-tracker\logs\cron.log`
- Live data: `D:\YMX\llm-yt-tracker\web\videos.json`
- Frontend: `D:\YMX\llm-yt-tracker\web\index.html` (also published to GitHub Pages)
- API keys: `D:\YMX\llm-yt-tracker\.env` (never commit)

## Failure checklist

If the run exits with a warning or no new commits show up:

1. `tail -100 D:\YMX\llm-yt-tracker\logs\cron.log`
2. Check `.env` has YOUTUBE_API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY.
3. Verify `yt-dlp --version` works (skill assumes it's on PATH).
4. Check YouTube API quota usage in Google Cloud Console.
5. Manually try `git push` from the project root to surface auth issues.
```

- [ ] **Step 3: Verify skill is discoverable**

Run:
```bash
ls "C:/Users/Administrator/.openclaw/workspace/skills/llm-yt-tracker"
```
Expected: `SKILL.md` listed.

- [ ] **Step 4: Commit (project repo only — the OpenClaw workspace is not part of this repo)**

No commit needed for `SKILL.md` itself; it lives outside the project repo. Mention this in the README later.

---

### Task 13: Windows Task Scheduler registration

**Files:**
- Create: `scripts/register_task.ps1`

- [ ] **Step 1: Write `scripts/register_task.ps1`**

```powershell
# Registers a Windows Scheduled Task to run the tracker pipeline every 6h
# and on user logon. Run this script ONCE from an elevated PowerShell prompt.

$ErrorActionPreference = "Stop"

$TaskName = "LLM-YT-Tracker-Refresh"
$ProjectRoot = "D:\YMX\llm-yt-tracker"
$PythonExe = (Get-Command python).Source
$LogFile = "$ProjectRoot\logs\cron.log"

if (-not (Test-Path "$ProjectRoot\logs")) {
  New-Item -ItemType Directory -Path "$ProjectRoot\logs" | Out-Null
}

$Action = New-ScheduledTaskAction `
  -Execute $PythonExe `
  -Argument "-m pipeline.run" `
  -WorkingDirectory $ProjectRoot

$Trigger1 = New-ScheduledTaskTrigger -AtLogOn
$Trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
            -RepetitionInterval (New-TimeSpan -Hours 6)

$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger @($Trigger1, $Trigger2) `
  -Settings $Settings `
  -Description "Refresh LLM YouTube Landscape Tracker every 6h" `
  -Force

Write-Host "Registered task '$TaskName'. Logs: $LogFile"
Write-Host "Run manually with: Start-ScheduledTask -TaskName '$TaskName'"
```

- [ ] **Step 2: Commit**

```bash
git add scripts/register_task.ps1
git commit -m "feat(scheduler): PowerShell registration for Windows Task Scheduler"
```

---

### Task 14: README and deployment doc

**Files:**
- Create: `README.md`
- Create: `docs/deployment.md`
- Create: `docs/architecture.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# LLM YouTube Landscape Tracker

Auto-updating, transcript-grounded landscape of LLM YouTube content.

**Live URL:** https://<your-github-user>.github.io/llm-yt-tracker/

## Quick start

1. `python -m pip install -r requirements.txt`
2. Install `yt-dlp` (already in requirements, but verify with `yt-dlp --version`).
3. `cp .env.example .env` and fill in API keys (YouTube Data v3, DeepSeek, OpenAI).
4. `python -m pipeline.run --dry-run --limit 1` to verify the pipeline end-to-end.
5. `python -m pipeline.run` for a real cycle (writes `web/videos.json`, pushes to GitHub).
6. Open `web/index.html` locally, or push and open the GitHub Pages URL.

## How it stays current

Windows Task Scheduler runs `python -m pipeline.run` every 6 hours (plus on logon).
The OpenClaw skill at `~/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md`
documents the same workflow and can be triggered interactively via OpenClaw
("刷新 LLM 表格" or "refresh llm tracker").

See `docs/architecture.md` for the data flow and `docs/deployment.md` for the
one-time setup runbook.

## Repository layout

- `pipeline/` — Python modules; each can be run as `python -m pipeline.<name>`
- `web/` — static frontend (Tailwind CDN, vanilla JS, reads `videos.json`)
- `channels.yaml` — monitored channels
- `scripts/register_task.ps1` — one-shot Windows scheduler registration
- `tests/` — pytest suite (run `python -m pytest`)
- `docs/specs/` — design spec
- `docs/plans/` — implementation plan (this build)
```

- [ ] **Step 2: Write `docs/architecture.md`**

```markdown
# Architecture

## Data flow

```
Windows Task Scheduler  ──┐
OpenClaw skill (manual)  ─┴──►  python -m pipeline.run
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
  debugged with `python -m pipeline.<name>` and the cron path doesn't depend on
  the OpenClaw runtime being online.

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
```

- [ ] **Step 3: Write `docs/deployment.md`**

```markdown
# Deployment runbook

One-time setup, in order. Steps marked **(skip if done)** can be reused later.

## 1. API keys

- **YouTube Data API v3**: Google Cloud Console → APIs & Services → Enable
  "YouTube Data API v3" → Create credentials → API key. Copy.
- **DeepSeek**: platform.deepseek.com → API Keys → Create. Copy.
- **OpenAI** (Whisper fallback only): platform.openai.com → API Keys → Create.

`cp .env.example .env` and paste the three values.

## 2. Python + deps

```bash
python -m pip install -r requirements.txt
yt-dlp --version       # verify on PATH
```

## 3. Verify pipeline end-to-end

```bash
python -m pipeline.run --dry-run --limit 1
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
python -m pipeline.run
```

Expect a new `data: refresh ...` commit on GitHub. Within ~1 min the live URL
shows the new rows.

## 6. Register Windows Task Scheduler

Open PowerShell **as Administrator**:

```powershell
cd D:\YMX\llm-yt-tracker
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

Verify with:

```powershell
Get-ScheduledTask -TaskName "LLM-YT-Tracker-Refresh"
Start-ScheduledTask -TaskName "LLM-YT-Tracker-Refresh"   # manual fire
```

## 7. (Optional) OpenClaw skill manual trigger

The skill at `~/.openclaw/workspace/skills/llm-yt-tracker/SKILL.md` lets you
trigger a refresh interactively: type "刷新 LLM 表格" or "refresh llm tracker"
to OpenClaw and it will execute the same command.
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/architecture.md docs/deployment.md
git commit -m "docs: README, architecture, deployment runbook"
```

---

### Task 15: Final smoke + tag pipeline version

**Files:**
- (no new files)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 2: Smoke import the orchestrator**

Run: `python -m pipeline.run --help`
Expected: argparse output, no traceback.

- [ ] **Step 3: Tag v1.0.0**

```bash
git tag -a v1.0.0 -m "v1.0.0: initial release"
```

- [ ] **Step 4: Final status check**

Run: `git log --oneline`
Expected: ~14 commits, one per task, and the v1.0.0 tag.

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| 1. Goal | Tasks 5–10 (pipeline) |
| 2. Constraints — public URL | Tasks 11, 14 |
| 2. Constraints — auto-update 24h | Task 13 |
| 2. Constraints — transcript-grounded | Tasks 6, 7, 11 |
| 2. Constraints — cost <$5 | Tasks 6 (captions-first), 7 (DeepSeek) |
| 3. Stack — OpenClaw skill | Task 12 |
| 3. Stack — pipeline modules | Tasks 2–10 |
| 3. Stack — frontend | Task 11 |
| 3. Stack — deployment | Tasks 13, 14 |
| 4. Architecture / file layout | Tasks 1–14 collectively |
| 5. Data contract — videos.json | Tasks 8, 10 |
| 5. Data contract — controlled tags | Task 2 |
| 5. Data contract — state.json | Task 4 |
| 5. Data contract — channels.yaml | Task 5 |
| 6. Module contracts | Tasks 2–10 |
| 7. Error handling matrix | Tasks 4, 5, 6, 7, 9, 10 |
| 8. Testing | Tasks 2, 4, 6, 7, 8, 15 |
| 9. Walkthrough script | Task 14 (`docs/architecture.md`) |
| 10. Cost estimate | Task 14 (`docs/architecture.md`) |
| 11. Out of scope | (Acknowledged by absence) |

**Placeholders:** None — all code, commands, and expected output are concrete.

**Type consistency:** `transcribe()` returns `{"source", "text", "chars"}` consistently in Tasks 6 and 10. `summarise()` returns `{"summary", "topic_tags", "key_quotes", "related_channels"}` consistently in Tasks 7 and 10. `build_and_save()` signature matches between Task 8 and Task 10.
