from unittest.mock import patch, MagicMock
import pipeline.transcribe as tr


def test_captions_path_short_circuits_whisper(tmp_path):
    long_text = "hello world " * 200
    with patch.object(tr, "_try_captions", return_value=long_text) as mc, \
         patch.object(tr, "_run_whisper") as mw:
        out = tr.transcribe("vid1", "https://x", workdir=tmp_path)
    assert out["source"] == "captions"
    assert out["chars"] >= 1000
    mc.assert_called_once()
    mw.assert_not_called()


def test_short_captions_fall_back_to_whisper(tmp_path):
    short = "tiny"
    long_w = "whisper text " * 200
    with patch.object(tr, "_try_captions", return_value=short), \
         patch.object(tr, "_download_audio", return_value=tmp_path / "a.mp3"), \
         patch.object(tr, "_run_whisper", return_value=long_w):
        out = tr.transcribe("vid2", "https://x", workdir=tmp_path)
    assert out["source"] == "whisper"
    assert out["text"] == long_w


def test_both_fail_returns_none(tmp_path):
    with patch.object(tr, "_try_captions", return_value=""), \
         patch.object(tr, "_download_audio", return_value=None), \
         patch.object(tr, "_run_whisper", return_value=""):
        assert tr.transcribe("vid3", "https://x", workdir=tmp_path) is None


def test_vtt_to_text_strips_timestamps_and_dedupes():
    vtt = (
        "WEBVTT\n"
        "\n"
        "1\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Hello world\n"
        "\n"
        "2\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "Hello world\n"
        "\n"
        "3\n"
        "00:00:04.000 --> 00:00:06.000\n"
        "<c.colorE5E5E5>This is a test</c>\n"
    )
    out = tr._vtt_to_text(vtt)
    assert "Hello world" in out
    assert out.count("Hello world") == 1
    assert "This is a test" in out
    assert "-->" not in out
    assert "<c" not in out
