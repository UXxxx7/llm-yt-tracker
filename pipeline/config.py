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

# Base URLs are overridable so the project can route through a domestic
# OpenAI-compatible proxy. Leave the env var unset to hit the official API.
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
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
