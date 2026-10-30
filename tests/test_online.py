"""Online layer: switch, cache, providers, matching. No real internet needed."""
import random

import pytest

from online_fixtures import FakeWeb


def make_net(tmp_path, web=None, enabled=True):
    from core.online.net import NetClient
    flag = {"on": enabled}
    net = NetClient(str(tmp_path / "cache"), enabled=lambda: flag["on"], opener=web or FakeWeb())
    net._flag = flag
    return net


# ------------------------------------------------------------------ net + cache
def test_switched_off_never_connects_even_with_cache(tmp_path):
    from core.online.net import OnlineDisabled
    web = FakeWeb()
    net = make_net(tmp_path, web)
    net.get_json("https://api.deezer.com/search", {"q": "x"})
    net._flag["on"] = False
    calls = len(web.calls)
    with pytest.raises(OnlineDisabled):
        net.get_json("https://api.deezer.com/search", {"q": "x"})
    with pytest.raises(OnlineDisabled):
        net.get_image("https://img/a.jpg")
    assert len(web.calls) == calls


def test_offline_uses_last_known_answer_and_reports_offline(tmp_path):
    from core.online.net import OfflineError
    web = FakeWeb()
    net = make_net(tmp_path, web)
    first = net.get_json("https://api.deezer.com/search", {"q": "narc"}, ttl=0)
    web.offline = True
    assert net.get_json("https://api.deezer.com/search", {"q": "narc"}, ttl=0) == first
    assert net.online is False
    with pytest.raises(OfflineError):
        net.get_json("https://api.deezer.com/search", {"q": "never seen"})


def test_fresh_cache_avoids_network(tmp_path):
    web = FakeWeb()
    net = make_net(tmp_path, web)
    net.get_json("https://api.deezer.com/search", {"q": "a"})
    net.get_json("https://api.deezer.com/search", {"q": "a"})
    assert len(web.calls) == 1


# ------------------------------------------------------------------ providers
def test_deezer_search_parses_and_skips_unplayable(tmp_path):
    from core.online.providers import OnlineMusic
    om = OnlineMusic(make_net(tmp_path))
    res = om.search("narc")
    assert [t.title for t in res] == ["NARC", "Gamechanger"]
    t = res[0]
    assert (t.artist, t.album, t.duration_ms, t.source) == ("Mega Drive", "198XAD", 284000, "deezer")
    assert t.preview_url.endswith(".mp3") and t.cover_url and not t.can_download
    assert "open.spotify.com/search/Mega%20Drive%20NARC" in t.links()["Spotify"]
    assert list(t.links())[0] == "Deezer"


def test_artist_card_uses_exact_name_and_lastfm_bio(tmp_path):
    from core.online.providers import OnlineMusic
    om = OnlineMusic(make_net(tmp_path), lastfm_key="k")
    card = om.artist_card("Mega Drive")
    assert card["fans"] == 85860 and card["picture_url"] == "https://img/megadrive.jpg"
    assert card["listeners"] == 123456 and card["tags"] == ["synthwave", "darksynth"]
    assert card["bio"] == "Mega Drive is a darksynth producer from Texas." and card["bio_source"] == "Last.fm"


def test_wikipedia_skips_disambiguation(tmp_path):
    from core.online.providers import Wikipedia
    w = Wikipedia(make_net(tmp_path)).artist_summary("Perturbator")
    assert "synthwave musician" in w["bio"] and w["url"].endswith("/Perturbator")


def test_radio_mixes_sources_removes_seed_duplicates_and_caps_artists(tmp_path):
    from core.online.providers import OnlineMusic
    om = OnlineMusic(make_net(tmp_path), lastfm_key="k")
    songs = om.radio("Mega Drive", "NARC", rng=random.Random(3))
    titles = [t.title for t in songs]
    assert "NARC" not in titles
    assert titles.count("Remoteness") == 1
    assert sum(1 for t in songs if t.artist == "Mega Drive") <= 3
    assert {"Turbo Killer", "Avalanche", "A Dream Drawn from Darkness", "Raining Steel"} <= set(titles)


