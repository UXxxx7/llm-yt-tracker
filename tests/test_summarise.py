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
