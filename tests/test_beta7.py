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


class _WindowWatcher:
    """Records every widget that is shown as a window of its own (even for an instant)."""

    def __init__(self, app, main):
        from PyQt6.QtCore import QObject, QEvent
        from PyQt6.QtWidgets import QMenu, QWidget
        seen = self.seen = []

        class F(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow() \
                        and obj is not main and not isinstance(obj, QMenu) \
                        and obj.windowType() not in (Qt.WindowType.ToolTip, Qt.WindowType.Popup):
                    seen.append(type(obj).__name__)
                return False
        from PyQt6.QtCore import Qt
        self.f = F()
        app.installEventFilter(self.f)
        self.app = app

    def stop(self):
        self.app.removeEventFilter(self.f)


def test_cards_never_open_as_little_windows(win, qapp):
    """beta.6: Home cards were shown before being put in the window, so on Windows they flashed up as small
    "Sevbify" windows (worst while downloads refreshed Home), and could keep the mouse."""
    win.show()
    watch = _WindowWatcher(qapp, win)
    for chip in ("podcasts", "audiobooks", "all", "podcasts"):
        win.set_home_chip(chip)
        wait_until(qapp, lambda: False, 0.6)
        assert loose_windows(qapp, win) == []
    win.show_podcasts()
    wait_until(qapp, lambda: False, 0.6)
    assert loose_windows(qapp, win) == []
    assert win._top_shows                    # the Top podcasts shelf really loaded
    watch.stop()
    assert watch.seen == [], watch.seen     # not even for an instant


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


def test_shift_and_ctrl_click_select_like_spotify(window, qapp):
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import Qt, QPoint
    from ui import track_table
    pl = window.create_playlist("Sel", list(window.songs))
    window.show_playlist(pl)
    window.show()
    t = window.pl_table
    qapp.processEvents()

    def click(row, mods=Qt.KeyboardModifier.NoModifier):
        rect = t.visualRect(t.model().index(row, 3))
        QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, mods, rect.center())

    click(0)
    click(2, Qt.KeyboardModifier.ShiftModifier)
    assert t.selected_rows() == [0, 1, 2]
    click(1, Qt.KeyboardModifier.ControlModifier)
    assert t.selected_rows() == [0, 2]
    # Right-click inside the selection: the menu is for both songs
    track_table.menu_selection = [t.song_at(0), t.song_at(2)]
    track_table.menu_selection_rows = [0, 2]
    menu = window.build_song_menu(t.song_at(0), playlist=pl, row=0)
    texts = [a.text() for a in menu.actions()]
    assert "2 songs selected" in texts and "✕  Remove 2 from this playlist" in texts
    track_table.menu_selection, track_table.menu_selection_rows = [], []
    first, third = pl.songs[0], pl.songs[2]
    window.remove_rows_from_playlist(pl, [0, 2])
    assert first not in pl.songs and third not in pl.songs and len(pl.songs) == len(window.songs) - 2


def test_zoom_keys_and_reset_settings_keep_your_music(window, qapp):
    window._auto_answer_dialogs = True
    pl = window.create_playlist("Keep me", [window.songs[0]])
    assert window.change_zoom(+1) == 110 and window.change_zoom(+1) == 125
    assert window.user_data.zoom == 125 and not window.restart_bar.isHidden()
    assert window.change_zoom(0) == 100
    window.change_zoom(+1)
    window.apply_settings({"fade_seconds": 7, "autoplay": False, "canvas_enabled": False})
    window.library_panel.set_view_options(view="grid")
    assert window.reset_settings("appearance")
    u = window.user_data
    assert u.zoom == 100 and u.library_view == "list" and u.canvas_enabled
    assert u.fade_seconds == 7                       # appearance only
    assert window.reset_settings("all")
    assert u.fade_seconds == 0 and u.autoplay
    assert pl in window.playlists and window.songs and u.music_folders   # music and playlists kept
    window._auto_answer_dialogs = False
    assert not window.reset_settings("all")          # Cancel changes nothing


def test_delete_asks_with_spotify_card_and_never_touches_files(window, qapp):
    pl = window.create_playlist("Bin me", [window.songs[0]])
    path = window.songs[0].file_path
    window._auto_answer_dialogs = False
    window._confirm_delete_playlist(pl)
    assert pl in window.playlists
    window._auto_answer_dialogs = True
    window._confirm_delete_playlist(pl)
    assert pl not in window.playlists and os.path.exists(path)
    window.create_folder("Box")
    window._confirm_delete_folder("Box")
    assert "Box" not in window.user_data.folders


def test_playlist_menu_has_spotify_items_and_export_copy(window, qapp, tmp_path):
    from core import playlist_files as pf
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    pl = window.create_playlist("Trip", list(window.songs) + [RemoteSong(OnlineTrack("Later", "Band"))])
    texts = [a.text() for a in window.build_playlist_menu(pl).actions()]
    for t in ("✎  Edit details", "⊖  Delete", "📁  Move to folder", "＋  Add to other playlist", "⇪  Share and export"):
        assert t in texts
    n, pending = pf.export_playlist(pl.songs, str(tmp_path / "trip.m3u8"))
    assert (n, pending) == (len(window.songs), 1)
    text = (tmp_path / "trip.m3u8").read_text(encoding="utf-8")
    assert text.count("#EXTINF") == len(window.songs) and "# not downloaded yet: Band - Later" in text
    res = pf.copy_playlist(pl.songs, str(tmp_path / "phone"), "Trip")
    files = sorted(os.listdir(res["folder"]))
    assert res["copied"] == len(window.songs) and res["pending"] == 1 and files[0].startswith("1 - ") is False
    assert files[0].startswith("01 - ") and "Trip.m3u8" in files
    again = pf.copy_playlist(pl.songs, str(tmp_path / "phone"), "Trip")
    assert again["copied"] == 0 and again["skipped"] == len(window.songs)   # nothing copied twice


