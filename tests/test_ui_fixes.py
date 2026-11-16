"""Fixes from the owner's first test on Windows (27 Oct 2026)."""
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from conftest import make_wav, wait_until


def catch_errors(monkeypatch):
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: errors.append(a[1]))
    return errors


def test_clicking_a_library_row_that_rebuilds_the_list_does_not_crash(window, qapp, monkeypatch):
    errors = catch_errors(monkeypatch)
    window.create_playlist("bm", [window.songs[0]])
    window.show()
    qapp.processEvents()
    from ui.library_panel import LibraryRow
    rows = [r for r in window.library_panel.findChildren(LibraryRow)]
    assert rows
    for _ in range(3):                                    # each click rebuilds the panel (new active row)
        row = window.library_panel.findChildren(LibraryRow)[-1]
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)
        qapp.processEvents()
    assert not errors, errors
    assert window.stack.currentWidget() is window.playlist_page


# --- downloads: folders, privacy, playlist files ------------------------------------------------------------------

def test_download_folder_is_never_nested(window, tmp_path):
    dl = tmp_path / "Music" / "Sevbify downloads"
    dl.mkdir(parents=True)
    window.user_data.music_folders = [str(tmp_path / "gone" / "audio"), str(dl)]   # old folder no longer exists
    assert window.download_folder() == str(dl)
    other = tmp_path / "Other"
    other.mkdir()
    window.user_data.music_folders = [str(other)]
    assert window.download_folder() == str(other / "Sevbify downloads")
    chosen = tmp_path / "Chosen"
    window.user_data.download_folder = str(chosen)
    assert window.download_folder() == str(chosen) and chosen.is_dir()
    assert str(chosen) in window.user_data.music_folders


def test_missing_folder_is_reported_once(window, qapp, tmp_path):
    window.user_data.music_folders = [str(tmp_path / "moved away"), window.user_data.music_folders[0]]
    window.rescan_library()
    assert wait_until(qapp, lambda: "Folder not found" in window.status_label.text())
    assert "remove it with ✕" in window.status_label.text()
    window.clear_status()
    window.rescan_library()
    assert wait_until(qapp, lambda: not window._rescan_pending and window._scan_thread is None
                      or (window._scan_thread and not window._scan_thread.isRunning()))
    qapp.processEvents()
    assert "Folder not found" not in window.status_label.text()


def test_artist_folders():
    from core.downloader import artist_folder as a
    assert a("Straplocked feat. Occams Laser") == "Straplocked"
    assert a("Kalwi x Remi") == "Kalwi"
    assert a("Rex Orange County ft. Someone") == "Rex Orange County"
    assert a("Simon & Garfunkel") == "Simon & Garfunkel"         # bands with & / , stay whole
    assert a("Earth, Wind & Fire") == "Earth, Wind & Fire"
    assert a("AC/DC") == "AC-DC"
    assert a("CON") == "CON (artist)" and a("") == "Unknown Artist"


def test_downloads_are_filed_by_artist(qapp, tmp_path):
    from ui.download_manager import DownloadManager
    from core.online.models import OnlineTrack
    from pathlib import Path
    m = DownloadManager()
    m.check_tools = lambda: []
    seen = []

    def fake(song, out_dir, opts, state, say, step=lambda _t: None):
        seen.append(out_dir)
        path = os.path.join(out_dir, song + ".wav")
        make_wav(Path(path), 0.1)
        return {"status": "ok", "path": path}

    m.process = fake
    done = []
    m.run_finished.connect(done.append)
    m.request([OnlineTrack("Those in My Way", "Straplocked feat. Occams Laser")], str(tmp_path))
    assert wait_until(qapp, lambda: done, 10)
    m.wait()
    assert seen == [str(tmp_path / "Straplocked")]


def test_youtube_downloads_dont_use_browser_sign_in_unless_allowed(monkeypatch):
    import types
    from core import downloader
    assert getattr(downloader.engine().download_youtube_mp3, "_sevbify_cookies", False)   # the real engine is wrapped
    calls = []
    fake_engine = types.SimpleNamespace(
        download_youtube_mp3=lambda q, o, l, use_cookies=True: calls.append(use_cookies) or True)
    downloader._respect_cookie_setting(fake_engine)
    monkeypatch.setattr(downloader, "ALLOW_BROWSER_COOKIES", False)
    fake_engine.download_youtube_mp3("a - b", "/tmp", print)
    monkeypatch.setattr(downloader, "ALLOW_BROWSER_COOKIES", True)
    fake_engine.download_youtube_mp3("a - b", "/tmp", print)
    assert calls == [False, True]


