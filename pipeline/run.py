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