def test_miniplayer_and_full_screen_keep_playing(window, qapp):
    window.play_song(window.songs[0], queue=window.songs)
    wait_until(qapp, lambda: window.is_playing, 3)
    window.open_mini_player()
    assert window.mini_player is not None and window.mini_player.isVisible()
    window.mini_player.controls.next.click()
    assert window.current_song is window.songs[1]
    window.mini_player.close()
    window.showNormal()
    window.open_full_screen()
    assert window.full_screen_view.isVisible()
    window.full_screen_view.close()
    assert window.full_screen_view is None and window.current_song is window.songs[1]


def test_canvas_video_from_the_song_menu_and_hide_canvas(window, qapp, tmp_path):
    from core import canvas as cv
    song = window.songs[0]
    video = tmp_path / "loop.mp4"
    video.write_bytes(b"fake mp4")
    texts = [a.text() for a in window.build_song_menu(song).actions()]
    assert "▣  Canvas video" in texts and "▣  Hide Canvas" not in texts       # no loop yet
    cv.set_canvas(song, str(video), window.storage.data_dir)
    assert cv.find_canvas(song, window.storage.data_dir)
    menu = window.build_song_menu(song)
    hide = next(a for a in menu.actions() if a.text() == "▣  Hide Canvas")
    hide.trigger()
    assert window.user_data.canvas_enabled is False
    assert any(a.text() == "▣  Show Canvas" for a in window.build_song_menu(song).actions())
    assert cv.remove_canvas(song, window.storage.data_dir) and not cv.find_canvas(song, window.storage.data_dir)


def test_private_session_remembers_nothing(window, qapp):
    pl = window.create_playlist("Quiet", [window.songs[0]])
    before = pl.last_played
    window.apply_settings({"private_session": True})
    assert window.top_bar.private_label.isVisibleTo(window.top_bar)
    window.show_playlist(pl)
    window.play_song(window.songs[0], queue=[window.songs[0]])
    assert window.songs[0] not in window.pq.recent and pl.last_played == before
    assert window._private_timer.isActive()               # ends by itself after 6 hours
    window.apply_settings({"private_session": False})
    window.play_song(window.songs[1], queue=[window.songs[1]])
    assert window.songs[1] in window.pq.recent
    assert not window.top_bar.private_label.isVisibleTo(window.top_bar)


def _drag_events(widget, mime, pos):
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    from PyQt6.QtWidgets import QApplication
    enter = QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, enter)
    move = QDragMoveEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, move)
    drop = QDropEvent(QPointF(pos), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, drop)
    return enter.isAccepted(), move.isAccepted(), drop.isAccepted()


def test_files_dragged_from_explorer_are_accepted(window, qapp, audio_dir):
    """beta.6 showed the "not allowed" cursor: the song list had switched drops off."""
    from PyQt6.QtCore import QMimeData, QUrl, QPoint
    from ui.library_panel import LibraryRow
    pl = window.create_playlist("Empty", [])
    window.show_playlist(pl)
    window.resize(1400, 900)
    window.show()
    qapp.processEvents()
    files = sorted(audio_dir.iterdir())
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in files])
    vp = window.pl_table.viewport()
    assert vp.acceptDrops() and window.pl_table.acceptDrops()
    assert _drag_events(vp, mime, QPoint(vp.width() // 2, 20)) == (True, True, True)
    assert [s.file_path for s in pl.songs] == [str(p) for p in files]          # same order, no copies made
    assert all(not getattr(s, "is_remote", False) for s in pl.songs)
    other = window.create_playlist("Other", [])
    window._refresh_library_panel()
    qapp.processEvents()
    row = next(r for r in window.library_panel.findChildren(LibraryRow) if r.accepts_drops and r.title_text == "Other")
    assert row.acceptDrops()
    _drag_events(row, mime, QPoint(10, 10))
    assert wait_until(qapp, lambda: len(other.songs) == len(files), 3)


def test_playlist_preview_steps_through_songs(window, qapp):
    pl = window.create_playlist("Peek", list(window.songs))
    window.show_playlist(pl)
    assert window.pl_preview_btn.isVisibleTo(window.playlist_page)
    window.open_preview()
    page = window.preview_page
    assert window.stack.currentWidget() is page and window.current_song is pl.songs[0]
    assert page.position.text() == f"1 of {len(pl.songs)}"
    page.next_btn.click()
    assert window.current_song is pl.songs[1] and page.title.text() == pl.songs[1].title
    page.step(-1)
    assert window.current_song is pl.songs[0]
    page.leave()
    assert window.stack.currentWidget() is window.playlist_page


def test_no_window_flashes_while_downloads_refresh_the_pages(window, qapp):
    import time
    from test_download import prepare, fake_ok, remote
    window.show()
    watch = _WindowWatcher(qapp, window)

    def slow(song, *a, **k):
        time.sleep(0.15)
        return fake_ok(song, *a, **k)
    prepare(window, slow)
    pl = window.create_playlist("Mix", [remote(f"T{i}", "Art") for i in range(4)])
    for page in (window.show_saved, window.show_home, lambda: window.show_playlist(pl)):
        page()
        window.download_songs([s for s in pl.songs if getattr(s, "is_remote", False)][:2])
        wait_until(qapp, lambda: not window.downloads.is_busy(), 10)
        wait_until(qapp, lambda: False, 0.6)
    watch.stop()
    assert watch.seen == []
