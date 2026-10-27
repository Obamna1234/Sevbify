"""Library, search, playlist and persistence tests. Run: python -m pytest tests -v"""
import json
import os

from conftest import make_wav, wait_until


# ---------------------------------------------------------------- persistence
def test_first_run_creates_sample_playlists_and_save_file(window, data_dir):
    assert [p.name for p in window.playlists] == ["Favorites", "Chill Hits", "Workout Mix"]
    saved = json.loads((data_dir / "library.json").read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert [p["name"] for p in saved["playlists"]] == ["Favorites", "Chill Hits", "Workout Mix"]


def test_playlists_and_volume_survive_restart(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    pl = w.create_playlist("Road Trip", [w.songs[2], w.songs[0]])
    w.delete_playlist(next(p for p in w.playlists if p.name == "Favorites"))
    w.volume_slider.setValue(42)
    w.close()  # flushes the pending volume save

    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    names = [p.name for p in w2.playlists]
    assert "Road Trip" in names and "Favorites" not in names
    road = next(p for p in w2.playlists if p.name == "Road Trip")
    assert [s.title for s in road.songs] == ["03 - third", "01 - first"]
    assert road.songs[0] is w2.songs[2]  # linked to the library's Song object
    assert w2.user_data.volume == 42 and w2.volume_slider.value() == 42


def test_missing_track_kept_in_playlist(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w.create_playlist("Keep", [w.songs[0], w.songs[1]])
    w.close()
    os.remove(audio_dir / "02 - second.wav")

    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    keep = next(p for p in w2.playlists if p.name == "Keep")
    assert len(keep.songs) == 2
    assert keep.songs[0].exists and not keep.songs[1].exists
    w2.show_playlist(keep)
    assert "1 missing" in w2.pl_meta.text()
    assert "(file missing)" in w2.pl_table.item(1, 1).text()


def test_corrupt_save_file_is_kept_and_defaults_loaded(open_window, audio_dir, data_dir):
    (data_dir / "library.json").write_text("{ this is not json", encoding="utf-8")
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    backups = list(data_dir.glob("library.corrupt-*.json"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "{ this is not json"
    assert "could not be read" in w.status_label.text()
    assert w.playlists == []  # not treated as a first run, so no samples


def test_project_files_saved_with_relative_paths(tmp_path):
    from core.paths import PROJECT_ROOT, to_stored_path, from_stored_path
    inside = os.path.join(PROJECT_ROOT, "audio", "x.mp3")
    assert to_stored_path(inside) == "audio/x.mp3"
    assert os.path.normcase(from_stored_path("audio/x.mp3")) == os.path.normcase(inside)
    outside = str(tmp_path / "y.mp3")
    assert to_stored_path(outside) == os.path.abspath(outside)


# ------------------------------------------------------------------ playlists
def test_duplicate_playlist_names_rejected(window):
    assert window.create_playlist("Mix") is not None
    assert window.create_playlist("mix") is None
    assert "already have" in window.status_label.text()
    other = window.create_playlist("Other")
    assert not window.rename_playlist(other, "MIX")
    assert window.rename_playlist(other, "Renamed") and other.name == "Renamed"


def test_add_remove_and_reorder(window):
    pl = window.create_playlist("Edit me")
    assert window.add_to_playlist(pl, [window.songs[0], window.songs[1]]) == 2
    assert window.add_to_playlist(pl, [window.songs[0]]) == 0  # no duplicates
    window.move_in_playlist(pl, 0, 1)
    assert [s.title for s in pl.songs] == ["02 - second", "01 - first"]
    window.remove_from_playlist(pl, 0)
    assert [s.title for s in pl.songs] == ["01 - first"]


def test_playlist_page_and_menu(window, qapp):
    pl = window.create_playlist("Page", [window.songs[0], window.songs[1]])
    window.show_playlist(pl)
    assert window.stack.currentWidget() is window.playlist_page
    assert window.pl_title.text() == "Page"
    assert window.pl_table.rowCount() == 2
    menu = window.build_song_menu(pl.songs[0], queue=pl.songs, playlist=pl, row=0)
    labels = [a.text() for a in menu.actions()]
    assert any("Remove from this playlist" in t for t in labels)
    assert not next(a for a in menu.actions() if "Move up" in a.text()).isEnabled()
    window.delete_playlist(pl)
    assert window.stack.currentWidget() is window.playlists_page


# --------------------------------------------------------------------- search
def test_search_matches_title_artist_album_case_insensitive(window):
    window.songs[1].artist = "Molchat Doma"
    assert window.search("MOLCHAT") == [window.songs[1]]
    assert window.search("doma second") == [window.songs[1]]
    assert window.search("nothing like this") == []
    window.search_input.setText("first")
    assert window.search_table.rowCount() == 1
    assert "1 song" in window.search_summary.text()
    window.search_input.setText("zzz")
    assert "No results" in window.search_summary.text()


def test_search_queue_is_the_results(window):
    window.search_input.setText("first")
    window.search_table.play_requested.emit(window.songs[0], window.search_table.songs_in_view())
    assert window.queue == [window.songs[0]]


# --------------------------------------------------------------------- folders
def test_add_and_remove_music_folder(window, qapp, tmp_path):
    extra = tmp_path / "extra" / "nested"
    extra.mkdir(parents=True)
    make_wav(extra / "04 - fourth.wav", 0.5)
    assert window.add_music_folder(str(tmp_path / "extra"))
    assert wait_until(qapp, lambda: len(window.songs) == 4)  # nested folders scanned
    assert not window.add_music_folder(str(tmp_path / "extra"))  # already added
    window.remove_music_folder(str(tmp_path / "extra"))
    assert wait_until(qapp, lambda: len(window.songs) == 3)


def test_rescan_keeps_playlists_linked(window, qapp, audio_dir):
    pl = window.create_playlist("Linked", [window.songs[0]])
    make_wav(audio_dir / "00 - new.wav", 0.5)
    window.rescan_library()
    assert wait_until(qapp, lambda: len(window.songs) == 4)
    assert pl.songs[0] is next(s for s in window.songs if s.title == "01 - first")
    assert window.library_table.rowCount() == 4


def test_playlists_migrate_from_old_app_name(tmp_path):
    from core.storage import Storage, UserData, StoredPlaylist, migrate_legacy_data
    old_dir = tmp_path / "Custom Spotify Replica"
    new_dir = tmp_path / "Aurvo"
    data = UserData(volume=33, playlists=[StoredPlaylist("Old faves", ["/music/a.mp3"])])
    Storage(str(old_dir)).save(data)
    assert migrate_legacy_data(str(new_dir))
    loaded = Storage(str(new_dir)).load()
    assert loaded.volume == 33 and loaded.playlists[0].name == "Old faves"
    assert (old_dir / "library.json").exists()       # old copy kept as a backup
    assert not migrate_legacy_data(str(new_dir))      # only ever runs once
