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

