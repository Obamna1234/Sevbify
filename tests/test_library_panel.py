"""Your Library like Spotify: chips, folders, sorting, views, albums and artists, collapse and expand."""
import time

from conftest import wait_until


def kinds(window):
    return [(e["kind"], e["title"]) for e in window.library_panel.entries()]


def tag(window):
    """Give the test songs real tags: two albums by two artists."""
    a, b, c = window.songs
    a.artist, a.album, a.title = "Perturbator", "Dangerous Days", "Future Club"
    b.artist, b.album, b.title = "Perturbator feat. Someone", "Dangerous Days", "Humans Are Such Easy Prey"
    c.artist, c.album, c.title = "Carpenter Brut", "Trilogy", "Turbo Killer"
    window._collections_for = None
    window._refresh_library_panel()


def test_albums_and_artists_chips_and_pages(window, qapp):
    tag(window)
    lp = window.library_panel
    lp.set_chip("albums")
    assert [t for k, t in kinds(window)] == ["Dangerous Days", "Trilogy"] or \
        sorted(t for k, t in kinds(window)) == ["Dangerous Days", "Trilogy"]
    lp.set_chip("artists")
    assert sorted(t for k, t in kinds(window)) == ["Carpenter Brut", "Perturbator"]   # feat. goes under the main artist
    perturbator = next(e["obj"] for e in lp.entries() if e["title"] == "Perturbator")
    window.show_artist(perturbator)
    assert window.stack.currentWidget() is window.collection_page
    assert window.collection_table.rowCount() == 2
    album = window.find_album("dangerous days\x1fperturbator")
    window.show_album(album)
    assert window.collection_table.rowCount() == 2 and window._collection_name == "Dangerous Days"
    window.show_home()
    window.go_back()
    assert window.stack.currentWidget() is window.collection_page
    # Go to artist / Go to album from a song's menu open the local pages
    window.go_to_artist("Carpenter Brut")
    assert window._collection_name == "Carpenter Brut"
    window.go_to_album(window.songs[0])          # offline-style: your own copy of the album (no network in tests)
    from conftest import wait_until
    assert wait_until(window.app if hasattr(window, "app") else __import__("PyQt6.QtWidgets").QtWidgets.QApplication.instance(),
                      lambda: window._collection_name == "Dangerous Days")


