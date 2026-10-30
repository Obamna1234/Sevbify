"""Imported files are checked song by song: found ones get their details, typos get a "Did you mean"."""
from core import import_check as C
from core.online.models import OnlineTrack
from core.online.net import NetClient
from core.online.providers import OnlineMusic
from online_fixtures import FakeWeb, deezer_track


def music_with(tmp_path, routes):
    net = NetClient(str(tmp_path / "c"), opener=FakeWeb(routes))
    return OnlineMusic(net), net


def test_found_songs_are_ok_and_typos_get_the_closest_song(tmp_path):
    routes = {
        "api.deezer.com/search?q=artist%3A%22Drake%22+track%3A%22Hotline+Bling%22": {"data": [
            deezer_track(1, "Hotline Bling", "Drake", 5)]},
        "api.deezer.com/search?q=Drake+Hotlin+Blng": {"data": [deezer_track(1, "Hotline Bling", "Drake", 5)]},
        "api.deezer.com/search?q=Drake+-+Hotlin+Blng": {"data": [deezer_track(1, "Hotline Bling", "Drake", 5)]},
        "api.deezer.com/search": {"data": []},
        "duckduckgo.com/ac/": ["x", []],
    }
    music, net = music_with(tmp_path, routes)
    good = C.check_song(music, net, OnlineTrack("Hotline Bling", "Drake"))
    assert good["status"] == C.OK and good["track"].cover_url
    typo = C.check_song(music, net, OnlineTrack("Hotlin Blng", "Drake"))
    assert typo["status"] == C.SUGGEST and C.as_text(typo["suggestion"]) == "Drake - Hotline Bling"
    nothing = C.check_song(music, net, OnlineTrack("Qwzx", "Nobody Atall"))
    assert nothing["status"] == C.MISSING


def test_progress_and_correction(tmp_path):
    music, net = music_with(tmp_path, {"api.deezer.com/search": {"data": []}, "duckduckgo.com/ac/": ["x", []]})
    seen = []
    res = C.check_tracks(music, net, [OnlineTrack("A", "B"), OnlineTrack("C", "D")], progress=lambda a, b: seen.append((a, b)))
    assert [r["status"] for r in res] == [C.MISSING, C.MISSING] and seen == [(1, 2), (2, 2)]
    t = C.corrected(OnlineTrack("Hotlin", "Drake"), "Drake - Hotline Bling")
    assert (t.artist, t.title) == ("Drake", "Hotline Bling")


def test_window_names_the_import_checks_it_and_asks_about_typos(window, qapp, tmp_path):
    from conftest import wait_until
    window.net._opener = FakeWeb({
        "api.deezer.com/search?q=artist%3A%22Drake%22+track%3A%22Hotline+Bling%22": {"data": [
            deezer_track(1, "Hotline Bling", "Drake", 5)]},
        "api.deezer.com/search?q=Drake+-+Hotlin+Blng": {"data": [deezer_track(1, "Hotline Bling", "Drake", 5)]},
        "api.deezer.com/search": {"data": []},
        "duckduckgo.com/ac/": ["x", []]})
    f = tmp_path / "my list.txt"
    f.write_text("Drake - Hotline Bling\nDrake - Hotlin Blng\n", encoding="utf-8")
    pl = window.import_from_file(str(f), name="Road trip")
    assert pl.name == "Road trip" and len(pl.songs) == 2
    assert wait_until(qapp, lambda: window.reviewed_imports, 10)
    name, problems = window.reviewed_imports[0]
    assert name == "Road trip" and [(w, s) for _song, w, s in problems] == [("Drake - Hotlin Blng", "Drake - Hotline Bling")]
    assert pl.songs[0].track.cover_url                           # the song that was found got its details


def test_spotify_beyond_100_uses_the_embed_key_or_offers_chosic(tmp_path):
    from core import importers
    import json as _j
    page = {"items": [{"track": {"name": "Song 101", "id": "abc", "duration_ms": 1000,
                                 "artists": [{"name": "X"}], "album": {"name": "A", "images": [{"url": "https://i/1"}]}}}],
            "next": None}
    more = importers.fetch_spotify_rest(None, "37i9dQZF1DX5Ejj0EkURtP", "tok", 100,
                                        opener=lambda url: _j.dumps(page).encode())
    assert [(t.artist, t.title) for t in more] == [("X", "Song 101")]
    import pytest
    with pytest.raises(Exception):
        importers.fetch_spotify_rest(None, "37i9dQZF1DX5Ejj0EkURtP", "", 100)


def test_window_fills_a_playlist_from_the_chosic_download(window, qapp, tmp_path):
    from core.online.remote_song import RemoteSong
    pl = window.create_playlist("Big", [RemoteSong(OnlineTrack(f"S{i}", "A")) for i in range(3)])
    f = tmp_path / "Big.csv"
    f.write_text("Song,Artist\n" + "".join(f"S{i},A\n" for i in range(5)), encoding="utf-8")
    window._check_imported = lambda p: None
    window._fill_from_file(pl, str(f))
    assert len(pl.songs) == 5 and pl.name == "Big"


def test_m3u_network_paths_are_never_opened(tmp_path, monkeypatch):
    import os
    from core import importers
    looked = []
    real = os.path.exists
    monkeypatch.setattr(importers.os.path, "exists", lambda p: looked.append(p) or real(p))
    m = tmp_path / "x.m3u"
    m.write_text("#EXTM3U\n#EXTINF:1,Band - One\n\\\\attacker\\share\\a.mp3\n#EXTINF:1,Band - Two\n//host/b.mp3\n",
                 encoding="utf-8")
    res = importers.read_playlist_file(str(m))
    assert [v.title for k, v in res["items"]] == ["One", "Two"]
    assert not any("attacker" in p or "host" in p for p in looked)


def test_only_song_lists_are_picked_up_from_downloads(window, tmp_path):
    songs = tmp_path / "playlist.csv"
    songs.write_text("Song,Artist\nA,B\n", encoding="utf-8")
    bank = tmp_path / "statement.csv"
    bank.write_text("Date,Amount,Payee\n2026-10-01,12.50,Shop\n", encoding="utf-8")
    assert window._looks_like_song_list(str(songs))
    assert not window._looks_like_song_list(str(bank))