def test_no_console_windows_flag():
    from core.platform_fixes import hide_console_windows, CREATE_NO_WINDOW

    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

    assert hide_console_windows(FakePopen, windows=True)
    assert FakePopen(["ffmpeg"]).kwargs["creationflags"] == CREATE_NO_WINDOW
    assert FakePopen(["x"], creationflags=8).kwargs["creationflags"] == 8       # caller's own flags are kept
    assert hide_console_windows(FakePopen, windows=True)                     # applying twice is harmless
    assert not hide_console_windows(FakePopen, windows=False)


def test_show_in_folder_commands(tmp_path):
    from core.platform_fixes import reveal_in_file_manager
    ran = []
    f = tmp_path / "My Song.mp3"
    reveal_in_file_manager(str(f), run=ran.append, system="win32")
    reveal_in_file_manager(str(f), run=ran.append, system="darwin")
    reveal_in_file_manager(str(f), run=ran.append, system="linux")
    assert ran[0].lower().endswith(f'explorer.exe" /select,"{f}"'.lower()) and ran[0].startswith('"')
    assert ran[1] == ["/usr/bin/open", "-R", str(f)] and ran[2] == ["xdg-open", str(tmp_path)]


def test_show_in_folder_is_in_the_menu_for_your_own_songs(window):
    texts = [a.text() for a in window.build_song_menu(window.songs[0]).actions()]
    assert "📂  Show in folder" in texts


def test_playlist_files_for_phones(window, audio_dir, tmp_path):
    from core import playlist_files
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    dl = audio_dir / "Sevbify downloads"
    dl.mkdir()
    pl = window.create_playlist("Road / Trip", [window.songs[2], RemoteSong(OnlineTrack("Later", "Band")),
                                               window.songs[0]])
    written = window.write_playlist_files()
    path = dl / "Playlists" / "Road _ Trip.m3u8"
    assert [str(path)] == written
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[:2] == ["#EXTM3U", playlist_files.MARKER]
    assert text[3] == "../../03 - third.wav"                     # relative: the folder can be copied as a whole
    assert "# not downloaded yet: Band - Later" in text
    assert text[-1] == "../../01 - first.wav"                    # same order as the playlist
    # your own .m3u8 files are never touched; ours are removed when the playlist goes
    mine = dl / "Playlists" / "Mine.m3u8"
    mine.write_text("#EXTM3U\nsong.mp3\n", encoding="utf-8")
    window.delete_playlist(pl)
    window.write_playlist_files()
    assert not path.exists() and mine.exists()


# --- song lists: hover ▶, deselect, drag and drop, seek bar ------------------------------------------------------

def test_hover_shows_play_and_clicking_it_plays(window, qapp):
    from PyQt6.QtCore import QPoint
    t = window.library_table
    window.show_library()
    window.show()
    qapp.processEvents()
    t._set_hover(1)
    assert t.item(1, 0).text() == "▶"
    t._set_hover(-1)
    assert t.item(1, 0).text() == "2"                        # the number comes back
    rect = t.visualItemRect(t.item(1, 0))
    QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert wait_until(qapp, lambda: window.current_song is t.song_at(1))


def test_clicking_empty_space_clears_the_selection(window, qapp):
    from PyQt6.QtCore import QPoint
    t = window.library_table
    window.show_library()
    window.show()
    t.resize(800, 600)
    qapp.processEvents()
    t.selectRow(0)
    assert t.selectedItems()
    QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(200, t.viewport().height() - 5))
    assert not t.selectedItems()
    t.selectRow(0)
    QTest.keyClick(t, Qt.Key.Key_Escape)
    assert not t.selectedItems()


