from youtune.downloader import _existing_downloaded_files


def test_existing_downloaded_files_ignores_noise(tmp_path):
    track = tmp_path / "Artist - Song.mp3"
    track.write_bytes(b"fake")

    stdout = f"download progress\n{track}\n"

    assert _existing_downloaded_files(stdout) == [track]


def test_existing_downloaded_files_ignores_missing_paths(tmp_path):
    missing = tmp_path / "missing.mp3"

    assert _existing_downloaded_files(str(missing)) == []
