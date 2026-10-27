"""Now-playing panel, canvas videos and the artist card."""
import os

from conftest import wait_until


class FakeSong:
    def __init__(self, path, title="NARC", artist="Mega Drive"):
        self.file_path, self.title, self.artist = str(path), title, artist


def test_find_canvas_order(tmp_path):
    from core.canvas import find_canvas
    music = tmp_path / "Music"; music.mkdir()
    song = FakeSong(music / "Mega Drive - NARC.mp3")
    data = tmp_path / "data"; (data / "canvas").mkdir(parents=True)
    assert find_canvas(song, str(data)) is None
    (data / "canvas" / "Mega Drive.mp4").write_bytes(b"x")                 # artist-wide
    assert find_canvas(song, str(data)).endswith("Mega Drive.mp4")
    (music / "canvas").mkdir(); (music / "canvas" / "Mega Drive - NARC.webm").write_bytes(b"x")
    assert find_canvas(song, str(data)).endswith(os.path.join("canvas", "Mega Drive - NARC.webm"))
    (music / "Mega Drive - NARC.mp4").write_bytes(b"x")                      # next to the song wins
    assert find_canvas(song, str(data)) == str(music / "Mega Drive - NARC.mp4")


def test_panel_follows_current_song(window, qapp):
    window.set_right_panel("nowplaying")
    window.play_song(window.songs[1], queue=window.songs, source="Your Songs")
    p = window.now_playing_panel
    assert p.title.text() == "02 - second"
    assert p.source_label.text() == "Your Songs"
    assert not p.showing_video
    assert window.nowplaying_btn.toolTip() == "Now playing view"


def test_canvas_video_used_when_present(window, qapp, audio_dir):
    from ui.now_playing_panel import HAVE_VIDEO
    (audio_dir / "02 - second.mp4").write_bytes(b"not really a video")
    window.set_right_panel("nowplaying")
    window.play_song(window.songs[1], queue=window.songs)
    if HAVE_VIDEO:
        # A broken video must fall back to the animated artwork, never crash.
        assert wait_until(qapp, lambda: not window.now_playing_panel.showing_video, timeout=5)


def test_artist_card_messages_offline_and_switched_off(window, qapp):
    from core.models import Song
    song = window.songs[0]
    song.artist = "Mega Drive"
    window.apply_settings({"online_enabled": False, "lastfm_api_key": "", "jamendo_client_id": ""})
    window.play_song(song, queue=window.songs)
    assert "Turn on Online features" in window.now_playing_panel.card_stats.text()


def test_artist_card_filled_from_online(window, qapp, tmp_path):
    from online_fixtures import FakeWeb
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: window.user_data.online_enabled,
                           opener=FakeWeb())
    window.online = OnlineMusic(window.net, "key")
    window._artist_cards.clear()
    window.songs[0].artist = "Mega Drive"
    window.set_right_panel("nowplaying")
    window.play_song(window.songs[0], queue=window.songs)
    p = window.now_playing_panel
    assert wait_until(qapp, lambda: "Mega Drive" == p.card_name.text())
    assert "85,860 fans on Deezer" in p.card_stats.text() and "123,456 listeners" in p.card_stats.text()
    assert "darksynth producer" in p.card_bio.text()
    assert "Last.fm ↗" in p.card_links.text()
