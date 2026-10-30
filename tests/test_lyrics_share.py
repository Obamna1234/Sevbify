"""Lyrics (local .lrc files, LRCLIB) and share links (song.link with search-link fallback)."""
from online_fixtures import FakeWeb

from core import lyrics, share
from core.online.net import NetClient

LRC = "[ar:Kino]\n[00:01.50]First line\n[00:05.00]Second line\n[00:05.00][01:00.25]Chorus\n"


def net_with(tmp_path, routes):
    net = NetClient(str(tmp_path / "cache"))
    net._opener = FakeWeb(routes)
    return net


def test_parse_lrc_and_current_line():
    lines = lyrics.parse_lrc(LRC)
    assert lines == [(1500, "First line"), (5000, "Second line"), (5000, "Chorus"), (60250, "Chorus")]
    lyr = lyrics.Lyrics(lines, "x", "test")
    assert lyr.line_at(0) == -1 and lyr.line_at(1600) == 0 and lyr.line_at(61000) == 3


def test_own_lrc_file_wins_and_needs_no_internet(tmp_path):
    song = tmp_path / "Kino - Leto.mp3"
    song.write_bytes(b"x")
    (tmp_path / "Kino - Leto.lrc").write_text(LRC, encoding="utf-8")
    got = lyrics.find(None, "Kino", "Leto", song_path=str(song))
    assert got.synced and got.source == "your file" and got.plain.startswith("First line")


def test_lrclib_exact_then_search(tmp_path):
    rec = {"trackName": "Leto", "artistName": "Kino", "duration": 354, "instrumental": False,
           "plainLyrics": "Line one\nLine two", "syncedLyrics": "[00:10.00]Line one\n[00:20.00]Line two"}
    net = net_with(tmp_path, {"lrclib.net/api/get": rec})
    got = lyrics.find(net, "Kino", "Leto", "Chorny albom", 354_000)
    assert got.synced and got.lines[1] == (20000, "Line two") and got.source == "LRCLIB"
    # Not an exact match (404): the search result with the right length is used, a live version isn't
    net2 = net_with(tmp_path / "b", {"lrclib.net/api/get": 404,
                                     "lrclib.net/api/search": [dict(rec, duration=420, plainLyrics="LIVE"),
                                                               dict(rec, syncedLyrics="", plainLyrics="Studio")]})
    got = lyrics.find(net2, "Kino", "Leto", duration_ms=354_000)
    assert got is not None and got.plain == "Studio" and not got.synced


def test_share_links_exact_or_search(tmp_path):
    odesli = {"pageUrl": "https://song.link/d/1", "linksByPlatform": {
        "spotify": {"url": "https://open.spotify.com/track/abc"},
        "youtube": {"url": "https://www.youtube.com/watch?v=xyz"}}}
    net = net_with(tmp_path, {"api.song.link": odesli})
    got = share.links(net, "Kino", "Leto", page_url="https://www.deezer.com/track/1")
    assert got["spotify"].endswith("/track/abc") and got["exact"] == {"spotify": True, "youtube": True}
    assert got["songlink"] == "https://song.link/d/1"
    # The service is gone (410) or there's no Deezer page: search links, plus the video already matched
    net_gone = net_with(tmp_path / "g", {"api.song.link": 410})
    got = share.links(net_gone, "Kino", "Leto", page_url="https://www.deezer.com/track/1",
                      youtube_url="https://www.youtube.com/watch?v=matched")
    assert got["spotify"].startswith("https://open.spotify.com/search/") and not got["exact"]["spotify"]
    assert got["youtube"].endswith("v=matched") and got["exact"]["youtube"]
    assert share.message("Kino", "Leto", "https://x") == "Leto by Kino\nhttps://x"


def test_windows_lyrics_page_share_and_devices(window, qapp, monkeypatch, tmp_path):
    from conftest import wait_until
    from core import lyrics as L
    song = window.songs[0]
    window.play_song(song)
    monkeypatch.setattr(L, "find", lambda net, a, t, al="", d=0, song_path="": L.Lyrics(
        [(0, "First line"), (1000, "Second line")], "First line\nSecond line", "LRCLIB"))
    monkeypatch.setattr(L, "from_file", lambda path: None)
    window.toggle_lyrics()
    assert window.stack.currentWidget() is window.lyrics_page
    assert wait_until(qapp, lambda: len(window.lyrics_page.labels) == 2)
    window.lyrics_page.set_position(1500)
    assert window.lyrics_page.current == 1
    window.toggle_lyrics()                                          # again: back to where you were
    assert window.stack.currentWidget() is not window.lyrics_page
    # Share: offline-style search links copied to the clipboard
    from PyQt6.QtWidgets import QApplication
    window.online_enabled_backup = window.online_enabled
    monkeypatch.setattr(type(window), "online_enabled", property(lambda self: False), raising=False)
    window.share_song(song, "spotify")
    assert QApplication.clipboard().text().startswith("https://open.spotify.com/search/")
    # Connect: the devices list never crashes (VLC's silent test output may list none)
    assert isinstance(window.audio_devices(), list)
    window.set_audio_device("")
    assert window.user_data.audio_device == ""


def test_playlist_download_all_or_choose(window, qapp, monkeypatch):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    a, b, c = (RemoteSong(OnlineTrack(t, "Band", preview_url="https://p/x.mp3")) for t in ("One", "Two", "Three"))
    got = []
    monkeypatch.setattr(window, "download_songs", lambda songs: got.append([s.title for s in songs]) or len(songs))
    window._auto_answer_dialogs = True                       # "Download all"
    window.download_with_choice([window.songs[0], a, b, c, a], "Mix")
    assert got[-1] == ["One", "Two", "Three"]                # own songs and duplicates skipped
    window._auto_answer_dialogs = [b]                        # ticked only "Two"
    window.download_with_choice([a, b, c], "Mix")
    assert got[-1] == ["Two"]
    window._auto_answer_dialogs = False                      # cancelled
    assert window.download_with_choice([a], "Mix") == 0
    window._auto_answer_dialogs = None
