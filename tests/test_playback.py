"""Playback regression tests. Run: python -m pytest tests -v"""
import os
import time
from pathlib import Path

from conftest import VLC_TEST_ARGS, make_wav, wait_until


def test_library_scanned(window):
    assert [s.title for s in window.songs] == ["01 - first", "02 - second", "03 - third"]
    assert all(s.duration > 900 for s in window.songs)


def test_play_song_does_not_block(window, qapp):
    start = time.perf_counter()
    window.play_song(window.songs[0])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"play_song blocked the UI for {elapsed:.2f}s"
    assert wait_until(qapp, lambda: window._reached_playing)
    assert window.play_btn.text() == "⏸"


def test_track_end_advances_exactly_once(window, qapp):
    window.play_song(window.songs[0], queue=window.songs)
    assert wait_until(qapp, lambda: window.songs[1] in window.pq.recent)
    # Played in order with nothing skipped: first, then second (the silent test
    # audio plays faster than real time, so the third may already have started).
    played = list(reversed(window.pq.recent))
    assert played[:2] == [window.songs[0], window.songs[1]]
    assert "Skipped" not in window.status_label.text()


def test_pause_and_resume(open_window, qapp, tmp_path, data_dir):
    import vlc

    audio = tmp_path / "long"
    audio.mkdir()
    make_wav(audio / "long.wav", 6.0)
    w = open_window(audio_folder=str(audio), data_dir=str(data_dir))
    w.play_song(w.songs[0])
    assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Playing)
    w.play_pause_song()
    assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Paused)
    assert w.play_btn.text() == "▶️"
    w.play_pause_song()
    assert wait_until(qapp, lambda: w.player.get_state() == vlc.State.Playing)
    assert w.play_btn.text() == "⏸"


def test_missing_file_is_skipped_with_message(window, qapp):
    os.remove(window.songs[1].file_path)
    window.play_song(window.songs[1])
    assert wait_until(qapp, lambda: window.current_song is window.songs[2] and window._reached_playing)
    # The message must still be visible after the next song has started.
    assert "Skipped" in window.status_label.text()


def test_corrupt_file_is_skipped_with_message(window, qapp):
    Path(window.songs[0].file_path).write_bytes(b"this is not audio")
    window.play_song(window.songs[0])
    assert wait_until(qapp, lambda: "Skipped" in window.status_label.text())
    assert wait_until(qapp, lambda: window.current_song is window.songs[1] and window._reached_playing)


def test_all_bad_files_stop_instead_of_looping(window, qapp):
    for s in window.songs:
        os.remove(s.file_path)
    start = time.perf_counter()
    window.play_song(window.songs[0])
    assert wait_until(qapp, lambda: "No playable songs" in window.status_label.text(), timeout=5)
    assert time.perf_counter() - start < 5
    assert window.play_btn.text() == "▶️"


def test_playlist_queue_stays_in_playlist(window, qapp):
    from ui.main_window import Playlist

    pl = Playlist("Test")
    pl.add_song(window.songs[2])
    pl.add_song(window.songs[0])
    window.play_playlist(pl)
    assert [s.title for s in window.queue] == ["03 - third", "01 - first"]
    window.next_song()
    assert window.current_song is window.songs[0]
    window.next_song()
    assert window.current_song is window.songs[2]  # wraps within the playlist


def test_finds_music_when_launched_from_another_folder(open_window, tmp_path, data_dir, monkeypatch):
    from core import paths
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    # Paths must not depend on the current working directory.
    assert os.path.isfile(paths.PLACEHOLDER_IMAGE)
    assert os.path.isabs(paths.AUDIO_FOLDER)
    # No audio_folder given: uses the default music folder.
    w = open_window(data_dir=str(data_dir))
    if os.path.isdir(os.path.join(paths.PROJECT_ROOT, "audio")):
        assert len(w.songs) > 0, "bundled audio/ folder not found from another working directory"
    assert not (elsewhere / "album_covers").exists()


def test_volume_and_mute(window):
    window.volume_slider.setValue(30)
    assert window.user_data.volume == 30
    assert window.mute_btn.text() == "🔉"
    window.toggle_mute()
    assert window.user_data.muted and window.mute_btn.text() == "🔇"
    window.volume_slider.setValue(60)  # moving the slider unmutes
    assert not window.user_data.muted and window.mute_btn.text() == "🔊"


def test_now_playing_highlight_in_library(window, qapp):
    from ui.track_table import GREEN
    window.play_song(window.songs[1])
    row = [s.key for s in window.library_table.songs_in_view()].index(window.songs[1].key)
    assert window.library_table.item(row, 1).foreground().color() == GREEN