def test_selected_rows_are_grey_not_white(qapp):
    from ui.track_table import TrackTable, ROW_SELECTED, ROW_HOVER
    from ui import theme
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    # The whole row is painted grey when selected (and on hover), never white, never one cell at a time.
    t = TrackTable()
    t.resize(600, 200)
    t.set_songs([RemoteSong(OnlineTrack("A", "B")), RemoteSong(OnlineTrack("C", "D"))])
    t.selectRow(0)
    img = t.viewport().grab().toImage()
    y = t.rowViewportPosition(0) + 4
    for x in (t.columnViewportPosition(2) + 2, t.columnViewportPosition(3) + 40, 590):
        assert img.pixelColor(x, y).name() == ROW_SELECTED.name()
    t._set_hover(1)
    img = t.viewport().grab().toImage()
    y1 = t.rowViewportPosition(1) + 4
    assert img.pixelColor(t.columnViewportPosition(3) + 40, y1).name() == ROW_HOVER.name()
    from PyQt6.QtGui import QPalette
    theme.apply_dark_palette(qapp)
    assert qapp.palette().color(QPalette.ColorRole.Highlight).name() == theme.ROW_SELECTED
    assert qapp.palette().color(QPalette.ColorRole.Base).name() == theme.PANEL


def test_drag_to_reorder_a_playlist(window):
    pl = window.create_playlist("Order", list(window.songs))
    window.show_playlist(pl)
    first, second, third = pl.songs
    window.pl_table.rows_moved.emit(0, 2)                     # what a drop of row 0 onto row 2 sends
    assert pl.songs == [second, third, first]
    assert window.pl_table.song_at(2) is first


def test_drop_files_and_folders_from_explorer(window, audio_dir, tmp_path):
    from pathlib import Path
    pl = window.create_playlist("Dropped", [window.songs[0]])
    window.show_playlist(pl)
    outside = tmp_path / "Elsewhere" / "Album"
    outside.mkdir(parents=True)
    make_wav(outside / "b.wav", 0.2)
    make_wav(outside / "a.wav", 0.2)
    (outside / "cover.jpg").write_bytes(b"x")
    window.pl_table.files_dropped.emit([str(outside.parent)], 0)      # a folder, dropped at the top
    assert [os.path.basename(s.file_path) for s in pl.songs] == ["a.wav", "b.wav", "01 - first.wav"]
    assert window.add_files_to_playlist(pl, [str(outside / "a.wav")]) == 0        # no duplicates
    assert window.add_files_to_playlist(pl, [str(outside / "cover.jpg")]) == 0
    assert "aren't music files" in window.status_label.text()


def test_drag_songs_onto_a_playlist_on_the_left(window, qapp):
    from ui.library_panel import LibraryRow
    pl = window.create_playlist("Target", [])
    qapp.processEvents()
    row = next(r for r in window.library_panel.findChildren(LibraryRow) if r.accepts_drops)
    row.songs_dropped.emit([window.songs[1], window.songs[2]])
    assert pl.songs == [window.songs[1], window.songs[2]]


