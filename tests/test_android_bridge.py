"""The Android app's bridge into the shared core (android/app/src/main/python/sevbify_bridge.py).
Runs on the PC with fake web answers, so a core change that would break Android fails here first."""
import importlib.util
import json
import os

import pytest

from online_fixtures import FakeWeb, ROUTES
from test_podcasts import ROUTES as SHOW_ROUTES
from test_import import embed_page

BRIDGE = os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main", "python", "sevbify_bridge.py")


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("sevbify_bridge", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("SEVBIFY_DATA_DIR", str(tmp_path / "data"))
    out = json.loads(mod.setup(str(tmp_path / "data"), str(tmp_path / "cache"), True, ""))
    assert out["ok"], out
    routes = dict(ROUTES)
    routes.update(SHOW_ROUTES)
    routes["open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M"] = embed_page()
    mod._state["net"]._opener = FakeWeb(routes)
    return mod


def call(mod, name, *args):
    res = json.loads(getattr(mod, name)(*args))
    assert res["ok"], res.get("trace")
    return res["value"]


def test_bridge_search_import_podcasts_and_errors(bridge):
    found = call(bridge, "search", "narc")
    assert found and found[0]["title"] == "NARC" and found[0]["key"]
    pl = call(bridge, "import_link", "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", "")
    assert pl["name"] == "Road Trip" and [t["title"] for t in pl["tracks"]][:1] == ["Highway Run"]
    show = call(bridge, "show_link", "https://feeds.example.com/fvh")
    got = call(bridge, "fetch_show", json.dumps(show))
    assert got["show"]["title"] == "Fin vs History" and len(got["episodes"]) == 2
    assert "official feed" in got["note"]
    # Errors come back as text, never as a crash
    bad = json.loads(bridge.show_link("not a link"))
    assert bad["ok"] is False and "Paste" in bad["error"]
    assert call(bridge, "set_online", False) is False
    offline = json.loads(bridge.search("anything"))
    assert offline["ok"] is False


def test_bridge_errors_are_readable(bridge):
    class E(Exception):
        pass
    out = json.loads(bridge._fail(E("ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot. Use --cookies")))
    assert out["error"].startswith("YouTube is blocking") and "--cookies" not in out["error"]


def test_bridge_book_chapters_and_quality(bridge, monkeypatch):
    from core import audiobooks
    from core.online.models import OnlineTrack
    seen = {}

    def fake(net, book, quality="standard"):
        seen["quality"] = quality
        return book, [OnlineTrack("Chapter 1", "Author", source="audiobook", stream_url="https://archive.org/a.mp3")]
    monkeypatch.setattr(audiobooks, "chapters", fake)
    book = audiobooks.Book(identifier="x", title="A Book")
    got = call(bridge, "book_chapters", json.dumps(book.to_dict()), "high")
    assert [t["title"] for t in got] == ["Chapter 1"] and seen["quality"] == "high"


def test_bridge_opens_shared_playlists_and_blends(bridge):
    from core import share_playlist as SP
    link = call(bridge, "share_link", "Road trip", json.dumps([{"title": "Siesta", "artist": "Jahzzar"}]))
    got = call(bridge, "import_link", "Here: " + link)
    assert got["shared"] == "playlist" and got["name"] == "Road trip" and got["tracks"][0]["title"] == "Siesta"
    taste = SP.taste_link([["Jahzzar", "Siesta", 1]], "Sam")
    got = call(bridge, "import_link", taste, "", "", False, json.dumps([["Kevin MacLeod", "Sneaky Snitch", 1]]))
    assert got["shared"] == "blend" and got["name"] == "You + Sam" and len(got["tracks"]) == 2
    assert call(bridge, "taste_link", json.dumps([["A", "B", 1]])).startswith("sevbify://taste#")
    bad = json.loads(bridge.import_link("sevbify://playlist#v1.%%%"))
    assert not bad["ok"]


def test_bridge_debug_log_is_a_local_text_file_without_emails(bridge, tmp_path):
    call(bridge, "log_event", "play", "Jahzzar - Siesta from https://cdn.example.com/a/b?token=secret")
    call(bridge, "log_event", "note", "signed in as someone.private@example.org")
    call(bridge, "log_private", True)
    call(bridge, "log_event", "play", "Kevin MacLeod - Sneaky Snitch")
    call(bridge, "log_private", False)
    out = call(bridge, "problem_report", str(tmp_path / "report.txt"))
    text = open(out, encoding="utf-8").read()
    assert "Jahzzar - Siesta" in text and "[example.com link]" in text and "token=secret" not in text
    assert "someone.private" not in text and "[email]" in text
    assert "Sneaky Snitch" not in text and "Private Session" in text
