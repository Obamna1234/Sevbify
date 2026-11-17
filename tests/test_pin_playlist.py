"""Pin playlist (like Spotify's): a pinned playlist stays at the top of Your Library, and is remembered."""
from core.storage import Storage


def test_pin_keeps_a_playlist_on_top_and_is_saved(window):
    a = window.create_playlist("Aaa", [window.songs[0]])
    z = window.create_playlist("Zzz", [window.songs[0]])
    window.library_panel.sort = "alpha"
    window._refresh_library_panel()
    titles = lambda: [e["title"] for e in window.library_panel.entries() if e["kind"] == "playlist"]
    assert titles().index("Aaa") < titles().index("Zzz")
    window.pin_playlist(z)
    assert titles()[0] == "Zzz" and titles().count("Zzz") == 1
    assert next(e for e in window.library_panel.entries() if e["title"] == "Zzz")["subtitle"].startswith("📌")
    window.save_now()
    again = Storage(window.storage.data_dir).load()
    assert [p.name for p in again.playlists if p.pinned] == ["Zzz"]
    window.pin_playlist(z, False)
    assert titles().index("Aaa") < titles().index("Zzz")
