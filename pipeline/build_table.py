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
