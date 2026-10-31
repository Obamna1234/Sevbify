"""Jellyfin and Nextcloud (WebDAV): sign-in, song lists, playing with the sign-in kept out of playlists."""
import json

import pytest

from core import servers as S


def test_addresses_need_https_except_on_your_own_network():
    assert S.clean_address("music.example.com") == "https://music.example.com"
    assert S.clean_address("http://192.168.1.20:8096/") == "http://192.168.1.20:8096"
    assert S.clean_address("http://nas.local:8096") == "http://nas.local:8096"
    with pytest.raises(S.ServerError):
        S.clean_address("http://music.example.com")
    with pytest.raises(S.ServerError):
        S.clean_address("https://bob:secret@music.example.com")


def test_jellyfin_keeps_only_a_token_and_lists_songs():
    calls = []

    def opener(method, url, headers, body):
        calls.append((method, url, headers, body))
        if url.endswith("/Users/AuthenticateByName"):
            assert json.loads(body) == {"Username": "ann", "Pw": "pw"}
            return json.dumps({"AccessToken": "TOK", "User": {"Id": "U1"}, "ServerId": "x"}).encode()
        return json.dumps({"TotalRecordCount": 1, "Items": [
            {"Id": "A1", "Name": "Song", "AlbumArtist": "Band", "Album": "LP", "RunTimeTicks": 2_000_000_000,
             "AlbumId": "L1"}]}).encode()
    srv = S.jellyfin_sign_in("https://jf.example.com", "ann", "pw", opener=opener)
    assert "password" not in srv and srv["token"] == "TOK"
    songs = S.songs(srv, opener=opener)
    t = songs[0]
    assert (t.artist, t.title, t.album, t.duration_ms) == ("Band", "Song", "LP", 200_000)
    assert "TOK" not in json.dumps(t.to_dict())                       # nothing secret in a saved song
    assert 'Token="TOK"' in calls[-1][2]["Authorization"]
    url, headers = S.playable(srv, t)
    assert headers == {"Authorization": 'MediaBrowser Token="TOK"'} and "TOK" not in url
    assert S.find([srv], t) is srv
    assert "token" not in S.public(srv)


