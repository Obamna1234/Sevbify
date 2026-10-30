"""Spotify-style playlist pictures, the optional origin border, Spotify-style totals and radio skip feedback."""
from types import SimpleNamespace as NS

from core.playlist_cover import choose


def song(album, artist="A", cover=None):
    return NS(album=album, artist=artist, album_cover_path=cover or f"/c/{album}.jpg")


def test_first_four_different_albums_in_order():
    songs = [song("x"), song("x"), song("y"), song("z"), song("y"), song("w"), song("v")]
    assert choose(songs) == ["/c/x.jpg", "/c/y.jpg", "/c/z.jpg", "/c/w.jpg"]


def test_fewer_than_four_albums_uses_the_first_songs_cover():
    assert choose([song("x"), song("y"), song("x")]) == ["/c/x.jpg"]
    assert choose([]) == []


def test_same_album_name_by_different_artists_counts_twice_and_web_covers_count():
    remote = NS(album="", artist="B", album_cover_path="/x/placeholder.png",
                track=NS(cover_url="https://img/b.jpg"))
    songs = [song("Greatest Hits", "A"), song("Greatest Hits", "B", "/c/gh-b.jpg"), remote, song("q")]
    assert choose(songs) == ["/c/Greatest Hits.jpg", "/c/gh-b.jpg", "https://img/b.jpg", "/c/q.jpg"]


def test_format_total_like_spotify_desktop():
    from core.models import format_total
    assert format_total((2 * 3600 + 45 * 60) * 1000) == "about 2 hr 45 min"
    assert format_total((23 * 60 + 5) * 1000) == "23 min 5 sec"


def test_origin_is_saved_and_border_setting_defaults_off(open_window, audio_dir, data_dir):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    assert w.user_data.show_playlist_origin is False and w.library_panel.show_origin is False
    pl = w.create_playlist("Mine", [w.songs[0]])
    pl.origin = "file"
    w.save_now()
    w.apply_settings({"show_playlist_origin": True})
    assert w.library_panel.show_origin
    w.close()
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    assert next(p for p in w2.playlists if p.name == "Mine").origin == "file"
    assert w2.user_data.show_playlist_origin and w2.library_panel.show_origin


def test_origin_of_links():
    from core.importers import origin_of
    assert origin_of("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M") == "spotify"
    assert origin_of("https://music.apple.com/us/playlist/x/pl.123") == "apple"


def test_radio_skip_drops_that_artists_upcoming_songs_only_in_memory():
    from core.play_queue import PlayQueue
    songs = [NS(artist=a, title=str(i)) for i, a in enumerate("SXAXBCXDEFG")]
    q = PlayQueue()
    q.set_context(songs, songs[1], "Seed Radio")          # playing X
    assert q.drop_upcoming_by_artist("x") == 2
    assert [s.artist for s in q.items] == list("SXABCDEFG")
    assert q.drop_upcoming_by_artist("nobody") == 0
    short = [NS(artist=a, title=str(i)) for i, a in enumerate("SXXAB")]
    q.set_context(short, short[1], "Seed Radio")
    assert q.drop_upcoming_by_artist("x") == 0               # would leave too few songs: keep going as is
