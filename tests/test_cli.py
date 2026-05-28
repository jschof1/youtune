import argparse

import pytest

from youtune.cli import _config_int, _is_playlist_url, _looks_like_url, _min_bitrate, _quality


def test_quality_accepts_valid_range():
    assert _quality("0") == 0
    assert _quality("9") == 9


@pytest.mark.parametrize("value", ["-1", "10", "best"])
def test_quality_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        _quality(value)


def test_min_bitrate_rejects_negative_values():
    with pytest.raises(argparse.ArgumentTypeError):
        _min_bitrate("-1")


def test_playlist_detection_uses_query_parameter():
    assert _is_playlist_url("https://youtube.com/watch?v=abc&list=PL123")
    assert not _is_playlist_url("https://example.com/list=not-a-query")


def test_url_detection_requires_http_netloc():
    assert _looks_like_url("https://youtube.com/watch?v=abc")
    assert not _looks_like_url("download")
    assert not _looks_like_url("not-a-url")


def test_config_int_falls_back_for_bad_saved_values():
    assert _config_int({"quality": "bad"}, "quality", 0, _quality) == 0
