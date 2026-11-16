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
    monkeypatch.setattr(streamer, "url_works", lambda url, headers=None, timeout=8: True)
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
    window._preview_window = None
    window.preview_song(song)                       # asks for a fresh link first (offline here: the saved one)
    assert wait_until(qapp, lambda: window._preview_window is not None)
    dlg = window._preview_window
    assert dlg.isVisible()
    assert wait_until(qapp, lambda: dlg.player.get_time() > 0 or dlg.player.is_playing())
    assert window.current_song is not song                    # the main player never gets the clip
    dlg.slider.setValue(1500)
    dlg._seek()
    dlg.close()


def test_a_link_the_server_refuses_sends_the_lookup_to_the_next_client(monkeypatch):
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
                    return {"url": "https://cdn/" + "-".join(self.clients), "http_headers": {}, "duration": 99}
    monkeypatch.setattr(streamer, "url_works", lambda url, headers=None, timeout=8: "android_vr" not in url)
    streamer.clear_cache()
    assert streamer._extract(Eng(), "https://www.youtube.com/watch?v=x")[0] == "https://cdn/tv"
    assert Eng.calls == [["android_vr"], ["tv"]]
    # the player was refused that link anyway: the next client is tried first next time
    monkeypatch.setattr(downloader, "engine", lambda: Eng())
    assert streamer.link_failed("https://cdn/tv")
    Eng.calls.clear()
    streamer._extract(Eng(), "https://www.youtube.com/watch?v=y")
    assert Eng.calls[0] == ["mweb"]
    streamer.clear_cache()


