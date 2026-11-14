"""Spotify Canvas without an account: the request, reading the answer, caching and 'no Canvas' memory."""
import importlib
import os

import pytest


@pytest.fixture
def sc(monkeypatch):
    import core.spotify_canvas as mod
    mod = importlib.reload(mod)            # the real module (conftest stands in for find() elsewhere)
    mod._token.update(value="", until=0)
    return mod


class FakeNet:
    def __init__(self, html):
        self.html, self.pages, self.downloads = html, [], []

    def get_text(self, url, ttl=0):
        self.pages.append(url)
        return self.html

    def download(self, url, dest):
        self.downloads.append(url)
        with open(dest, "wb") as f:
            f.write(b"\x00" * 20_000)
        return dest


TID = "4uLU6hMCjMI75M1A2tKUQC"
HTML = '<script id="__NEXT_DATA__">{"accessToken":"BQAnonymousKey_abcdefghijklmnop"}</script>'


def test_request_is_one_track_and_the_video_link_is_read(sc):
    body = sc._request_body(TID)
    assert body.endswith(b"spotify:track:" + TID.encode()) and body[0] == 0x0a
    seen = []

    def opener(req):
        seen.append(req)
        return b"\n\x99\x01\x12Hhttps://canvaz.scdn.co/upload/artist/abc/video/def.cnvs.mp4\x1a\x04xxxx"
    url = sc.canvas_url(FakeNet(HTML), TID, opener=opener)
    assert url == "https://canvaz.scdn.co/upload/artist/abc/video/def.cnvs.mp4"
    assert seen[0].get_header("Authorization") == "Bearer BQAnonymousKey_abcdefghijklmnop"
    with pytest.raises(sc.NoCanvas):
        sc.canvas_url(FakeNet(HTML), TID, opener=lambda req: b"\n\x00")


def test_find_downloads_once_and_remembers_songs_without_one(sc, tmp_path, monkeypatch):
    net = FakeNet(HTML)
    monkeypatch.setattr(sc, "canvas_url", lambda n, tid, opener=None: "https://canvaz.scdn.co/x.cnvs.mp4")
    page = f"https://open.spotify.com/track/{TID}"
    p = sc.find(net, str(tmp_path), "Cassetter", "Neon Towers", page)
    assert p and os.path.isfile(p) and net.downloads == ["https://canvaz.scdn.co/x.cnvs.mp4"]
    assert sc.find(net, str(tmp_path), "Cassetter", "Neon Towers", page) == p and len(net.downloads) == 1

    def none(*a, **k):
        raise sc.NoCanvas("no Canvas")
    monkeypatch.setattr(sc, "canvas_url", none)
    asked = []
    other = "https://open.spotify.com/track/" + "B" * 22
    assert sc.find(net, str(tmp_path), "Band", "Song", other) is None
    monkeypatch.setattr(sc, "canvas_url", lambda *a, **k: asked.append(1) or "https://canvaz.scdn.co/y.mp4")
    assert sc.find(net, str(tmp_path), "Band", "Song", other) is None and not asked     # remembered for a week


def test_songs_without_a_spotify_link_are_found_by_spotify_search(sc, monkeypatch):
    import json as _json
    monkeypatch.setattr(sc, "_anonymous_token", lambda net, tid: "KEY")
    asked = []

    def opener(req):
        asked.append(req.full_url)
        return _json.dumps({"tracks": {"items": [
            {"id": "X" * 22, "name": "Neon Towers (Remix)", "artists": [{"name": "Cassetter"}]},
            {"id": TID, "name": "Neon Towers", "artists": [{"name": "Cassetter"}, {"name": "Guest"}]}]}}).encode()
    assert sc.search_id(None, "Cassetter", "Neon Towers", opener=opener) == TID      # the remix isn't taken
    assert sc.search_id(None, "A", "B", isrc="USUM71234567", opener=opener) == "X" * 22
    assert "isrc%3AUSUM71234567" in asked[-1]
    assert sc.search_id(None, "Someone Else", "Neon Towers", opener=opener) == ""
