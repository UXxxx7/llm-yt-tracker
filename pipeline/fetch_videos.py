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
