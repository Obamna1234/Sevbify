"""Full-length streaming of songs you don't have yet (core/streamer.py and the player).

No internet: the engine's Bandcamp/YouTube searches and yt-dlp's link lookup are replaced by fakes, and the
"stream" is a local WAV file handed to VLC. The real Bandcamp/YouTube lookup is not tested here.
"""
import pytest

from conftest import make_wav, wait_until
from core import downloader, streamer


@pytest.fixture(autouse=True)
def fresh_cache():
    streamer.clear_cache()
    yield
    streamer.clear_cache()


@pytest.fixture
def fake_engine(monkeypatch):
    e = downloader.engine()
    calls = {"bc": [], "yt": []}
    state = {"bc": {"found": False}, "yt": []}

    def bc(line):
        calls["bc"].append(line)
        return state["bc"]

    def yt(line, n=8):
        calls["yt"].append(line)
        return state["yt"]

    monkeypatch.setattr(e, "search_bandcamp", bc)
    monkeypatch.setattr(e, "search_youtube_candidates", yt)
    return state, calls


def test_bandcamp_is_tried_first(fake_engine):
    state, calls = fake_engine
    state["bc"] = {"found": True, "url": "https://artist.bandcamp.com/track/song"}
    res = streamer.find_full_song("Artist", "Song", 200000, extract=lambda page: ("https://cdn/bc.mp3", {}, 200))
    assert res["source"] == "Bandcamp" and res["url"] == "https://cdn/bc.mp3" and res["duration_ms"] == 200000
    assert calls["bc"] == ["Artist - Song"]


def test_youtube_match_uses_the_songs_real_length(fake_engine):
    state, calls = fake_engine
    state["yt"] = [
        {"id": "live1", "title": "Artist - Song (Live)", "duration": 420, "channel": "Fan"},
        {"id": "good1", "title": "Artist - Song (Official Audio)", "duration": 201, "channel": "Artist"},
        {"id": "other", "title": "Completely different thing", "duration": 200, "channel": "X"},
    ]
    seen = []
    res = streamer.find_full_song("Artist", "Song", 200000,
                                  extract=lambda page: seen.append(page) or ("https://cdn/yt.webm", {"User-Agent": "UA"}, 201))
    assert res["source"] == "YouTube" and seen == ["https://www.youtube.com/watch?v=good1"]
    assert res["headers"] == {"User-Agent": "UA"}


def test_falls_back_to_youtube_when_bandcamp_cant_stream(fake_engine):
    state, _ = fake_engine
    state["bc"] = {"found": True, "url": "https://artist.bandcamp.com/track/song"}
    state["yt"] = [{"id": "v", "title": "Artist - Song", "duration": 200}]

    def extract(page):
        if "bandcamp" in page:
            raise RuntimeError("purchase only")
        return "https://cdn/yt.webm", {}, 200

    assert streamer.find_full_song("Artist", "Song", 200000, extract=extract)["source"] == "YouTube"


def test_source_setting_and_nothing_found(fake_engine):
    state, calls = fake_engine
    with pytest.raises(streamer.NoFullSong):
        streamer.find_full_song("Artist", "Song", source=downloader.SOURCE_BANDCAMP, extract=lambda p: ("x", {}, 1))
    assert calls["yt"] == []                                     # Bandcamp only: YouTube never searched
    with pytest.raises(streamer.NoFullSong):
        streamer.find_full_song("Artist", "Song", source=downloader.SOURCE_YOUTUBE, extract=lambda p: ("x", {}, 1))
    assert len(calls["bc"]) == 1                                 # YouTube only: Bandcamp not searched again


def test_found_streams_are_remembered_for_a_while(fake_engine):
    state, calls = fake_engine
    state["bc"] = {"found": True, "url": "https://a.bandcamp.com/track/s"}
    for _ in range(3):
        streamer.find_full_song("Artist", "Song", extract=lambda p: ("https://cdn/a.mp3", {}, 100))
    assert len(calls["bc"]) == 1