def test_click_anywhere_on_the_progress_bar(window, qapp):
    from PyQt6.QtCore import QPoint
    s = window.volume_slider
    window.show()
    s.resize(200, 20)
    qapp.processEvents()
    QTest.mouseClick(s, Qt.MouseButton.LeftButton, pos=QPoint(190, 10))
    assert s.value() > 85                                      # jumped to where it was clicked
    QTest.mouseClick(s, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert s.value() < 15


# --- Song radio ---------------------------------------------------------------------------------------------------

def test_radio_order_spreads_artists_and_mixes_in_your_songs(window):
    import random
    from core.online.providers import spread_artists
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    ts = [OnlineTrack("a1", "A"), OnlineTrack("a2", "A"), OnlineTrack("b1", "B"), OnlineTrack("a3", "A"),
          OnlineTrack("c1", "C")]
    order = [t.title for t in spread_artists(ts, first_artist="Seed")]
    assert order == ["a1", "b1", "a2", "c1", "a3"]                 # never the same artist twice in a row
    assert [t.title for t in spread_artists(ts, first_artist="A")][0] == "b1"   # not right after the seed artist

    seed = window.songs[0]
    seed.artist = "Seed Artist"
    window.songs[1].artist = window.songs[2].artist = "B"
    radio = [seed] + [RemoteSong(OnlineTrack(f"t{i}", "B" if i % 3 == 0 else f"X{i}")) for i in range(16)]
    mixed = window._mix_in_your_songs(radio, seed, rng=random.Random(1))
    yours = [i for i, s in enumerate(mixed) if not getattr(s, "is_remote", False) and s is not seed]
    assert set(mixed[i] for i in yours) == {window.songs[1], window.songs[2]}
    assert yours[0] >= 4 and yours[1] - yours[0] >= 5               # spaced out, not at the start
    assert mixed[0] is seed


def test_starting_radio_opens_the_radio_page(window, qapp, tmp_path):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    from online_fixtures import FakeWeb
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: True, opener=FakeWeb())
    window.online = OnlineMusic(window.net, "key")
    seed = window.songs[0]
    seed.artist, seed.title = "Mega Drive", "NARC"
    window.start_radio(seed)
    assert wait_until(qapp, lambda: window.stack.currentWidget() is window.radio_page)
    assert window._radio_name == "NARC Radio" and window.radio_table.song_at(0) is seed
    labels = [l.text() for l in window.radio_page.findChildren(type(window.song_info))]
    assert "Song radio" in labels and "NARC Radio" in labels
    assert any(t.startswith("With ") and "songs" in t for t in labels)
    window.show_home()
    window.go_back()                                                # Back returns to the radio
    assert window.stack.currentWidget() is window.radio_page
    pl = window.save_songs_as_playlist(window._radio_name, window._radio_songs)
    assert pl.name == "NARC Radio" and len(pl.songs) == len(window._radio_songs)


# --- menus, sleep timer -----------------------------------------------------------------------------------------

def menu_tree(menu):
    out = {}
    for a in menu.actions():
        if a.isSeparator():
            continue
        out[a.text()] = menu_tree(a.menu()) if a.menu() else a
    return out


def test_app_menu_has_spotifys_sections_and_shortcuts(window):
    tree = menu_tree(window.build_app_menu())
    assert list(tree) == ["File", "Edit", "View", "Playback", "Help"]
    assert tree["File"]["New Playlist"].shortcut().toString() == "Ctrl+N"
    assert tree["Edit"]["Search"].shortcut().toString() == "Ctrl+L"
    assert tree["Edit"]["Filter Your Library"].shortcut().toString() == "Ctrl+F"
    pb = tree["Playback"]
    assert pb["Seek Forward"].shortcut().toString() == "Shift+Right"
    assert "☾  Sleep timer" in pb and "Volume Up" in pb
    assert "Troubleshooting" in tree["Help"] and "About Sevbify" in tree["Help"]
    tree["Edit"]["Search"].trigger()
    assert window.stack.currentWidget() is window.search_page


def test_song_menu_in_spotify_order_with_find_a_playlist(window):
    for name in ("Rock", "Chill", "Road Trip"):
        window.create_playlist(name, [])
    window.songs[0].artist = "Mega Drive"
    menu = window.build_song_menu(window.songs[0])
    tree = menu_tree(menu)
    names = list(tree)
    assert names[:3] == ["＋  Add to playlist", "♡  Add to Liked Songs", "≡  Add to queue"]
    assert names.index("◉  Go to song radio") > names.index("☾  Sleep timer")
    assert "👤  Go to artist" in names
    sub = tree["＋  Add to playlist"]
    assert "＋  New playlist" in sub and {"Rock", "Chill", "Road Trip"} <= set(sub)
    window._last_playlist_finder.setText("ro")                    # Find a playlist
    assert sub["Rock"].isVisible() and sub["Road Trip"].isVisible() and not sub["Chill"].isVisible()
    sub["Rock"].trigger()
    assert next(p for p in window.playlists if p.name == "Rock").songs == [window.songs[0]]


def test_sleep_timer(window, qapp):
    window.set_sleep_timer(15)
    assert window._sleep_timer.isActive() and 14 * 60_000 < window._sleep_timer.remainingTime() <= 15 * 60_000 + 1000
    window.set_sleep_timer("track")
    assert not window._sleep_timer.isActive() and window._sleep_at_track_end
    window.play_song(window.songs[0], queue=window.songs)
    assert wait_until(qapp, lambda: window._reached_playing)
    # when the song ends, the next one doesn't start
    assert wait_until(qapp, lambda: not window.is_playing, 10)
    assert window.current_song is window.songs[0] and "Sleep timer" in window.status_label.text()
    window.set_sleep_timer(None)
    assert not window._sleep_at_track_end


