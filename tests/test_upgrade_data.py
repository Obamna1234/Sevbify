"""Updating keeps your library: a library saved by an earlier release loads in this one with nothing lost.

tests/fixtures/library-v<N>.json were written by that release's own code (its core/storage.py). Before each
release, add the previous release's file (tools: a git worktree of its tag, save a UserData like this one's) and
keep the old ones: every past format must keep loading.
"""
import glob
import json
import os
import shutil

from core.storage import Storage

FIXTURES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "fixtures", "library-v*.json")))


def test_there_is_at_least_one_earlier_library():
    assert FIXTURES


def test_every_earlier_library_loads_with_nothing_lost(tmp_path):
    for fixture in FIXTURES:
        d = tmp_path / os.path.basename(fixture)
        d.mkdir()
        shutil.copy(fixture, d / "library.json")
        data = Storage(str(d)).load()
        assert not getattr(data, "load_warning", ""), (fixture, data.load_warning)
        assert data.volume == 63 and data.shuffle and data.repeat == "all"
        names = [p.name for p in data.playlists]
        assert names == ["Liked Songs", "Road trip", "Imported"], fixture
        trip = data.playlists[1]
        assert trip.folder == "Trips" and trip.pinned and trip.description == "Made in v48"
        assert len(trip.tracks) == 2 and trip.tracks[1]["pending"]["title"] == "Candlepower"
        assert data.playlists[0].origin == "liked" and data.playlists[2].origin == "spotify"
        # ...and saving it again in today's format keeps it all
        Storage(str(d)).save(data)
        again = Storage(str(d)).load()
        assert [p.name for p in again.playlists] == names and again.playlists[1].tracks == trip.tracks


def test_a_damaged_library_is_kept_aside_not_lost(tmp_path):
    (tmp_path / "library.json").write_text("{ not json")
    data = Storage(str(tmp_path)).load()
    assert "could not be read" in data.load_warning
    assert any("library" in f and f != "library.json" for f in os.listdir(tmp_path))   # the copy kept
