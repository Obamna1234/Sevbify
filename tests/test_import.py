"""Importing playlists: Spotify links (public embed page), Exportify CSV, .txt in any encoding, .m3u.
No internet: the Spotify page is a small page made for the test."""
import json
import os

from conftest import make_wav, wait_until
from online_fixtures import FakeWeb, ROUTES


def embed_page(name="Road Trip", tracks=None, cover="https://i.scdn.co/image/cover1"):
    tracks = tracks or [
        {"entityType": "track", "title": "Highway Run", "subtitle": "Biodrive", "duration": 327000,
         "uri": "spotify:track:aaa", "isExplicit": False},
        {"entityType": "track", "title": "first", "subtitle": "01", "duration": 1000, "uri": "spotify:track:bbb"},
        {"entityType": "episode", "title": "Some podcast", "subtitle": "Show", "uri": "spotify:episode:x"},
        {"entityType": "track", "title": "Those in My Way", "subtitle": "Straplocked, Occams Laser",
         "duration": 282000, "uri": "spotify:track:ccc", "isExplicit": True},
    ]
    data = {"props": {"pageProps": {"state": {"data": {"entity": {
        "type": "playlist", "name": name, "subtitle": "CheemsBalls",
        "coverArt": {"sources": [{"url": cover, "width": None, "height": None}]}, "trackList": tracks}}}}}}
    return ('<html><head></head><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(data) + "</script></body></html>")


def test_links_are_recognised():
    from core.importers import parse_link
    assert parse_link("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc") == \
        ("spotify", "playlist", "37i9dQZF1DXcBWIGoYBM5M")
    assert parse_link("https://open.spotify.com/intl-de/album/4aawyAB9vmqN3uQ7FjRGTy") == \
        ("spotify", "album", "4aawyAB9vmqN3uQ7FjRGTy")
    assert parse_link("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")[1:] == ("playlist", "37i9dQZF1DXcBWIGoYBM5M")
    assert parse_link("https://music.apple.com/us/playlist/x/pl.u-123")[0] == "apple"
    assert parse_link("hello") is None


def test_spotify_embed_page_is_read_in_order():
    from core.importers import parse_spotify_embed
    res = parse_spotify_embed(embed_page())
    assert res["name"] == "Road Trip" and res["cover_url"] == "https://i.scdn.co/image/cover1"
    assert [(t.artist, t.title) for t in res["tracks"]] == [
        ("Biodrive", "Highway Run"), ("01", "first"), ("Straplocked, Occams Laser", "Those in My Way")]
    assert res["tracks"][0].duration_ms == 327000 and res["tracks"][2].explicit
    assert res["tracks"][0].page_url == "https://open.spotify.com/track/aaa"


def test_text_files_in_any_encoding_and_dash_style(tmp_path):
    from core.importers import read_playlist_file, split_line
    assert split_line("邓紫棋-光年之外") == ("邓紫棋", "光年之外")
    assert split_line("陈奕迅 － 十年") == ("陈奕迅", "十年")
    assert split_line("Jay-Z - Empire State of Mind") == ("Jay-Z", "Empire State of Mind")
    assert split_line("Blink-182") == ("", "Blink-182") or split_line("Blink-182")[1]
    for enc in ("utf-8", "gbk", "utf-16"):
        p = tmp_path / f"{enc}.txt"
        p.write_text("周杰伦 - 晴天\n邓紫棋-光年之外\n", encoding=enc)
        items = read_playlist_file(str(p))["items"]
        assert [(t.artist, t.title) for _k, t in items] == [("周杰伦", "晴天"), ("邓紫棋", "光年之外")], enc


def test_exportify_csv(tmp_path):
    from core.importers import read_playlist_file
    p = tmp_path / "My Mix.csv"
    p.write_text('Track URI,Track Name,Artist Name(s),Album Name,Duration (ms)\n'
                 'spotify:track:1,Netrunner,"Lazerpunk, Donbor",Synthicate,244000\n'
                 'spotify:track:2,Enter Sandman,Metallica,Metallica,331000\n', encoding="utf-8")
    res = read_playlist_file(str(p))
    assert res["name"] == "My Mix"
    assert [t.title for _k, t in res["items"]] == ["Netrunner", "Enter Sandman"]
    assert res["items"][1][1].artist == "Metallica"


def test_import_link_makes_a_playlist_in_order_with_cover_and_local_matches(window, qapp, audio_dir, tmp_path):
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    routes = dict(ROUTES)
    routes["open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M"] = embed_page()
    routes["i.scdn.co/image/cover1"] = b"\x89PNG fake"
    window.net = NetClient(str(tmp_path / "c"), enabled=lambda: True, opener=FakeWeb(routes))
    window.online = OnlineMusic(window.net)
    window.songs[0].artist, window.songs[0].title = "01", "first"            # you already have this one
    window.FRESH_FILE_SECONDS = 0                                             # test files are brand new
    window.import_from_link("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    assert wait_until(qapp, lambda: any(p.name == "Road Trip" for p in window.playlists))
    pl = next(p for p in window.playlists if p.name == "Road Trip")
    assert [s.title for s in pl.songs] == ["Highway Run", "first", "Those in My Way"]
    assert not getattr(pl.songs[1], "is_remote", False) and pl.songs[1] is window.songs[0]   # your file
    assert getattr(pl.songs[0], "is_remote", False) and pl.songs[0] in window.songs_to_download()
    assert wait_until(qapp, lambda: bool(pl.custom_cover))                    # the playlist's own cover
    assert os.path.dirname(pl.custom_cover) == os.path.join(window.storage.data_dir, "covers")
    assert window.stack.currentWidget() is window.playlist_page and window.open_playlist is pl
    window.import_from_link("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    assert wait_until(qapp, lambda: any(p.name == "Road Trip 2" for p in window.playlists))   # never overwrites


def test_import_m3u_with_files_and_missing_songs(window, audio_dir, tmp_path):
    m3u = tmp_path / "Phone.m3u8"
    m3u.write_text("#EXTM3U\n#EXTINF:1,x - first\n" + str(audio_dir / "01 - first.wav") +
                   "\n#EXTINF:200,Kavinsky - Nightcall\nmissing/Kavinsky - Nightcall.mp3\n"
                   "# not downloaded yet: Band - Later\n", encoding="utf-8")
    pl = window.import_from_file(str(m3u))
    assert pl.name == "Phone"
    assert [s.title for s in pl.songs] == ["01 - first", "Nightcall", "Later"]
    assert pl.songs[0] is window.songs[0] and getattr(pl.songs[1], "is_remote", False)


def test_change_and_reset_playlist_cover(window, tmp_path):
    from PIL import Image
    pic = tmp_path / "cover.png"
    Image.new("RGB", (10, 10), "red").save(pic)
    pl = window.create_playlist("Mine", [window.songs[0]])
    assert window.set_playlist_cover(pl, str(pic))
    assert pl.cover_path == pl.custom_cover and os.path.exists(pl.custom_cover)
    stored = pl.custom_cover
    window.set_playlist_cover(pl, "")
    assert not pl.custom_cover and not os.path.exists(stored)            # our copy is tidied up
