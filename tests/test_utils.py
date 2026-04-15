"""Tests for filename utilities."""

from youtune.utils import sanitize_filename, format_filename


def test_sanitize_illegal():
    assert ":" not in sanitize_filename('test: file?"<>|')
    assert "/" not in sanitize_filename("test/file")


def test_format():
    assert format_filename("Rick Astley", "Never Gonna Give You Up") == "Rick Astley - Never Gonna Give You Up.mp3"


def test_format_no_artist():
    assert format_filename("", "Some Song") == "Some Song.mp3"


def test_sanitize_truncates():
    assert len(sanitize_filename("a" * 300)) <= 200
