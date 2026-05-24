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
        max_tokens=1500,
    )
    return resp.choices[0].message.content


def summarise(transcript, controlled_tags, known_channels):
    """Return dict with summary, topic_tags, key_quotes, related_channels."""
    prompt = _build_prompt(transcript, controlled_tags, known_channels)
    last_error = None

    for attempt in range(3):
        raw = None
        try:
            raw = _call(prompt)
            if not raw or not raw.strip():
                last_error = RuntimeError("empty response from model")
                log.warning("empty response (attempt %d), retrying after backoff", attempt + 1)
                time.sleep(2 ** attempt)
                continue
            data = _extract_json(raw)
            return {
                "summary": str(data.get("summary", "")).strip(),
                "topic_tags": normalize_tags(data.get("topic_tags", [])),
                "key_quotes": [str(q) for q in data.get("key_quotes", [])][:3],
                "related_channels": [c for c in data.get("related_channels", []) if c in known_channels][:3],
            }
        except json.JSONDecodeError as e:
            last_error = e
            log.warning("JSON parse fail (attempt %d): %s | raw[:300]=%r", attempt + 1, e, (raw or "")[:300])
            prompt += "\n\nIMPORTANT: your previous response was not valid JSON. Return ONLY the JSON object."
        except Exception as e:
            last_error = e
            log.warning("DeepSeek call failed (attempt %d): %s", attempt + 1, e)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"summarise failed after retries: {last_error}")