def test_seek_by_and_go_to_artist(window, qapp):
    window.play_song(window.songs[0])
    window.seek_by(5000)                                         # no crash on a short song
    window.songs[1].artist = "Mega Drive"
    tree = menu_tree(window.build_song_menu(window.songs[1]))
    tree["👤  Go to artist"].trigger()
    # Online: the artist's own page (popular songs, releases); offline: a search for them
    assert (window.stack.currentWidget() is window.genre_page and window.genre_page.title == "Mega Drive") or \
        (window.stack.currentWidget() is window.search_page and window.search_input.text() == "Mega Drive")


def test_player_bar_buttons_have_spotify_labels_and_lyrics_can_be_unavailable(window, qapp):
    from ui.widgets import HoverHint
    names = {b.toolTip() for b in window.player_bar.findChildren(type(window.queue_btn))}
    for want in ("Lyrics", "Now playing view", "Queue", "Connect to a device", "Open Miniplayer", "Enter Full screen"):
        assert want in names
    assert any(h.button is window.queue_btn for h in HoverHint._instances)
    window._set_lyrics_available(False)
    from PyQt6.QtCore import Qt
    assert window.lyrics_btn.cursor().shape() == Qt.CursorShape.ForbiddenCursor
    before = window.stack.currentWidget()
    window.toggle_lyrics()                                  # does nothing: no lyrics for this song
    assert window.stack.currentWidget() is before
    window._set_lyrics_available(True)
    assert window.lyrics_btn.toolTip() == "Lyrics"


def test_liked_songs_heart_menu_and_pinned_first(window, qapp, tmp_path):
    """Spotify's Liked Songs: the heart (song menu or next to the playing song) adds it, newest first; the
    playlist is pinned at the top of Your Library, keeps its name and survives a restart."""
    a, b = window.songs[0], window.songs[1]
    assert window.liked_playlist() is None and not window.is_liked(a)
    window.toggle_like(a)
    window.toggle_like(b)
    liked = window.liked_playlist()
    assert liked.name == "Liked Songs" and liked.songs == [b, a] and os.path.isfile(liked.custom_cover)
    assert window.library_panel.entries()[0]["obj"] is liked
    names = list(menu_tree(window.build_song_menu(a)))
    assert "♥  Remove from your Liked Songs" in names
    assert not window.rename_playlist(liked, "Something else") and liked.name == "Liked Songs"
    window.play_song(a)
    window._update_like_button()
    assert window.like_btn.isVisibleTo(window) and "Remove" in window.like_btn.toolTip()
    window.like_btn.click()
    assert not window.is_liked(a) and liked.songs == [b]
    window.save_now()
    from core.storage import Storage
    stored = Storage(window.storage.data_dir).load()
    assert any(p.origin == "liked" and p.name == "Liked Songs" for p in stored.playlists)


def test_menus_show_outline_icons_instead_of_symbols(window):
    from ui.menu_style import polish
    menu = window.build_song_menu(window.songs[0])
    polish(menu)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Add to queue" in texts and "Go to song radio" in texts
    assert all(not a.icon().isNull() for a in menu.actions() if a.text() in ("Add to queue", "Go to song radio"))


def test_folders_dropped_on_your_library_become_playlists_with_their_cover(window, tmp_path):
    """A folder dragged from File Explorer onto Your Library: a playlist named after it, songs in the folder's
    order, and the folder's own cover picture."""
    from PyQt6.QtGui import QImage
    album = tmp_path / "Night Drive"
    album.mkdir()
    for name in ("02 - Two.wav", "01 - One.wav", "03 - Three.wav"):
        make_wav(album / name, 0.3)
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(0x336699)
    img.save(str(album / "Cover.jpg"))
    made = window.playlists_from_dropped([str(album)])
    assert [p.name for p in made] == ["Night Drive"]
    pl = made[0]
    assert [os.path.basename(s.file_path) for s in pl.songs] == ["01 - One.wav", "02 - Two.wav", "03 - Three.wav"]
    assert pl.custom_cover.endswith("Cover.jpg") and pl.cover_path == pl.custom_cover
    # the same folder again: a second playlist with its own name, nothing lost
    again = window.playlists_from_dropped([str(album)])
    assert again[0].name == "Night Drive 2"


