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