def test_url_works_only_says_no_when_the_server_clearly_refuses(monkeypatch):
    import urllib.error
    import urllib.request

    def refuse(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    def hiccup(req, timeout=0):
        raise OSError("no network")
    monkeypatch.setattr(downloader, "_engine", None)          # without yt-dlp: a plain request
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert streamer.url_works("https://cdn/a", {}) is False
    monkeypatch.setattr(urllib.request, "urlopen", hiccup)
    assert streamer.url_works("https://cdn/a", {}) is True            # can't tell: let the player try
    assert streamer.url_works("http://cdn/a", {}) is True             # only https links are checked


def test_not_found_says_why_the_searches_failed(monkeypatch):
    """"Not found" keeps the reason a search failed (e.g. YouTube's bot check), for Playback status and the
    end-to-end test."""
    from core import streamer, downloader
    e = downloader.engine()
    monkeypatch.setattr(e, "search_bandcamp", lambda line: (_ for _ in ()).throw(OSError("Bandcamp is down")))
    monkeypatch.setattr(streamer, "_pick_youtube", lambda *a: (_ for _ in ()).throw(
        RuntimeError("Sign in to confirm you're not a bot")))
    streamer.clear_cache()
    import pytest
    with pytest.raises(streamer.NoFullSong) as err:
        streamer.find_full_song("Nobody", "Nothing Song Xyz")
    assert "not a bot" in str(err.value) and "Bandcamp is down" in str(err.value)


def test_journey_report_table(tmp_path):
    import json
    from ui.journey import write_markdown
    (tmp_path / "journey.json").write_text(json.dumps({"info": {"system": "Test 1"}, "steps": [
        {"step": "Stream a song (YouTube)", "status": "blocked", "detail": "not a bot", "seconds": 3},
        {"step": "Download a song", "status": "fail", "detail": "no file | here", "seconds": 9}],
        "dialogs": ["Update available"]}))
    md = write_markdown(str(tmp_path), "T")
    assert "🚫 blocked here" in md and "❌ FAIL" in md and "no file \\| here" in md
    assert "Restart check | ❌ FAIL" in md and "Update available" in md


def test_a_link_vlc_cant_open_is_tried_again_then_saved_first(window, qapp, tmp_path, monkeypatch):
    """Jet Pack on Windows: the link was found but VLC couldn't open it. Sevbify asks for a fresh link once, then
    saves the audio to a temporary file and plays that, before giving up."""
    good = tmp_path / "saved.wav"
    make_wav(good, 3.0)
    full_streaming(window)
    links = iter([str(tmp_path / "broken1.mp3"), str(tmp_path / "broken2.mp3")])
    for name in ("broken1.mp3", "broken2.mp3"):
        (tmp_path / name).write_bytes(b"not audio at all" * 100)
    failed_links = []
    monkeypatch.setattr(streamer, "find_full_song", lambda *a: {"url": next(links), "headers": {}, "source": "YouTube",
                                                                "page": "https://www.youtube.com/watch?v=x"})
    monkeypatch.setattr(streamer, "link_failed", failed_links.append)
    monkeypatch.setattr(streamer, "download_original_audio", lambda page, out, *a, **k: str(good))
    song = remote("Jet Pack", "Cassetter")
    window.play_song(song, queue=[song], source="Test")
    assert wait_until(qapp, lambda: window._reached_playing, 20)
    assert failed_links == [str(tmp_path / "broken1.mp3")]
    assert window.player.get_media().get_mrl().endswith("saved.wav")


def test_soundcloud_is_the_third_place_to_look_and_previews_are_refused(monkeypatch):
    """Songs on neither Bandcamp nor YouTube (e.g. an album taken down everywhere else) can be on SoundCloud.
    It's only searched when the others have nothing, and only a close match by the same artist, of about the
    right length, counts."""
    import re
    from core import streamer

    class Eng:
        @staticmethod
        def _split_query(line):
            a, _, t = line.partition(" - ")
            return a, t
        @staticmethod
        def _words(text):
            return re.findall(r"\w+", (text or "").casefold())
    monkeypatch.setattr(streamer, "_sc_search", lambda e, q, n: {"entries": [
        {"url": "https://soundcloud.com/someone/sets/the-album", "title": "Abyssic Hate - Suicidal Emotions", "duration": 300},
        {"url": "https://soundcloud.com/dj/mix", "title": "Suicidal Emotions (2 hour mix)", "duration": 7200},
        {"url": "https://evil.example/abyssic/suicidal", "title": "Suicidal Emotions", "duration": 300},
        {"url": "https://soundcloud.com/someoneelse/suicidal-emotions", "title": "Suicidal Emotions",
         "uploader": "Other Band", "duration": 300},
        {"url": "https://api.soundcloud.com/tracks/1", "webpage_url": "https://soundcloud.com/abyssichate/suicidal-emotions",
         "title": "Suicidal Emotions", "uploader": "Abyssic Hate", "duration": 302}]})
    assert streamer._pick_soundcloud(Eng, "Abyssic Hate - Suicidal Emotions", 300) == \
        "https://soundcloud.com/abyssichate/suicidal-emotions"
    assert streamer._pick_soundcloud(Eng, "Abyssic Hate - Something Else", 300) is None
    assert streamer.is_soundcloud_track("https://soundcloud.com/a/b") and not streamer.is_soundcloud_track(
        "https://soundcloud.com/a/sets/b") and not streamer.is_soundcloud_track("http://soundcloud.com/a/b")
    assert streamer._page_ok("SoundCloud", "https://soundcloud.com/a/b")
    assert not streamer._page_ok("SoundCloud", "https://soundcloud.com.evil.example/a/b")


def test_url_works_asks_the_way_downloads_do(monkeypatch):
    """With yt-dlp loaded the check goes through yt-dlp's own networking (what YouTube accepts)."""
    e = downloader.engine()
    seen = []

    class Refused(Exception):
        status = 403

    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def urlopen(self, req):
            seen.append(req.headers.get("Range"))
            if "bad" in req.url:
                raise Refused()
            import io
            r = io.BytesIO(b"ok")
            r.status = 206
            return r
    monkeypatch.setattr(e.yt_dlp, "YoutubeDL", FakeYDL)
    assert streamer.url_works("https://rr1.googlevideo.com/good", {}) is True
    assert streamer.url_works("https://rr1.googlevideo.com/bad", {}) is False
    assert seen == ["bytes=0-1", "bytes=0-1"]


def test_soundcloud_albums_are_the_artists_own_each_once(monkeypatch):
    from core import streamer
    monkeypatch.setattr(streamer, "_sc_api", lambda path, query, ident="x": {"collection": [
        {"title": "Suicidal Emotions", "permalink_url": "https://soundcloud.com/rob/sets/suicidal-emotions",
         "artwork_url": "https://i1.sndcdn.com/artworks-abc-large.jpg", "publisher_metadata": {"artist": "Abyssic Hate"},
         "user": {"username": "Rob_rob_"}, "release_date": "1994-01-01", "track_count": 7, "set_type": "album"},
        {"title": "Abyssic Hate - Suicidal Emotions", "permalink_url": "https://soundcloud.com/x/sets/se",
         "user": {"username": "x"}},                                     # the same album again: listed once
        {"title": "Abyssic Hate - Cleansing of an Ancient Mind", "permalink_url": "https://soundcloud.com/y/sets/c",
         "user": {"username": "y"}, "set_type": "ep"},
        {"title": "Abyssic - Brought Forth", "permalink_url": "https://soundcloud.com/z/sets/b",
         "user": {"username": "Abyssic"}},                               # a different band
        {"title": "Some playlist", "permalink_url": "https://soundcloud.com/abyssichate/likes",
         "user": {"username": "Abyssic Hate"}}]})                        # not an album link
    albums = streamer.soundcloud_albums("Abyssic Hate")
    assert [a["title"] for a in albums] == ["Suicidal Emotions", "Cleansing of an Ancient Mind"]
    assert albums[0]["cover"] == "https://i1.sndcdn.com/artworks-abc-t500x500.jpg" and albums[0]["year"] == "1994"
    assert albums[1]["kind"] == "EP" and albums[1]["cover"] == ""


def test_soundcloud_album_songs_come_in_order_with_their_pages(monkeypatch):
    from core import streamer

    def api(path, query, ident="x"):
        if path == "resolve":
            return {"tracks": [{"id": 1, "title": "Abyssic Hate - Bloodletting", "permalink_url": "https://soundcloud.com/rob/bloodletting",
                                "duration": 280000},
                               {"id": 2}, {"id": 3}]}                       # later songs: ids only
        assert path == "tracks" and query["ids"] == "2,3"
        return [{"id": 3, "title": "Attack", "permalink_url": "https://soundcloud.com/rob/attack", "duration": 1000},
                {"id": 2, "title": "Mirror", "permalink_url": "https://soundcloud.com/rob/mirror"}]
    monkeypatch.setattr(streamer, "_sc_api", api)
    album = {"title": "Suicidal Emotions", "url": "https://soundcloud.com/rob/sets/se", "artist": "Abyssic Hate",
             "cover": "https://i1.sndcdn.com/a-t500x500.jpg"}
    tracks = streamer.soundcloud_album_tracks(album)
    assert [t.title for t in tracks] == ["Bloodletting", "Mirror", "Attack"]
    assert all(t.artist == "Abyssic Hate" and t.source == "soundcloud" for t in tracks)
    assert tracks[0].cover_url == album["cover"] and tracks[0].duration_ms == 280000
    assert streamer.soundcloud_album_tracks({"url": "https://soundcloud.com/rob/likes", "artist": "x"}) == []
