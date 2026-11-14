"""Bandcamp read directly: the track page's player data gives the full song's MP3 link."""
import html
import json

import pytest

from core import bandcamp

PAGE = "https://perturbator.bandcamp.com/track/future-club"


def page_with(data):
    return f'<html><script data-tralbum="{html.escape(json.dumps(data))}" data-x="1"></script></html>'


def test_reads_the_mp3_link_title_and_length():
    data = {"artist": "Perturbator", "album_title": "Dangerous Days", "art_id": 123,
            "trackinfo": [{"title": "Future Club", "duration": 288.5,
                           "file": {"mp3-128": "https://t4.bcbits.com/stream/abc/mp3-128/1?p=0&ts=1&t=x"}}]}
    url, headers, secs = bandcamp.stream(PAGE, opener=lambda u: page_with(data))
    assert url.startswith("https://t4.bcbits.com/stream/") and "&ts=1" in url and secs == 288.5
    info = bandcamp.track_info(PAGE, opener=lambda u: page_with(data))
    assert info["artist"] == "Perturbator" and info["cover"].endswith("a123_10.jpg")


def test_tracks_bandcamp_wont_stream_and_odd_pages_are_refused():
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream(PAGE, opener=lambda u: page_with({"trackinfo": [{"title": "x", "file": None}]}))
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream(PAGE, opener=lambda u: "<html>changed</html>")
    with pytest.raises(bandcamp.NotPlayable):
        bandcamp.stream("https://evil.example.com/track/x", opener=lambda u: "")
    assert not bandcamp.is_track_page("https://bandcamp.com.evil.com/track/x")


def test_streaming_uses_bandcamp_directly(monkeypatch):
    from core import streamer, downloader
    monkeypatch.setattr(bandcamp, "stream", lambda page, opener=None: ("https://t4.bcbits.com/s", {"User-Agent": "x"}, 200))
    url, headers, secs = streamer._extract(downloader.engine(), PAGE)
    assert url == "https://t4.bcbits.com/s" and secs == 200
