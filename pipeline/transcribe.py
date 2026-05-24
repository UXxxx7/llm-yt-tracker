"""Get a video transcript. Captions first, Whisper API as fallback.

WHY: captions are free and instant when YouTube has them (~80% of videos).
Whisper is $0.006/min — fine as fallback but we never want it as the default.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from pipeline.config import MIN_TRANSCRIPT_CHARS, OPENAI_API_KEY, OPENAI_BASE_URL, WHISPER_MODEL

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
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=f,
            response_format="text",
        )
    return resp if isinstance(resp, str) else getattr(resp, "text", "")