def test_genre_lookup(tmp_path):
    from core.online.providers import OnlineMusic
    om = OnlineMusic(make_net(tmp_path))
    t = om.search("narc")[0]
    assert om.genre_of(t) == "Electro"


def test_lastfm_needs_key(tmp_path):
    from core.online.providers import OnlineMusic
    om = OnlineMusic(make_net(tmp_path))
    assert not om.lastfm.available
    card = om.artist_card("Mega Drive")
    assert "listeners" not in card and card["fans"] == 85860


# ------------------------------------------------------------------ matching
class FakeSong:
    def __init__(self, title, artist, duration=0, exists=True):
        self.title, self.artist, self.duration, self.exists = title, artist, duration, exists


def test_match_ignores_feat_remaster_case_and_accents():
    from core.online.models import OnlineTrack, find_local_match
    lib = [FakeSong("Frontiere", "Akitsa", 300000), FakeSong("Believe (2011 Remaster)", "CHER", 240000)]
    assert find_local_match(OnlineTrack("Frontière", "Akitsa", duration_ms=301000), lib) is lib[0]
    assert find_local_match(OnlineTrack("Believe (feat. Someone)", "Cher", duration_ms=239000), lib) is lib[1]


def test_match_rejects_different_length_and_missing_files():
    from core.online.models import OnlineTrack, find_local_match
    lib = [FakeSong("NARC", "Mega Drive", 284000, exists=False), FakeSong("Ghost", "Romane", 100000)]
    assert find_local_match(OnlineTrack("NARC", "Mega Drive"), lib) is None
    assert find_local_match(OnlineTrack("Ghost", "Romane", duration_ms=400000), lib) is None


def test_match_untagged_artist_title_filenames():
    from core.online.models import OnlineTrack, find_local_match
    lib = [FakeSong("019 - Molchat Doma - Обречен", "Unknown Artist")]
    assert find_local_match(OnlineTrack("Обречен", "Molchat Doma"), lib) is lib[0]


def test_online_track_round_trip():
    from core.online.models import OnlineTrack
    t = OnlineTrack("A", "B", duration_ms=1000, source="deezer", genre="Rock")
    assert OnlineTrack.from_dict(t.to_dict()) == t


# ------------------------------------------------------------------ in the window
def test_settings_switch_updates_indicator_and_blocks_requests(window):
    called = {}
    window.apply_settings({"online_enabled": False, "lastfm_api_key": "", "jamendo_client_id": ""})
    assert "Offline" in window.sidebar.online_label.text()
    window.online_call(lambda: 1, on_done=lambda r: called.setdefault("done", r),
                       on_error=lambda e: called.setdefault("err", type(e).__name__))
    assert called == {"err": "OnlineDisabled"}
    window.apply_settings({"online_enabled": True, "lastfm_api_key": "abc", "jamendo_client_id": "j"})
    assert window.online.lastfm.available and window.user_data.jamendo_client_id == "j"
    assert "Online" in window.sidebar.online_label.text()


def test_online_call_runs_in_background_and_returns_on_ui_thread(window, qapp):
    import threading
    from conftest import wait_until
    seen = {}
    main = threading.get_ident()
    window.online_call(lambda: threading.get_ident(),
                       on_done=lambda worker: seen.update(worker=worker, cb=threading.get_ident()))
    assert wait_until(qapp, lambda: "cb" in seen)
    assert seen["worker"] != main and seen["cb"] == main


def test_find_album_only_matches_the_same_album_and_artist(tmp_path):
    from core.online.net import NetClient
    from core.online.providers import Deezer
    from online_fixtures import FakeWeb
    albums = {"data": [{"id": 1, "title": "All or Nothing (Remix)", "artist": {"name": "Someone Else"}},
                       {"id": 2, "title": "All or Nothing", "artist": {"name": "Jeremiah Kane"}, "cover_xl": "x"},
                       {"id": 3, "title": "All or Nothing", "artist": {"name": "Other Band"}}]}
    net = NetClient(str(tmp_path / "c"))
    net._opener = FakeWeb({"api.deezer.com/search/album": albums})
    d = Deezer(net)
    assert d.find_album("Jeremiah Kane", "All or Nothing (Deluxe Edition)")["id"] == 2
    assert d.find_album("Nobody", "Something Else") is None
