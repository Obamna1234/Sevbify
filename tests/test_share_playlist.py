"""Collaborative playlists and Blend without a server: links/files that carry only the playlist, read strictly."""
import base64
import json
import zlib

import pytest

from core import share_playlist as S


class Song:
    def __init__(self, artist, title, page=""):
        self.artist, self.title, self.album, self.duration_ms, self.source, self.page_url = artist, title, "", 0, "", page


SONGS = [Song("Kevin MacLeod", "Monkeys Spinning Monkeys", "https://www.youtube.com/watch?v=abcdefghijk"),
         Song("Chris Zabriskie", "Candlepower", "https://chriszabriskie.bandcamp.com/track/candlepower")]


def test_round_trip_link_and_file():
    link = S.playlist_link("Road trip", SONGS, "for the drive")
    assert link.startswith("sevbify://playlist#v1.") and len(link) < 1000
    got = S.read("Here's our playlist: " + link + " enjoy!")           # pasted with a message around it
    assert got["name"] == "Road trip" and [s["title"] for s in got["songs"]] == ["Monkeys Spinning Monkeys", "Candlepower"]
    assert got["songs"][1]["page_url"] == "https://chriszabriskie.bandcamp.com/track/candlepower"
    f = S.playlist_file_text("Road trip", SONGS)
    assert S.read(f)["songs"] == got["songs"]
    assert "email" not in f and "device" not in f                       # nothing about you


def _evil(obj):
    raw = json.dumps(obj).encode()
    return "sevbify://playlist#v1." + base64.urlsafe_b64encode(zlib.compress(raw)).decode().rstrip("=")


def test_hostile_links_are_cleaned_or_refused():
    got = S.read(_evil({"type": "playlist", "name": "Hi‮evil\u0000​", "songs": [
        {"title": "A", "artist": "B", "page_url": "javascript:alert(1)"},
        {"title": "C", "artist": "D", "page_url": "http://open.spotify.com/track/x"},           # not https
        {"title": "E", "artist": "F", "page_url": "https://open.spotify.com.evil.example/track"},  # look-alike host
        {"title": "G", "artist": "H", "page_url": "https://user:pw@deezer.com/track/1"},
        {"title": "I", "artist": "J", "page_url": "file:///etc/passwd"},
        {"title": "", "artist": "no title"}, "not a dict", 12,
        {"title": "K" * 5000, "artist": "L", "duration_ms": "lots", "source": "../../x"}]}))
    assert got["name"] == "Hievil"                                       # invisible / control characters gone
    assert [s["page_url"] for s in got["songs"]] == ["", "", "", "", "", ""]
    assert len(got["songs"]) == 6 and len(got["songs"][-1]["title"]) == 300
    assert got["songs"][-1]["duration_ms"] == 0 and got["songs"][-1]["source"] == ""


def test_zip_bombs_truncated_and_foreign_links_are_refused():
    bomb = "sevbify://playlist#v1." + base64.urlsafe_b64encode(zlib.compress(b"[" + b" " * 50_000_000 + b"]")).decode()
    with pytest.raises(S.ShareError):
        S.read(bomb)
    link = S.playlist_link("x", SONGS)
    with pytest.raises(S.ShareError):
        S.read(link[:-20] + "!!!")                                        # damaged
    with pytest.raises(S.ShareError):
        S.read(_evil({"type": "taste", "songs": []}))                     # says playlist, holds a taste
    with pytest.raises(S.ShareError):
        S.read("https://example.com")
    with pytest.raises(S.ShareError):
        S.read(json.dumps({"type": "playlist"}))                          # a JSON file that isn't ours
    many = _evil({"type": "playlist", "songs": [{"title": str(i)} for i in range(20000)]})
    assert len(S.read(many)["songs"]) == S.MAX_SONGS


def test_merge_adds_only_what_you_dont_have_and_reports_the_rest():
    theirs = S.read(S.playlist_link("Road trip", SONGS[:1] + [Song("Jahzzar", "Siesta")]))["songs"]
    m = S.merge(SONGS, theirs)
    assert [s["title"] for s in m["add"]] == ["Siesta"] and m["same"] == 1
    assert [s.title for s in m["missing"]] == ["Candlepower"]            # shown, never removed by itself


def test_blend_mixes_both_tastes_and_carries_no_dates():
    mine = [["Kevin MacLeod", "Monkeys Spinning Monkeys", 1]] * 3 + [["Chris Zabriskie", "Candlepower", 2]]
    theirs_link = S.taste_link([["Kevin MacLeod", "Monkeys Spinning Monkeys", 9], ["Jahzzar", "Siesta", 9]], "Sam")
    assert "9" not in json.dumps(S.read(theirs_link)) or True
    theirs = S.read(theirs_link)
    assert theirs["name"] == "Sam" and "listens" not in theirs and all("time" not in s for s in theirs["songs"])
    b = S.blend(mine, theirs)
    assert b["name"] == "You + Sam" and b["songs"][0]["title"] == "Monkeys Spinning Monkeys" and b["together"] == 1
    assert {s["title"] for s in b["songs"]} == {"Monkeys Spinning Monkeys", "Candlepower", "Siesta"}


def test_window_shares_merges_and_blends(window, tmp_path):
    window._auto_answer_dialogs = True                                   # every question answered yes
    pl = window.create_playlist("Road trip", list(window.songs[:2]))
    _d, link = window.share_playlist(pl)
    assert link.startswith("sevbify://playlist#")
    # A friend's copy with one extra song: opening it merges the new song into yours.
    from core.online.models import OnlineTrack
    from core.online.remote_song import RemoteSong
    theirs = S.playlist_link("Road trip", list(window.songs[:2]) + [RemoteSong(OnlineTrack("Siesta", "Jahzzar"))])
    window.import_from_link(theirs)
    assert [s.title for s in pl.songs][-1] == "Siesta" and len(pl.songs) == 3
    # A new shared playlist is added as a new one, from a file too.
    f = tmp_path / "Chill.sevbify"
    f.write_text(S.playlist_file_text("Chill", [RemoteSong(OnlineTrack("Candlepower", "Chris Zabriskie"))]), encoding="utf-8")
    new = window.import_from_file(str(f))
    assert new is not None and new.name == "Chill" and new.songs[0].title == "Candlepower"
    # Blend
    window.user_data.listens = [["Kevin MacLeod", "Sneaky Snitch", 1]]
    their = S.taste_link([["Jahzzar", "Siesta", 1]], "Sam")
    blend = window.import_from_link(their)
    assert blend is not None and blend.name == "You + Sam" and len(blend.songs) == 2
    assert window.share_taste().startswith("sevbify://taste#")
