import json
from pathlib import Path
from pipeline.state import load_state, save_state, EMPTY_STATE


def test_load_state_returns_empty_when_file_missing(tmp_path):
    missing = tmp_path / "no.json"
    assert load_state(missing) == EMPTY_STATE


def test_load_state_self_heals_on_corruption(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_state(bad) == EMPTY_STATE


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    state = {
        "last_run": "2026-05-23T10:00:00Z",
        "processed_video_ids": ["a", "b"],
        "channel_last_checked": {"UCxxx": "2026-05-23T10:00:00Z"},
    }
    save_state(p, state)
    assert load_state(p) == state


def test_empty_state_has_required_keys():
    assert set(EMPTY_STATE.keys()) == {"last_run", "processed_video_ids", "channel_last_checked"}
