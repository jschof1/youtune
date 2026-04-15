"""Tests for the YouTube title parser."""

from youtune.parser import parse_title, clean_title


def test_basic_dash():
    p = parse_title("Rick Astley - Never Gonna Give You Up")
    assert p.artist == "Rick Astley"
    assert p.title == "Never Gonna Give You Up"
    assert p.confidence >= 0.7


def test_official_video_stripped():
    p = parse_title("Rick Astley - Never Gonna Give You Up (Official Music Video)")
    assert p.artist == "Rick Astley"
    assert "Official" not in p.title
    assert "Video" not in p.title


def test_hd_and_brackets():
    p = parse_title("Daft Punk - Get Lucky [HD] (Official Audio)")
    assert p.artist == "Daft Punk"
    assert "HD" not in p.title
    assert "Official" not in p.title


def test_pipe_separator():
    p = parse_title("The Beatles | Let It Be")
    assert p.artist == "The Beatles"
    assert p.title == "Let It Be"


def test_quotes_by():
    p = parse_title('"Bohemian Rhapsody" by Queen')
    assert p.artist == "Queen"
    assert p.title == "Bohemian Rhapsody"


def test_em_dash():
    p = parse_title("Daft Punk — Around the World")
    assert p.artist == "Daft Punk"
    assert p.title == "Around the World"


def test_fallback_no_artist():
    p = parse_title("some weird video title with no artist info")
    assert p.title != ""
    assert p.confidence < 0.5


def test_clean_title():
    assert "Official" not in clean_title("(Official Music Video)")
    assert "HD" not in clean_title("[HD Remaster]")


def test_unicode_brackets():
    p = parse_title("BTS «Dynamite»")
    assert "Dynamite" in p.title


def test_feat_stripped():
    p = parse_title("Drake - Nice For What (feat. Andre 3000)")
    assert "feat" not in p.title.lower() or "Andre" not in p.title