DAV = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
<d:response><d:href>/remote.php/dav/files/ann/Music/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
{rows}</d:multistatus>"""


def row(href, folder=False):
    rt = "<d:collection/>" if folder else ""
    return f"<d:response><d:href>{href}</d:href><d:propstat><d:prop><d:resourcetype>{rt}</d:resourcetype></d:prop></d:propstat></d:response>"


def test_nextcloud_walks_folders_and_never_leaves_the_server():
    def opener(method, url, headers, body):
        assert method == "PROPFIND" and headers["Authorization"].startswith("Basic ")
        if url.endswith("/Music/"):
            return DAV.format(rows=row("/remote.php/dav/files/ann/Music/Band/", True) +
                              row("https://evil.example.com/x.mp3") + row("/remote.php/dav/files/ann/Music/notes.txt")).encode()
        if url.endswith("/Band/"):
            return DAV.format(rows=row("/remote.php/dav/files/ann/Music/Band/LP/", True)).encode()
        return DAV.format(rows=row("/remote.php/dav/files/ann/Music/Band/LP/03%20-%20Night%20Song.flac")).encode()
    srv = S.webdav_connect("https://cloud.example.com", "ann", "app-pass", "Music", opener=opener)
    songs = S.songs(srv, opener=opener)
    assert [(t.artist, t.album, t.title) for t in songs] == [("Band", "LP", "Night Song")]
    url, headers = S.playable(srv, songs[0])
    assert "app-pass" not in url and headers["Authorization"].startswith("Basic ")
    assert "app-pass" not in json.dumps(songs[0].to_dict())


def test_entity_tricks_are_refused():
    srv = {"id": "x", "type": "webdav", "url": "https://c.example.com/remote.php/dav/files/a", "user": "a", "password": "p"}
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(S.ServerError):
        S.songs(srv, opener=lambda *a: bomb)


def test_window_adds_a_server_as_a_playlist_and_plays_with_the_sign_in(window, qapp, monkeypatch, tmp_path):
    from conftest import wait_until
    from PyQt6.QtWidgets import QInputDialog
    from core.online.models import OnlineTrack
    answers = iter([("https://jf.example.com", True), ("ann", True), ("pw", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(answers))
    srv = {"id": "abcdef123456", "type": "jellyfin", "url": "https://jf.example.com", "user": "ann",
           "user_id": "U1", "token": "TOK", "device_id": "d", "name": "Jellyfin (jf.example.com)"}
    monkeypatch.setattr(S, "jellyfin_sign_in", lambda *a, **k: dict(srv))
    track = OnlineTrack("Song", "Band", source="jellyfin", source_id="A1", page_url="abcdef123456",
                        stream_url="https://jf.example.com/Audio/A1/stream?static=true")
    monkeypatch.setattr(S, "songs", lambda s, opener=None: [track])
    window.add_music_server("jellyfin")
    assert wait_until(qapp, lambda: any(p.name == srv["name"] for p in window.playlists), 10)
    pl = next(p for p in window.playlists if p.name == srv["name"])
    assert pl.origin == "server:abcdef123456"
    import json, os
    saved = json.load(open(os.path.join(window.storage.data_dir, "servers.json")))
    assert saved[0]["token"] == "TOK"
    played = []
    monkeypatch.setattr(window, "_play_media", lambda url, *a: played.append(url) or True)
    window.play_song(pl.songs[0], queue=pl.songs)
    # VLC gets a 127.0.0.1 relay address with no sign-in in it; the relay asks the server with the token
    # in a header.
    assert played and played[0].startswith("http://127.0.0.1:") and "TOK" not in played[0]
    from core import server_relay
    seen = []

    class FakeResp:
        status = 200
        headers = {"Content-Type": "audio/flac", "Content-Length": "4"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1):
            out, self._done = (b"" if getattr(self, "_done", False) else b"fLaC"), True
            return out
    monkeypatch.setattr(S, "_open", lambda req, timeout: seen.append(req) or FakeResp())
    import urllib.request
    body = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(played[0], timeout=5).read()
    assert body == b"fLaC" and seen[0].full_url == track.stream_url
    assert seen[0].get_header("Authorization") == 'MediaBrowser Token="TOK"' or "TOK" in str(seen[0].headers)
    wrong = played[0].rsplit("/", 2)[0] + "/" + "0" * 32 + "/x"
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(wrong, timeout=5)
    window.save_now()
    assert "TOK" not in open(window.storage.path, encoding="utf-8").read()   # never in the save file


def test_server_song_downloads_straight_from_the_server(tmp_path):
    import io
    from core.online.models import OnlineTrack
    srv = {"id": "abcdef123456", "type": "webdav", "url": "https://c.example.com/remote.php/dav/files/a/Music",
           "user": "a", "password": "p"}
    t = OnlineTrack("Night Song", "Band", source="webdav", source_id="Band/LP/03%20-%20Night%20Song.flac",
                    page_url=srv["id"], stream_url="https://c.example.com/remote.php/dav/files/a/Music/Band/LP/03%20-%20Night%20Song.flac")

    class R(io.BytesIO):
        headers = {"Content-Type": "audio/flac"}
        def __enter__(self): return self
        def __exit__(self, *a): self.close()
    seen = []
    path = S.download(srv, t, str(tmp_path), opener=lambda url, h: seen.append(h) or R(b"fLaC" + b"0" * 100))
    assert path.endswith("Band - Night Song.flac") and open(path, "rb").read(4) == b"fLaC"
    assert seen[0]["Authorization"].startswith("Basic ")
    assert not [p for p in tmp_path.rglob("*.part")]


def test_sign_in_never_follows_a_redirect_to_another_host():
    import urllib.request
    h = S._KeepSignInHome()
    req = urllib.request.Request("https://cloud.example.com/a.mp3",
                                 headers={"Authorization": "Basic xyz", "X-Emby-Token": "T", "User-Agent": "x"})
    other = h.redirect_request(req, None, 302, "Found", {}, "https://cdn.evil.example.com/a.mp3")
    assert "Authorization" not in other.headers and "X-emby-token" not in other.headers
    same = h.redirect_request(req, None, 302, "Found", {}, "https://cloud.example.com/b.mp3")
    assert same.headers.get("Authorization") == "Basic xyz"


def test_file_names_are_safe_and_never_overwrite(tmp_path):
    import io
    from core.online.models import OnlineTrack
    assert S.safe_name('Intro: Part 1?') == "Intro- Part 1-"
    assert S.safe_name("CON") == "_CON"
    srv = {"id": "abcdef123456", "type": "jellyfin", "url": "https://jf.example.com", "user": "a", "token": "T"}
    t = OnlineTrack("Song", "Band", source="jellyfin", source_id="1", page_url=srv["id"],
                    stream_url="https://jf.example.com/Audio/1/stream?static=true")

    class R(io.BytesIO):
        headers = {"Content-Type": "audio/mpeg"}
        def __enter__(self): return self
        def __exit__(self, *a): self.close()
    a = S.download(srv, t, str(tmp_path), opener=lambda u, h: R(b"one"))
    b = S.download(srv, t, str(tmp_path), opener=lambda u, h: R(b"two"))
    assert a != b and open(a, "rb").read() == b"one" and b.endswith("Band - Song (2).mp3")
