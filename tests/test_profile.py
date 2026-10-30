"""The Sevbify profile file (core/profile.py) and the Windows app's Export / Import."""
import gzip
import json

import pytest

from core import profile


def sample():
    return {"from": "android", "playlists": [
        {"name": "Road trip", "folder": "Car", "pinned": True, "origin": "spotify",
         "tracks": [{"title": "Future Club", "artist": "Perturbator", "duration_ms": 290000, "local_uri": "content://x",
                     "cover_url": "https://img/x.jpg"}, {"artist": "no title"}]},
        {"name": "  ", "tracks": []}],
        "folders": ["Car"], "shows": [{"title": "Pod", "feed_url": "https://f/rss"}, {"title": "broken"}],
        "books": [{"identifier": "pride", "title": "Pride"}], "resume": {"podcast:1": 90000, "bad": -1},
        "recent": [{"title": "A", "artist": "B"}], "searches": ["daft punk", ""],
        "settings": {"autoplay": False, "skip_sponsors": True, "music_folders": ["C:/secret"]}}


def test_pack_unpack_keeps_only_safe_known_parts():
    raw = profile.pack(sample())
    assert raw[:2] == b"\x1f\x8b" and len(raw) < 2000          # small and compressed
    d = profile.unpack(raw)
    pl = d["playlists"]
    assert len(pl) == 1 and pl[0]["name"] == "Road trip" and pl[0]["pinned"] and pl[0]["origin"] == "spotify"
    assert pl[0]["tracks"] == [{"title": "Future Club", "artist": "Perturbator", "duration_ms": 290000,
                                "cover_url": "https://img/x.jpg"}]                  # no device paths
    assert len(d["shows"]) == 1 and d["resume"] == {"podcast:1": 90000} and d["searches"] == ["daft punk"]
    assert d["settings"] == {"autoplay": False, "skip_sponsors": True}            # no folders from the device


def test_rejects_other_files():
    for bad in (b"", b"hello", gzip.compress(b'{"format": "other"}'), json.dumps({"format": "sevbify-profile",
                                                                                   "version": 99}).encode()):
        with pytest.raises(profile.ProfileError):
            profile.unpack(bad)
    assert profile.unpack_b64(profile.pack_b64(json.dumps(sample())))["folders"] == ["Car"]


def test_names_never_clash():
    assert profile.merge_names(["Road trip"], "Road trip") == "Road trip (imported)"
    assert profile.merge_names(["Road trip", "road trip (imported)"], "Road trip") == "Road trip (imported 2)"
    assert profile.merge_names([], "New") == "New"


def test_windows_export_then_import_on_another_computer(open_window, audio_dir, data_dir, tmp_path):
    w = open_window(audio_folder=str(audio_dir), data_dir=str(data_dir))
    pl = w.create_playlist("Synth", w.songs[:2])
    w.user_data.folders.append("Car"); pl.folder = "Car"
    w.user_data.shows.append({"title": "Pod", "feed_url": "https://f/rss", "kind": "rss"})
    w.remember_search("daft punk")
    path = w.export_profile(str(tmp_path / "me"))
    assert path.endswith(".sevbify")
    d = profile.load(path)
    assert d["playlists"][0]["name"] == "Synth" and d["playlists"][0]["tracks"][0]["title"] == w.songs[0].title
    assert "file_path" not in json.dumps(d) and str(audio_dir) not in json.dumps(d)   # no paths from this computer
    w.close()

    other = tmp_path / "other"; other.mkdir()
    w2 = open_window(audio_folder=str(audio_dir), data_dir=str(other))
    w2.FRESH_FILE_SECONDS = 0                     # the test files were just made
    assert w2.import_profile(path) == 1
    synth = next(p for p in w2.playlists if p.name == "Synth")
    assert len(synth.songs) == 2 and synth.folder == "Car"
    assert all(not getattr(s, "is_remote", False) for s in synth.songs)        # matched to this computer's files
    assert w2.user_data.shows[0]["feed_url"] == "https://f/rss" and w2.user_data.recent_searches == ["daft punk"]
    assert w2.import_profile(path) == 0                                         # importing twice adds nothing
