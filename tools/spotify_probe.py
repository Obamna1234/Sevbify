"""Can a public Spotify playlist with more than 100 songs be read in full without signing in? (Information only;
run by hand from the "Health check" workflow.) Prints only counts and HTTP results, never song names.

Routes tried, all with the anonymous key Spotify's own embed / web player hands to any visitor:
  1. api.spotify.com/v1/playlists/<id>/tracks           (the public Web API)
  2. spclient.wg.spotify.com/playlist/v2/playlist/<id>  (the web player's own playlist service, JSON)
  3. api-partner.spotify.com/pathfinder/v1/query         (the web player's GraphQL; query id read from its script)
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PLAYLIST = sys.argv[1] if len(sys.argv) > 1 else "37i9dQZF1DX5Ejj0EkURtP"     # a public playlist of ~150 songs
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 "
      "Safari/537.36")


def get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read(8_000_000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000)
    except Exception as e:
        return 0, str(e).encode()


def shape(v, depth=0):
    """The structure of a JSON value with every text replaced by its type (no song names are printed)."""
    if depth > 7:
        return "…"
    if isinstance(v, dict):
        return {k: shape(x, depth + 1) for k, x in list(v.items())[:25]}
    if isinstance(v, list):
        return [shape(v[0], depth + 1), f"×{len(v)}"] if v else []
    if isinstance(v, str):
        return "uri" if v.startswith("spotify:") else ("url" if v.startswith("http") else "str")
    return type(v).__name__


def say(label, text):
    print(f"{label}: {text}", flush=True)


def main():
    from core import importers
    st, body = get(importers.spotify_embed_url("playlist", PLAYLIST))
    say("embed page", st)
    try:
        res = importers.parse_spotify_embed(body.decode("utf-8", "replace"))
    except Exception as e:
        say("embed parse", f"failed {e}")
        return
    token = res.get("_token", "")
    say("embed songs", f"{len(res['tracks'])}, key {'yes' if token else 'no'} ({len(token)} chars)")
    if not token:
        return
    auth = {"Authorization": "Bearer " + token}

    st, body = get(f"https://api.spotify.com/v1/playlists/{PLAYLIST}/tracks?offset=100&limit=100&fields=total,items(track(id))",
                   auth)
    try:
        d = json.loads(body)
        say("1 web api", f"{st} total={d.get('total')} got={len(d.get('items') or [])}")
    except Exception:
        say("1 web api", f"{st} {body[:160]!r}")

    st, body = get(f"https://spclient.wg.spotify.com/playlist/v2/playlist/{PLAYLIST}?from=0&length=1000",
                   {**auth, "Accept": "application/json", "App-Platform": "WebPlayer"})
    try:
        d = json.loads(body)
        items = ((d.get("contents") or {}).get("items")) or []
        say("2 spclient playlist", f"{st} items={len(items)} first uri kind={items[0].get('uri', '')[:14] if items else '-'}")
        if items:
            uris = [i.get("uri", "") for i in items if i.get("uri", "").startswith("spotify:track:")]
            ids = ",".join(u.split(":")[-1] for u in uris[100:150])
            st2, b2 = get(f"https://api.spotify.com/v1/tracks?ids={ids}", auth)
            try:
                say("2b web api tracks", f"{st2} got={len(json.loads(b2).get('tracks') or [])}")
            except Exception:
                say("2b web api tracks", f"{st2} {b2[:120]!r}")
            gid = uris[120].split(":")[-1] if len(uris) > 120 else ""
            if gid:
                st3, b3 = get(importers.spotify_embed_url("track", gid))
                t = importers.parse_spotify_track_embed(b3.decode("utf-8", "replace"), gid) if st3 == 200 else None
                say("2c track embed page", f"{st3} parsed={'yes' if t else 'no'}")
    except Exception:
        say("2 spclient playlist", f"{st} {body[:160]!r}")

    st, html = get("https://open.spotify.com/")
    scripts = re.findall(rb'src="(https://open\.spotifycdn\.com/cdn/build/web-player/[^"]+\.js)"', html)
    say("3 web player page", f"{st} scripts={len(scripts)}")
    hashes = {}
    for src in scripts[:12]:
        s2, js = get(src.decode())
        for name in (b"fetchPlaylist", b"fetchPlaylistContents"):
            m = re.search(b'"' + name + rb'","query","([0-9a-f]{64})"', js)
            if m:
                hashes[name.decode()] = m.group(1).decode()
    say("3 query ids", ", ".join(hashes) or "none found")
    for name, h in hashes.items():
        variables = {"uri": f"spotify:playlist:{PLAYLIST}", "offset": 100, "limit": 100}
        if name == "fetchPlaylist":
            variables["enableWatchFeedEntrypoint"] = False
        payload = json.dumps({"variables": variables, "operationName": name,
                              "extensions": {"persistedQuery": {"version": 1, "sha256Hash": h}}}).encode()
        st, body = get("https://api-partner.spotify.com/pathfinder/v1/query",
                       {**auth, "Content-Type": "application/json;charset=UTF-8", "App-Platform": "WebPlayer"}, payload)
        try:
            d = json.loads(body)
            pl = (d.get("data") or {}).get("playlistV2") or {}
            content = pl.get("content") or {}
            say(f"3 {name}", f"{st} total={content.get('totalCount')} got={len(content.get('items') or [])} "
                             f"errors={[e.get('message', '')[:60] for e in d.get('errors') or []]}")
            items = content.get("items") or []
            if items:
                say(f"3 {name} item shape", json.dumps(shape(items[0]))[:3000])
            if name == "fetchPlaylist":
                say("3 playlist shape", json.dumps(shape({k: v for k, v in pl.items() if k != "content"}))[:1500])
        except Exception:
            say(f"3 {name}", f"{st} {body[:160]!r}")


if __name__ == "__main__":
    main()
