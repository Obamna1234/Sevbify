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
