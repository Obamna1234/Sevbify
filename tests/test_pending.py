"""'Not downloaded yet' playlist slots, folder watching, Saved for later, export."""
import os

from conftest import make_wav, wait_until
from online_fixtures import FakeWeb


def remote(title, artist, duration_ms=0, genre=""):
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    return RemoteSong(OnlineTrack(title, artist, duration_ms=duration_ms, genre=genre, source="deezer",
                                  preview_url="https://cdn/x.mp3"))


def test_pending_slot_keeps_position_and_fills_in_when_file_appears(open_window, audio_dir, data_dir, qapp):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w.FRESH_FILE_SECONDS = 0
    pl = w.create_playlist("Mix", [w.songs[0], w.songs[1], w.songs[2]])
    w.add_to_playlist(pl, [remote("Night City", "Vogel")])
    w.move_in_playlist(pl, 3, -1)                                  # put it at #3
    assert [getattr(s, "is_remote", False) for s in pl.songs] == [False, False, True, False]
    w.show_playlist(pl)
    assert "1 not downloaded yet" in w.pl_meta.text()
    assert w.pl_table.item(2, 1).text().endswith("⬇")
    w.close()

    # Restart: the placeholder survives in the same position.
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    w2.FRESH_FILE_SECONDS = 0
    pl2 = next(p for p in w2.playlists if p.name == "Mix")
    assert getattr(pl2.songs[2], "is_remote", False) and pl2.songs[2].title == "Night City"

    # The song arrives in the music folder (untagged "Artist - Title" file name).
    make_wav(audio_dir / "Vogel - Night City.wav", 0.5)
    w2.rescan_library()
    assert wait_until(qapp, lambda: not getattr(pl2.songs[2], "is_remote", False))
    assert pl2.songs[2].file_path.endswith("Vogel - Night City.wav")
    assert [s.title for s in pl2.songs].index(pl2.songs[2].title) == 2     # still #3
    assert "Now in your library" in w2.status_label.text()


def test_brand_new_file_waits_until_finished_writing(window, audio_dir, qapp):
    pl = window.create_playlist("Wait", [remote("Fresh", "Artist")])
    window.FRESH_FILE_SECONDS = 60
    make_wav(audio_dir / "Artist - Fresh.wav", 0.5)
    window.rescan_library()
    assert wait_until(qapp, lambda: len(window.songs) == 4)
    assert getattr(pl.songs[0], "is_remote", False)            # not filled yet (file too new)


def test_music_folder_is_watched(window, audio_dir, qapp):
    make_wav(audio_dir / "04 - dropped in.wav", 0.5)
    assert wait_until(qapp, lambda: len(window.songs) == 4, timeout=12)


def test_save_for_later_by_genre_and_export(window, qapp, tmp_path):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: True, opener=FakeWeb())
    window.online = OnlineMusic(window.net)
    rock = remote("Smells Like Teen Spirit", "Nirvana", genre="Rock")
    rap = remote("Lose Yourself", "Eminem", genre="Rap/Hip Hop")
    window.save_for_later(rock)
    window.save_for_later(rap)
    window.save_for_later(rock)                                 # duplicate ignored
    assert wait_until(qapp, lambda: set(window.user_data.save_for_later) == {"Rock", "Rap/Hip Hop"})
    assert len(window.user_data.save_for_later["Rock"]) == 1
    window.show_saved()
    assert window.stack.currentWidget() is window.saved_page

    txt = window.write_song_list(window.saved_songs("Rock"), str(tmp_path / "rock.txt"))
    assert open(txt, encoding="utf-8").read() == "Nirvana - Smells Like Teen Spirit\n"
    m3u = window.write_song_list([window.songs[0], rap], str(tmp_path / "x.m3u"), m3u=True)
    content = open(m3u, encoding="utf-8").read().splitlines()
    assert content[0] == "#EXTM3U" and content[2] == window.songs[0].file_path
    assert content[4] == "# not downloaded yet: Eminem - Lose Yourself"

    window.remove_saved("Rock", 0)
    assert "Rock" not in window.user_data.save_for_later


def test_saved_song_leaves_list_when_you_get_it(window, audio_dir, qapp, tmp_path):
    window.FRESH_FILE_SECONDS = 0
    window.user_data.save_for_later = {"Electro": [remote("Turbo Killer", "Carpenter Brut").track.to_dict()]}
    make_wav(audio_dir / "Carpenter Brut - Turbo Killer.wav", 0.5)
    window.rescan_library()
    assert wait_until(qapp, lambda: "Electro" not in window.user_data.save_for_later)


def test_save_for_later_menu_only_for_online_songs(window):
    labels = [a.text() for a in window.build_song_menu(window.songs[0]).actions()]
    assert not any("Save for later" in t for t in labels)
    labels = [a.text() for a in window.build_song_menu(remote("A", "B")).actions()]
    assert any("Save for later" in t for t in labels)