def test_a_copied_folder_takes_over_songs_whose_files_are_gone(window, tmp_path):
    """Windows report: songs imported from folder A, A deleted, the same songs added from a copy (folder B): the
    playlist kept asking to download them. Now the missing entries play from the copies."""
    import shutil
    a = tmp_path / "A"
    a.mkdir()
    make_wav(a / "song.wav", 0.3)
    pl = window.create_playlist("Mine", [])
    window.add_files_to_playlist(pl, [str(a)])
    from core.models import Song
    first = pl.songs[0]
    first.title, first.artist = "VB Anthem", "The Chats"
    b = tmp_path / "B"
    shutil.copytree(a, b)
    shutil.rmtree(a)
    assert not first.exists
    import core.models as m
    orig = m.Song.__init__

    def tagged(self, path, *args, **kw):
        orig(self, path, *args, **kw)
        self.title, self.artist = "VB Anthem", "The Chats"
    m.Song.__init__ = tagged
    try:
        window.add_files_to_playlist(pl, [str(b)])
    finally:
        m.Song.__init__ = orig
    assert len(pl.songs) == 1 and pl.songs[0].exists and str(b) in pl.songs[0].file_path


def test_green_tick_for_songs_in_your_playlists_and_plus_saves_to_liked(window, qapp, monkeypatch):
    """Spotify's green tick next to a song's length when it's in Liked Songs or any playlist; clicking the + on an
    unsaved song saves it to Liked Songs."""
    from ui import track_table as tt
    a, b = window.songs[0], window.songs[1]
    window.create_playlist("Road", [a])
    assert tt.is_saved(a) and not tt.is_saved(b)
    t = window.library_table
    t.set_songs(window.songs)
    window.show()
    window.show_library()
    qapp.processEvents()
    row_b = next(r for r in range(t.rowCount()) if t.song_at(r) is b)
    cell = t.visualRect(t.model().index(row_b, t.columnCount() - 1))
    mark = tt._save_mark_rect(cell).center().toPoint()
    from PyQt6.QtTest import QTest
    QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, pos=mark)
    assert window.is_liked(b) and tt.is_saved(b)
    QTest.mouseClick(t.viewport(), Qt.MouseButton.LeftButton, pos=mark)   # the tick: "Add to playlist" pop-up
    picker = window._save_picker
    rows = {r.playlist.name: r for r in picker.rows}
    assert rows["Liked Songs"].tick.isChecked() and not rows["Road"].tick.isChecked()
    picker.find.setText("roa")
    assert rows["Road"].isVisible() and not rows["Liked Songs"].isVisible()
    rows["Road"].tick.toggle()
    rows["Liked Songs"].tick.toggle()
    road = next(p for p in window.playlists if p.name == "Road")
    assert b not in road.songs                                    # nothing changes until Done
    picker._done()
    assert b in road.songs and not window.is_liked(b) and tt.is_saved(b)


def test_right_panel_can_be_dragged_wider_and_remembers_it(window, qapp):
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import QPoint
    window.show()
    window.set_right_panel("nowplaying")
    qapp.processEvents()
    h = window.right_handle
    assert h.isVisible() and h.parentWidget() is window.right_panel.parentWidget()
    start = window.right_panel.width()
    QTest.mousePress(h, Qt.MouseButton.LeftButton, pos=QPoint(2, 50))
    QTest.mouseMove(h, QPoint(-98, 50))
    QTest.mouseRelease(h, Qt.MouseButton.LeftButton, pos=QPoint(-98, 50))
    assert window.right_panel.width() == start + 100 == window.user_data.right_panel_width
    window.set_right_panel("")
    qapp.processEvents()
    assert not h.isVisible()


