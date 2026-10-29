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
