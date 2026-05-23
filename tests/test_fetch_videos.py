"""Tests for pipeline.fetch_videos."""

from unittest.mock import MagicMock

import pytest

from pipeline.fetch_videos import (
    _parse_iso8601_duration,
    fetch_new_videos,
    load_channels,
)


# ---------- _parse_iso8601_duration ----------


def test_parse_duration_hours_minutes_seconds():
    assert _parse_iso8601_duration("PT1H2M3S") == 3723


def test_parse_duration_seconds_only():
    assert _parse_iso8601_duration("PT45S") == 45


def test_parse_duration_minutes_only():
    assert _parse_iso8601_duration("PT15M") == 900


def test_parse_duration_empty_returns_zero():
    assert _parse_iso8601_duration("") == 0


def test_parse_duration_none_returns_zero():
    assert _parse_iso8601_duration(None) == 0


def test_parse_duration_garbage_returns_zero():
    assert _parse_iso8601_duration("not a duration") == 0


# ---------- load_channels ----------


def test_load_channels_reads_yaml(tmp_path):
    yaml_path = tmp_path / "channels.yaml"
    yaml_path.write_text(
        "channels:\n"
        "  - name: Foo\n"
        "    channel_id: UCfoo\n"
        "  - name: Bar\n"
        "    channel_id: UCbar\n",
        encoding="utf-8",
    )
    chans = load_channels(yaml_path)
    assert isinstance(chans, list)
    assert len(chans) == 2
    assert chans[0]["name"] == "Foo"
    assert chans[0]["channel_id"] == "UCfoo"
    assert chans[1]["name"] == "Bar"
    assert chans[1]["channel_id"] == "UCbar"


# ---------- fetch_new_videos ----------


def test_fetch_new_videos_no_api_key_returns_empty():
    assert fetch_new_videos([{"name": "X", "channel_id": "UCx"}], {}, api_key="") == []
    assert fetch_new_videos([{"name": "X", "channel_id": "UCx"}], {}, api_key=None) == []


def _make_fake_client(search_items, videos_items):
    """Build a fake youtube client whose .search().list().execute() and
    .videos().list().execute() return the given payloads."""
    client = MagicMock()
    search_resource = MagicMock()
    search_list = MagicMock()
    search_list.execute.return_value = {"items": search_items}
    search_resource.list.return_value = search_list
    client.search.return_value = search_resource

    videos_resource = MagicMock()
    videos_list = MagicMock()
    videos_list.execute.return_value = {"items": videos_items}
    videos_resource.list.return_value = videos_list
    client.videos.return_value = videos_resource
    return client


def test_fetch_new_videos_skips_processed_ids(mocker):
    search_items = [
        {"id": {"videoId": "vid_already_done"}},
        {"id": {"videoId": "vid_new"}},
    ]
    videos_items = [
        {
            "id": "vid_new",
            "snippet": {"title": "New One", "publishedAt": "2026-05-23T00:00:00Z"},
            "contentDetails": {"duration": "PT10M"},
        }
    ]
    fake_client = _make_fake_client(search_items, videos_items)
    mocker.patch("pipeline.fetch_videos.build", return_value=fake_client)

    state = {"processed_video_ids": ["vid_already_done"]}
    channels = [{"name": "Test", "channel_id": "UCtest"}]
    out = fetch_new_videos(channels, state, api_key="fake-key")

    ids = [v["video_id"] for v in out]
    assert "vid_already_done" not in ids
    assert "vid_new" in ids
    # Verify videos.list was called only with the new id
    fake_client.videos.return_value.list.assert_called_once()
    call_kwargs = fake_client.videos.return_value.list.call_args.kwargs
    assert call_kwargs["id"] == "vid_new"


def test_fetch_new_videos_filters_short_videos(mocker):
    search_items = [
        {"id": {"videoId": "vid_short"}},
        {"id": {"videoId": "vid_long"}},
    ]
    videos_items = [
        {
            "id": "vid_short",
            "snippet": {"title": "Short", "publishedAt": "2026-05-23T00:00:00Z"},
            "contentDetails": {"duration": "PT30S"},  # 30s < 90s
        },
        {
            "id": "vid_long",
            "snippet": {"title": "Long", "publishedAt": "2026-05-23T00:00:00Z"},
            "contentDetails": {"duration": "PT5M"},  # 300s
        },
    ]
    fake_client = _make_fake_client(search_items, videos_items)
    mocker.patch("pipeline.fetch_videos.build", return_value=fake_client)

    out = fetch_new_videos(
        [{"name": "T", "channel_id": "UCt"}],
        {"processed_video_ids": []},
        api_key="fake-key",
    )
    ids = [v["video_id"] for v in out]
    assert "vid_short" not in ids
    assert "vid_long" in ids
    long_v = next(v for v in out if v["video_id"] == "vid_long")
    assert long_v["duration_seconds"] == 300
    assert long_v["channel"] == "T"
    assert long_v["channel_id"] == "UCt"
    assert long_v["url"] == "https://www.youtube.com/watch?v=vid_long"


def test_fetch_new_videos_skips_live_streams(mocker):
    search_items = [
        {"id": {"videoId": "vid_live"}},
        {"id": {"videoId": "vid_vod"}},
    ]
    videos_items = [
        {
            "id": "vid_live",
            "snippet": {"title": "Live", "publishedAt": "2026-05-23T00:00:00Z"},
            "contentDetails": {"duration": "PT10M"},
            "liveStreamingDetails": {"actualStartTime": "2026-05-23T00:00:00Z"},
        },
        {
            "id": "vid_vod",
            "snippet": {"title": "VOD", "publishedAt": "2026-05-23T00:00:00Z"},
            "contentDetails": {"duration": "PT10M"},
        },
    ]
    fake_client = _make_fake_client(search_items, videos_items)
    mocker.patch("pipeline.fetch_videos.build", return_value=fake_client)

    out = fetch_new_videos(
        [{"name": "T", "channel_id": "UCt"}],
        {"processed_video_ids": []},
        api_key="fake-key",
    )
    ids = [v["video_id"] for v in out]
    assert "vid_live" not in ids
    assert "vid_vod" in ids
