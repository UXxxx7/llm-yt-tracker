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