def test_playlist_description_is_edited_shown_and_kept(window, tmp_path):
    pl = window.create_playlist("Road", [window.songs[0]])
    window._auto_answer_dialogs = {"name": "Road Trip", "description": "x" * 400}
    window.edit_playlist_details(pl)
    window._auto_answer_dialogs = None
    assert pl.name == "Road Trip" and pl.description == "x" * 300          # 300 characters at most
    window.show_playlist(pl)
    assert window.pl_desc.isVisibleTo(window) and window.pl_desc.text()
    window.save_now()
    from core.storage import Storage
    stored = Storage(window.storage.data_dir).load()
    assert next(p for p in stored.playlists if p.name == "Road Trip").description == "x" * 300


def test_mouse_wheel_glides_instead_of_jumping(window, qapp):
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent
    from ui import smooth_scroll
    from ui.track_table import TrackTable
    window.show()
    t = TrackTable(parent=window.center_panel)                  # inside the window (not its own window)
    t.set_songs(window.songs * 40)
    t.setGeometry(0, 0, 600, 300)
    t.show()
    qapp.processEvents()
    bar = t.verticalScrollBar()
    assert bar.maximum() > 300
    ev = QWheelEvent(QPointF(50, 50), QPointF(t.viewport().mapToGlobal(QPoint(50, 50))), QPoint(0, 0), QPoint(0, -120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication = __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication
    QApplication.sendEvent(t.viewport(), ev)
    qapp.processEvents()
    assert bar.value() < smooth_scroll.STEP                     # it hasn't jumped there at once...
    assert wait_until(qapp, lambda: bar.value() == smooth_scroll.STEP, 2)   # ...it glides there
    t.hide()
    t.deleteLater()


def test_locate_songs_in_a_folder_fills_an_imported_playlist(window, qapp, tmp_path):
    """Alternative/Indie Chill: songs imported from Spotify that you already have in a folder play from there
    (Playlist ••• → Locate songs in a folder…) instead of being downloaded again."""
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    from mutagen.wave import WAVE
    folder = tmp_path / "Indie"
    folder.mkdir()
    make_wav(folder / "x.wav", 0.3)
    f = WAVE(str(folder / "x.wav"))
    f.add_tags()
    from mutagen.id3 import TIT2, TPE1
    f.tags.add(TIT2(encoding=3, text="Breathe the Fire"))
    f.tags.add(TPE1(encoding=3, text="The Soft Moon"))
    f.save()
    pl = window.create_playlist("Alt", [RemoteSong(OnlineTrack("Breathe the Fire", "The Soft Moon", preview_url="https://x/p")),
                                        RemoteSong(OnlineTrack("Other", "Someone", preview_url="https://x/q"))])
    window.locate_playlist_songs(pl, str(folder))
    assert wait_until(qapp, lambda: not getattr(pl.songs[0], "is_remote", False), 10)
    assert pl.songs[0].exists and getattr(pl.songs[1], "is_remote", False)
    assert "Found 1 song" in window.status_label.text()


def test_help_faq_opens_and_searches(window):
    from ui import help_faq
    window._auto_answer_dialogs = True
    d = help_faq.show(window)
    window._auto_answer_dialogs = None
    d.faq_filter("vpn")
    shown = [box for head, group in d.faq_items for box, hay in group if not box.isHidden()]
    assert len(shown) == 1
    d.deleteLater()


def test_a_video_floats_inside_sevbify_when_you_leave_its_page(window, qapp):
    """Like the phone app: leaving a playing video podcast keeps it going in a small window inside Sevbify
    (drag, resize, expand, close); going back to the video page makes it full size again."""
    from ui import video_page
    if not video_page.HAVE_VIDEO:
        return
    window.show()
    window._video_song = window.songs[0]                       # as if an episode's video were playing
    window.stack.setCurrentWidget(window.video_page)
    window.show_home()
    qapp.processEvents()
    ov = window.video_page.overlay
    assert ov is not None and ov.isVisible() and window._video_song is not None
    assert ov.parent() is window.center_panel
    ov.set_progress(0.5)
    assert ov.progress.width() == ov.width() // 2
    window.stack.setCurrentWidget(window.video_page)
    qapp.processEvents()
    assert not ov.isVisible()
    window.video_page.stop()
    window._video_song = None
