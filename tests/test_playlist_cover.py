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


def test_deezer_and_jamendo_links_are_recognised():
    from core.importers import parse_link, origin_of
    assert parse_link("https://www.deezer.com/en/playlist/1479458365") == ("deezer", "playlist", "1479458365")
    assert parse_link("https://deezer.com/album/302127") == ("deezer", "album", "302127")
    assert parse_link("https://www.jamendo.com/playlist/500608900/chill") == ("jamendo", "playlist", "500608900")
    assert parse_link("https://www.jamendo.com/album/145774/x") == ("jamendo", "album", "145774")
    assert origin_of("https://www.deezer.com/en/playlist/1") == "deezer"


def test_import_deezer_playlist_pages_through_all_songs():
    from core.importers import fetch_from_link

    def row(i):
        return {"id": i, "title": f"Song {i}", "duration": 200, "artist": {"name": "Band"},
                "album": {"title": "LP", "cover_xl": "https://img/lp.jpg"}}

    class Net:
        def get_json(self, url, params=None, ttl=0):
            if url.endswith("/playlist/7"):
                return {"title": "Road trip", "picture_xl": "https://img/p.jpg", "creator": {"name": "Sev"}}
            start = (params or {}).get("index", 0)
            rows = [row(i) for i in range(start, min(start + 100, 150))]
            return {"data": rows, **({"next": "more"} if start + 100 < 150 else {})}
    out = fetch_from_link(Net(), "https://www.deezer.com/playlist/7")
    assert out["name"] == "Road trip" and len(out["tracks"]) == 150 and out["tracks"][0].title == "Song 0"


def test_jamendo_import_asks_for_the_client_id():
    import pytest
    from core.importers import fetch_from_link, ImportError_
    with pytest.raises(ImportError_, match="client ID"):
        fetch_from_link(object(), "https://www.jamendo.com/playlist/5/x")


def test_origin_colours_follow_the_users_scheme():
    from ui.library_panel import origin_colour
    assert origin_colour("") == "#8a8a8a" and origin_colour("spotify") == "#1ed760"
    assert origin_colour("apple") == "#ffffff" and origin_colour("file") == "#509bf5"
    assert origin_colour("deezer") == "#a238ff" and origin_colour("jamendo") == "#ff8a1f"


def test_sponsorblock_uses_a_hash_prefix_and_picks_the_right_video():
    import hashlib
    from core import sponsorblock
    asked = {}

    class Net:
        def get_json(self, url, params=None, ttl=0):
            asked["url"] = url
            return [{"videoID": "other000000", "segments": [{"segment": [1, 50], "actionType": "skip"}]},
                    {"videoID": "dQw4w9WgXcQ", "segments": [{"segment": [30.5, 90.0], "category": "sponsor",
                                                             "actionType": "skip"},
                                                            {"segment": [5, 5.2], "actionType": "skip"}]}]
    segs = sponsorblock.segments(Net(), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert segs == [[30500, 90000, "sponsor"]]
    assert asked["url"].endswith(hashlib.sha256(b"dQw4w9WgXcQ").hexdigest()[:4])
    assert "dQw4w9WgXcQ" not in asked["url"]              # the video itself is never named
    assert sponsorblock.segments(Net(), "not a youtube link") == []


def test_artist_releases_are_grouped_and_newest_first():
    from core.online.providers import Deezer

    class Net:
        def get_json(self, url, params=None, ttl=0):
            return {"data": [{"title": "Old LP", "record_type": "album", "release_date": "2001-01-01"},
                             {"title": "New LP", "record_type": "album", "release_date": "2024-01-01"},
                             {"title": "Hit", "record_type": "single", "release_date": "2023-05-05"},
                             {"title": "Best Of", "record_type": "compile", "release_date": "2010-01-01"}]}
    r = Deezer(Net()).artist_albums(1)
    assert [a["title"] for a in r["albums"]] == ["New LP", "Old LP"]
    assert [a["title"] for a in r["singles"]] == ["Hit"] and [a["title"] for a in r["compilations"]] == ["Best Of"]


def test_podcast_category_chart_is_read():
    from core import podcasts

    class Net:
        def get_json(self, url, params=None, ttl=0):
            assert "genre=1303" in url
            return {"feed": {"entry": [{"im:name": {"label": "Funny Show"}, "im:artist": {"label": "Host"},
                                        "id": {"attributes": {"im:id": "123"}},
                                        "im:image": [{"label": "https://a/55x55bb.png"}, {"label": "https://a/170x170bb.png"}],
                                        "category": {"attributes": {"label": "Comedy"}}}]}}
    shows = podcasts.top_in_category(Net(), 1303)
    assert shows[0].title == "Funny Show" and shows[0].apple_id == "123" and shows[0].image_url.endswith("600x600bb.png")
