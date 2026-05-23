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
