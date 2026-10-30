"""Go to Radio and online (remote) songs in the queue."""
import pytest

from conftest import wait_until
from online_fixtures import FakeWeb


@pytest.fixture
def radio_window(window, tmp_path):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: window.user_data.online_enabled, opener=FakeWeb())
    window.online = OnlineMusic(window.net, "key")
    # Pretend the test files are tagged like real songs.
    seed, owned = window.songs[0], window.songs[1]
    seed.artist, seed.title = "Mega Drive", "NARC"
    owned.artist, owned.title, owned.duration = "Dan Terminus", "Avalanche", 200_000
    return window


def test_radio_builds_queue_with_local_matches_and_previews(radio_window, qapp):
    w = radio_window
    seed = w.songs[0]
    w.play_song(seed, queue=w.songs)
    w.start_radio(seed)
    assert wait_until(qapp, lambda: w.pq.source_name == "NARC Radio")
    items = w.pq.items
    assert items[0] == seed and items.count(seed) == 1
    assert w.songs[1] in items                                  # the song you own, not a preview
    remote = [s for s in items if getattr(s, "is_remote", False)]
    assert remote and not any(s.is_preview for s in remote)   # always full songs
    assert "Avalanche" not in [s.title for s in remote]
    w.set_right_panel("queue")
    texts = [lbl.text() for lbl in w.queue_panel.scroll.widget().findChildren(type(w.song_info))]
    assert "Next from: NARC Radio" in texts
    assert any(t.endswith("online") for t in texts)


def test_remote_song_plays_from_its_stream(radio_window, qapp, audio_dir):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    w = radio_window
    t = OnlineTrack("Free Song", "CC Artist", source="jamendo", stream_url=str(audio_dir / "03 - third.wav"))
    rs = RemoteSong(t)
    assert not rs.is_preview
    w.play_song(rs, queue=[rs], source="Test")
    assert wait_until(qapp, lambda: w._reached_playing)
    assert w.current_song is rs


def test_remote_songs_skipped_when_online_switched_off(radio_window, qapp):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    w = radio_window
    w.apply_settings({"online_enabled": False, "lastfm_api_key": "key", "jamendo_client_id": ""})
    rs = RemoteSong(OnlineTrack("X", "Y", preview_url="https://example.com/x.mp3"))
    w.play_song(rs, queue=[rs, w.songs[2]])
    assert "online features are switched off" in w.status_label.text()
    assert wait_until(qapp, lambda: w.current_song is w.songs[2])


def test_radio_menu_disabled_when_offline_switch_off(radio_window):
    w = radio_window
    w.apply_settings({"online_enabled": False, "lastfm_api_key": "", "jamendo_client_id": ""})
    menu = w.build_song_menu(w.songs[0], queue=w.songs)
    act = next(a for a in menu.actions() if "song radio" in a.text())
    assert not act.isEnabled() and "turn on Online features" in act.text()
    open_in = next(a for a in menu.actions() if "Open in" in a.text()).menu()
    labels = [a.text() for a in open_in.actions()]
    assert {"Spotify", "YouTube Music", "Apple Music", "Bandcamp"} <= set(labels)


def test_recent_list_saves_only_local_files(radio_window, qapp):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    w = radio_window
    w.pq.record_played(RemoteSong(OnlineTrack("A", "B")))
    w.pq.record_played(w.songs[2])
    w.save_now()
    assert w.user_data.recent == [w.songs[2].file_path]