def test_folders_create_move_rename_delete_and_survive_restart(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    rock = w.create_playlist("Rock", [w.songs[0]])
    chill = w.create_playlist("Chill", [])
    folder = w.create_folder()
    assert folder == "New Folder" and w.create_folder() == "New Folder 2"
    w.move_to_folder(rock, "New Folder")
    titles = kinds(w)
    assert ("folder", "New Folder") in titles and ("playlist", "Rock") in titles
    assert titles.index(("playlist", "Rock")) == titles.index(("folder", "New Folder")) + 1   # inside the open folder
    w.library_panel.toggle_folder("New Folder")                           # close it: Rock hidden
    assert ("playlist", "Rock") not in kinds(w) and ("playlist", "Chill") in kinds(w)
    assert w.rename_folder("New Folder", "Old stuff") and rock.folder == "Old stuff"
    w.close()

    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    assert w2.user_data.folders == ["Old stuff", "New Folder 2"]
    rock2 = next(p for p in w2.playlists if p.name == "Rock")
    assert rock2.folder == "Old stuff"
    w2.delete_folder("Old stuff")
    assert rock2.folder == "" and ("playlist", "Rock") in kinds(w2)


def test_sorting_recents_added_alphabetical(window):
    lp = window.library_panel
    b = window.create_playlist("Banana", [])
    a = window.create_playlist("Apple", [])
    c = window.create_playlist("Cherry", [])
    b.created, a.created, c.created = 100, 200, 300
    b.last_played, a.last_played, c.last_played = 900, 0, 500
    names = lambda: [t for k, t in kinds(window) if k == "playlist"]
    lp.set_view_options(sort="alpha")
    assert names() == ["Apple", "Banana", "Cherry"]
    lp.set_view_options(sort="added")
    assert names() == ["Cherry", "Apple", "Banana"]
    lp.set_view_options(sort="recents")
    assert names() == ["Banana", "Cherry", "Apple"]
    assert kinds(window)[0] == ("songs", "Your Songs")                     # pinned at the top, like Liked Songs
    window.show_playlist(a)                                                 # opening counts as recent
    assert names()[0] == "Apple"
    assert window.user_data.library_sort == "recents"


def test_views_collapse_expand_and_downloaded_chip(window, qapp):
    from ui.library_panel import LibraryRow, COLLAPSED_WIDTH
    lp = window.library_panel
    full = window.create_playlist("All here", [window.songs[0], window.songs[1]])
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    window.create_playlist("Half", [window.songs[0], RemoteSong(OnlineTrack("Later", "Band"))])
    lp.set_chip("downloaded")
    assert [t for k, t in kinds(window) if k == "playlist"] == ["All here"]
    lp.set_chip(None)
    for view in ("compact", "grid", "list"):
        lp.set_view_options(view=view)
        qapp.processEvents()
        rows = lp.findChildren(LibraryRow)
        assert rows and all(r.mode == view for r in rows if r.isVisible() or True)
    assert window.user_data.library_view == "list"
    lp.set_collapsed(True)
    qapp.processEvents()
    assert lp.maximumWidth() == COLLAPSED_WIDTH and window.user_data.library_collapsed
    assert all(r.mode == "collapsed" for r in lp.findChildren(LibraryRow))
    lp.set_collapsed(False)
    lp.set_expanded(True)
    assert not window.center_panel.isVisibleTo(window) and lp.expanded
    lp.open_playlist.emit(full)                                             # opening something goes back
    assert lp.expanded is False and window.center_panel.isVisibleTo(window)
    assert window.stack.currentWidget() is window.playlist_page


def test_create_menu_playlist_starts_empty_and_opens(window):
    pl = window.new_playlist()
    assert pl.name == "My Playlist #1" and pl.songs == []
    assert window.stack.currentWidget() is window.playlist_page and window.open_playlist is pl
    assert window.new_playlist().name == "My Playlist #2"


def test_search_in_your_library_finds_albums_and_artists(window):
    tag(window)
    lp = window.library_panel
    window.create_playlist("Synthwave", [])
    lp.show_filter()
    lp.filter_edit.setText("pert")
    assert ("artist", "Perturbator") in kinds(window)
    lp.filter_edit.setText("synth")
    assert kinds(window) == [("playlist", "Synthwave")]


def test_go_to_album_opens_the_whole_album_online(window, qapp, monkeypatch):
    from conftest import wait_until
    from core.online.models import OnlineTrack
    window.set_online(True) if hasattr(window, "set_online") else None
    album = {"id": 9, "title": "Dangerous Days", "cover_xl": ""}
    monkeypatch.setattr(window.online.deezer, "find_album", lambda artist, name: album)
    monkeypatch.setattr(window.online.deezer, "album_tracks", lambda a: [
        OnlineTrack("Intro", "Perturbator", album="Dangerous Days", preview_url="https://p/1.mp3"),
        OnlineTrack("Future Club", "Perturbator", album="Dangerous Days", preview_url="https://p/2.mp3")])
    from core.online.remote_song import RemoteSong
    calls = []
    monkeypatch.setattr(window, "show_status", lambda *a, **k: calls.append(a))
    window.go_to_album(RemoteSong(OnlineTrack("Future Club", "Perturbator", album="Dangerous Days")))
    assert wait_until(qapp, lambda: window._collection_name == "Dangerous Days" and window.collection_table.rowCount() == 2), \
        (calls, window._collection_name, window.collection_table.rowCount(), window.online_enabled)
