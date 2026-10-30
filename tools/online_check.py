"""Live check of Sevbify's online services (run by the GitHub build).

Calls each real service once and reports what came back as GitHub
annotations (::notice / ::warning), so problems with a service's format or
availability are visible without failing the build. Always exits 0.
"""
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.online.net import NetClient          # noqa: E402
from core.online.providers import OnlineMusic  # noqa: E402

results = []


def check(name, fn):
    try:
        detail = fn()
        print(f"::notice title=Online OK: {name}::{detail}")
        results.append(True)
    except Exception as e:
        print(f"::warning title=Online FAILED: {name}::{type(e).__name__}: {e}")
        traceback.print_exc()
        results.append(False)


net = NetClient(tempfile.mkdtemp())
om = OnlineMusic(net, os.environ.get("LASTFM_API_KEY", ""))


def deezer_search():
    r = om.search("Mega Drive NARC", limit=5)
    t = r[0]
    assert t.title and t.artist and t.preview_url and t.cover_url, t
    return f"{len(r)} results; first='{t.artist} - {t.title}' {t.duration_ms // 1000}s preview={bool(t.preview_url)}"


def deezer_artist_card():
    c = om.artist_card("Perturbator")
    assert c.get("picture_url") and c.get("fans"), c
    return f"fans={c['fans']} bio_source={c.get('bio_source', '-')} bio_len={len(c.get('bio', ''))}"


def deezer_radio():
    r = om.radio("Perturbator", "Raining Steel", limit=30)
    assert len(r) >= 10, len(r)
    return f"{len(r)} songs, {len({t.artist for t in r})} artists, e.g. " + "; ".join(f"{t.artist} - {t.title}" for t in r[:3])


def deezer_genre():
    t = om.search("Nirvana Smells Like Teen Spirit", limit=1)[0]
    g = om.genre_of(t)
    assert g and g != "Other", g
    return f"genre={g}"


def wikipedia():
    w = om.wiki.artist_summary("Perturbator")
    assert w.get("bio"), w
    return w["bio"][:80]


check("Deezer search", deezer_search)
check("Artist card", deezer_artist_card)
check("Radio", deezer_radio)
check("Genre", deezer_genre)
check("Wikipedia", wikipedia)

for extra in ("archive", "jamendo"):
    mod_path = os.path.join(os.path.dirname(__file__), f"online_check_{extra}.py")
    if os.path.exists(mod_path):
        exec(open(mod_path, encoding="utf-8").read())

print(f"Online checks: {sum(results)}/{len(results)} passed")
sys.exit(0)