def test_the_same_song_asked_for_twice_at_once_is_looked_up_once(fake_engine):
    import threading, time
    state, calls = fake_engine
    state["yt"] = [{"id": "v", "title": "Artist - Song", "duration": 200}]
    runs = []

    def slow(page):
        runs.append(page); time.sleep(0.3)
        return "https://cdn/yt.webm", {}, 200
    out = []
    ts = [threading.Thread(target=lambda: out.append(streamer.find_full_song("Artist", "Song", 200000, extract=slow)))
          for _ in range(3)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(runs) == 1 and len(out) == 3 and {o["url"] for o in out} == {"https://cdn/yt.webm"}
    assert len(calls["yt"]) == 1


def test_a_song_found_before_skips_the_searches_even_after_its_link_expired(fake_engine, monkeypatch):
    state, calls = fake_engine
    state["yt"] = [{"id": "v", "title": "Artist - Song", "duration": 200}]
    streamer.find_full_song("Artist", "Song", 200000, extract=lambda p: ("https://cdn/1", {}, 200))
    streamer._cache.clear()                                        # the 30-minute link memory ran out
    res = streamer.find_full_song("Artist", "Song", 200000, extract=lambda p: ("https://cdn/2", {}, 200))
    assert res["url"] == "https://cdn/2" and len(calls["yt"]) == 1 and len(calls["bc"]) == 1
    assert res["timings"]["searches"] == "remembered"


def test_timings_say_where_the_time_went(fake_engine):
    state, _ = fake_engine
    state["yt"] = [{"id": "v", "title": "Artist - Song", "duration": 200}]
    t = streamer.find_full_song("Artist", "Song", 200000, extract=lambda p: ("u", {}, 200))["timings"]
    assert {"bandcamp", "youtube_search", "extract", "total"} <= set(t)


def test_phone_tries_one_fast_client_first_then_the_full_list(monkeypatch):
    class Eng:
        SONG_EXTRACTORS = ["youtube"]
        class _QuietLogger: pass
        def yt_extractor_args(self):
            return {"youtube": {"player_client": ["default", "tv", "mweb", "ios", "android_vr"]}}
        calls = []

        class yt_dlp:
            class YoutubeDL:
                def __init__(self, opts): self.clients = opts["extractor_args"]["youtube"]["player_client"]
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def extract_info(self, page, download=False):
                    Eng.calls.append(self.clients)
                    if self.clients != ["tv"]:            # only the tv client works in this test
                        raise RuntimeError("no audio")
                    return {"url": "https://cdn/a", "http_headers": {}, "duration": 99}
    e = Eng()
    assert streamer._attempts(e)[:3] == [{"youtube": {"player_client": [c]}} for c in ("android_vr", "tv", "mweb")]
    assert streamer._extract(e, "https://www.youtube.com/watch?v=x")[0] == "https://cdn/a"
    assert Eng.calls == [["android_vr"], ["tv"]]
    Eng.calls.clear()
    streamer._extract(e, "https://www.youtube.com/watch?v=y")      # remembers: tv goes first now
    assert Eng.calls == [["tv"]]
    streamer.clear_cache()


def test_found_pages_survive_a_restart_and_only_trusted_pages_are_loaded(fake_engine, tmp_path):
    import json
    state, calls = fake_engine
    store = tmp_path / "song_pages.json"
    streamer.set_page_store(str(store))
    state["yt"] = [{"id": "v", "title": "Artist - Song", "duration": 200}]
    streamer.find_full_song("Artist", "Song", 200000, extract=lambda p: ("https://cdn/1", {}, 200))
    rows = json.loads(store.read_text())
    assert rows and rows[0][2] == "YouTube" and rows[0][3].startswith("https://www.youtube.com/watch?v=")
    # "restart": memory is empty, the file is read again; the searches are skipped
    streamer._pages.clear(); streamer._cache.clear()
    streamer.set_page_store(str(store))
    res = streamer.find_full_song("Artist", "Song", 200000, extract=lambda p: ("https://cdn/2", {}, 200))
    assert res["url"] == "https://cdn/2" and len(calls["yt"]) == 1
    # a tampered file: pages outside YouTube/Bandcamp, plain http, wrong names and wrong shapes are ignored
    store.write_text(json.dumps([["a - b", downloader.SOURCE_BOTH, "YouTube", "https://evil.example/watch?v=x"],
                                 ["c - d", downloader.SOURCE_BOTH, "YouTube", "http://www.youtube.com/watch?v=x"],
                                 ["e - f", downloader.SOURCE_BOTH, "Other", "https://www.youtube.com/watch?v=x"],
                                 ["g - h", downloader.SOURCE_BOTH, "YouTube", "https://www.youtube.com/watch?v=ok"],
                                 ["short"], 5]))
    streamer._pages.clear()
    streamer.set_page_store(str(store))
    assert list(streamer._pages) == [("g - h", downloader.SOURCE_BOTH)]
    streamer.clear_cache()
    assert not store.exists()
    streamer._store_path = ""


# --- in the player (needs VLC, like the other window tests) --------------------------------------------------------

def remote(title, artist, preview=""):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    return RemoteSong(OnlineTrack(title, artist, duration_ms=3000, source="deezer", preview_url=preview))


def full_streaming(window):
    from core.online.remote_song import RemoteSong
    window.user_data.stream_full = True
    RemoteSong.stream_full = True
    window.user_data.download_notice_accepted = True
    window.__dict__.pop("_stream_full_song", None)      # the real lookup (conftest stands in for it elsewhere)


def test_song_you_dont_have_streams_in_full_and_stays_not_downloaded(window, qapp, tmp_path, monkeypatch):
    stream = tmp_path / "stream.wav"
    make_wav(stream, 3.0)
    full_streaming(window)
    asked = []
    monkeypatch.setattr(streamer, "find_full_song",
                        lambda artist, title, dur, source: asked.append((artist, title, dur, source))
                        or {"url": str(stream), "headers": {}, "source": "YouTube", "duration_ms": 3000})
    song = remote("Night City", "Vogel", preview="https://cdn/preview.mp3")
    pl = window.create_playlist("Mix", [song])
    window.play_song(song, queue=pl.songs, source="Mix")
    assert wait_until(qapp, lambda: "Full song · YouTube · not downloaded" in window.artist_info.text()
                      or "Full song · YouTube · not downloaded" in window.song_info.text())
    assert wait_until(qapp, lambda: window._reached_playing)
    assert asked == [("Vogel", "Night City", 3000, downloader.SOURCE_BOTH)]
    assert getattr(pl.songs[0], "is_remote", False)              # still a ⬇ slot until downloaded
    assert song in window.songs_to_download()
    assert not song.is_preview


def test_song_is_skipped_not_swapped_for_its_preview_when_no_full_song_is_found(window, qapp, tmp_path, monkeypatch):
    preview = tmp_path / "preview.wav"
    make_wav(preview, 3.0)
    full_streaming(window)

    def nothing(*a):
        raise streamer.NoFullSong("not found")

    monkeypatch.setattr(streamer, "find_full_song", nothing)
    played = []
    real = window._play_media
    monkeypatch.setattr(window, "_play_media", lambda url, *a: played.append(url) or real(url, *a))
    song = remote("Rare B-side", "Nobody", preview=str(preview))
    window.play_song(song, queue=[song], source="Search")
    assert wait_until(qapp, lambda: "full song not found" in window.status_label.text())
    assert str(preview) not in played


def test_skipping_while_searching_ignores_the_late_result(window, qapp, tmp_path, monkeypatch):
    import threading
    gate = threading.Event()
    stream = tmp_path / "late.wav"
    make_wav(stream, 3.0)
    full_streaming(window)

    def slow(*a):
        gate.wait(5)
        return {"url": str(stream), "headers": {}, "source": "YouTube", "duration_ms": 3000}

    monkeypatch.setattr(streamer, "find_full_song", slow)
    song = remote("Slow", "Search")
    window.play_song(song, queue=[song, window.songs[0]], source="Search")
    assert wait_until(qapp, lambda: "Finding the full song" in window.artist_info.text()
                      or "Finding the full song" in window.song_info.text())
    window.play_song(window.songs[0])                             # user picks something else meanwhile
    gate.set()
    assert wait_until(qapp, lambda: window._reached_playing and window.current_song is window.songs[0])
    qapp.processEvents()
    assert window.current_song is window.songs[0]


def test_preview_only_plays_from_the_song_menu_in_its_own_window(window, qapp, tmp_path, monkeypatch):
    preview = tmp_path / "p.wav"
    make_wav(preview, 3.0)
    song = remote("Short", "Preview", preview=str(preview))
    menu = window.build_song_menu(song)
    labels = [a.text() for a in menu.actions()]
    assert any("Preview (30 s)" in t for t in labels)
    window.preview_song(song)
    dlg = window._preview_window
    assert dlg is not None and dlg.isVisible()
    assert wait_until(qapp, lambda: dlg.player.get_time() > 0 or dlg.player.is_playing())
    assert window.current_song is not song                    # the main player never gets the clip
    dlg.slider.setValue(1500)
    dlg._seek()
    dlg.close()

