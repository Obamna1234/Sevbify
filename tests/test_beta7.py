"""Fixes from the beta.6 test run on Windows."""
import os

from conftest import make_wav, wait_until
from test_shows_ui import win  # noqa: F401  (fixture: window with fake podcast / Deezer answers)


def loose_windows(app, main):
    """Visible top-level widgets other than the main window, menus and tooltips."""
    from PyQt6.QtWidgets import QApplication, QMenu
    from PyQt6.QtCore import Qt
    out = []
    for w in QApplication.topLevelWidgets():
        if w is main or not w.isVisible() or isinstance(w, QMenu):
            continue
        if w.windowType() in (Qt.WindowType.ToolTip, Qt.WindowType.Popup):
            continue
        out.append(type(w).__name__)
    return out


def test_cards_never_open_as_little_windows(win, qapp):
    """beta.6: Home cards were shown before being put in the window, so they flashed up as small "Sevbify"
    windows (worst while downloads refreshed Home), and could keep the mouse."""
    win.show()
    for chip in ("podcasts", "audiobooks", "all", "podcasts"):
        win.set_home_chip(chip)
        wait_until(qapp, lambda: False, 0.6)
        assert loose_windows(qapp, win) == []
    win.show_podcasts()
    wait_until(qapp, lambda: False, 0.6)
    assert loose_windows(qapp, win) == []
    assert win._top_shows                    # the Top podcasts shelf really loaded


def test_page_rebuild_waits_while_a_menu_is_open(window, qapp, monkeypatch):
    from ui import theme
    window.show()
    lp = window.library_panel
    before = lp.scroll.widget()
    monkeypatch.setattr(theme, "user_is_busy", lambda: True)
    window.create_playlist("New one", [window.songs[0]])
    qapp.processEvents()
    assert lp.scroll.widget() is before        # not pulled away while the user is clicking
    monkeypatch.setattr(theme, "user_is_busy", lambda: False)
    assert wait_until(qapp, lambda: lp.scroll.widget() is not before, 3)
    assert any(e["title"] == "New one" for e in lp.entries())


def test_online_button_switches_offline_and_back(window, qapp):
    window.show()
    assert window.online_enabled
    window.top_bar.online_label.click()
    assert not window.online_enabled and "Offline" in window.top_bar.online_label.text()
    assert window.net.enabled() is False
    wait_until(qapp, lambda: False, 0.2)
    pos = window.top_bar.center.geometry()
    window.top_bar.online_label.click()
    qapp.processEvents()
    assert window.online_enabled and "Online" in window.top_bar.online_label.text()
    wait_until(qapp, lambda: False, 0.2)
    assert window.top_bar.center.geometry().x() == pos.x()      # Home + search don't move


def test_crossfade_overlaps_the_two_songs(open_window, tmp_path, data_dir, qapp):
    audio = tmp_path / "xf"
    audio.mkdir()
    make_wav(audio / "a.wav", 8.0, 440)
    make_wav(audio / "b.wav", 8.0, 550)
    w = open_window(audio_folder=str(audio), data_dir=str(data_dir))
    w.user_data.fade_seconds = 3
    first, second = w.songs[0], w.songs[1]
    w.play_song(first, queue=[first, second])
    assert wait_until(qapp, lambda: w._xf is not None, 12), "crossfade never started"
    assert w.current_song is second            # the next song started while the first fades out
    out = w._xf["out"]
    assert out is not w.player
    assert wait_until(qapp, lambda: w._xf is None, 10)
    import vlc
    assert out.get_state() != vlc.State.Playing      # the old one stopped after the fade
    assert w.current_song is second


def test_effective_volume_curve(window):
    window.user_data.volume, window.user_data.muted = 80, False
    assert window._effective_volume(1.0) == 80
    assert window._effective_volume(0.0) == 0
    half = window._effective_volume(0.5)
    assert 60 < half < 70                        # cube-root: sounds like half, not a sudden drop
    window.user_data.muted = True
    assert window._effective_volume(1.0) == 0


def test_downloaded_episodes_listed_under_downloaded(win, qapp, monkeypatch):
    from core import podcasts
    from pathlib import Path

    def fake_download(url, dest, progress=None, cancelled=lambda: False, chunk=0):
        make_wav(Path(dest), 0.3)
        return dest
    monkeypatch.setattr(win.net, "download", fake_download)
    win.open_show(podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert wait_until(qapp, lambda: len(win._show_ctx["items"]) == 2)
    ep = win._show_ctx["items"][0]
    win.download_items([ep])
    assert wait_until(qapp, lambda: "podcast:ep-2" in win.user_data.offline, 10)
    win._refresh_library_panel()
    win.library_panel.set_chip("downloaded")
    titles = [e["title"] for e in win.library_panel.entries()]
    assert "Fin vs History" in titles             # not followed, but it has a download
    # Offline, the show page lists the downloaded episode so it can play
    win.user_data.online_enabled = False
    win.open_show(podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert [s.title for s in win._show_ctx["items"]] == [ep.title]


def test_episodes_sort_by_release_date(win, qapp):
    from core import podcasts
    win.open_show(podcasts.Show("Fin vs History", feed_url="https://feeds.example.com/fvh"))
    assert wait_until(qapp, lambda: len(win._show_ctx["items"]) == 2)
    newest_first = [e.published for e in win._show_ctx["episodes"]]
    assert newest_first == sorted(newest_first, reverse=True)
    win.show_page.sort_changed.emit("oldest")
    oldest_first = [e.published for e in win._show_ctx["episodes"]]
    assert oldest_first == sorted(oldest_first)
