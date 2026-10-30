# Temporary probe (run inside online_check.py): can a Spotify playlist with more than 100 songs be read without an
# account? Reports what the embed page and Chosic's exporter page expose. Nothing here is used by the app.
import json as _json
import re as _re
import urllib.request as _u

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0 Safari/537.36", "Accept-Language": "en"}


def _get(url, headers=None):
    req = _u.Request(url, headers={**_UA, **(headers or {})})
    with _u.urlopen(req, timeout=30) as r:
        return r.status, r.read(3_000_000).decode("utf-8", "replace")


def spotify_embed_token():
    pid = "37i9dQZF1DX5Ejj0EkURtP"          # a public playlist with well over 100 songs
    st, html = _get(f"https://open.spotify.com/embed/playlist/{pid}")
    m = _re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, _re.S)
    data = _json.loads(m.group(1))
    text = _json.dumps(data)
    keys = sorted(set(_re.findall(r'"(accessToken|clientId|correlationId|isAnonymous|accessTokenExpirationTimestampMs)"', text)))
    tok = None
    for mm in _re.finditer(r'"accessToken":\s*"([^"]+)"', text):
        tok = mm.group(1)
    n = len(data["props"]["pageProps"]["state"]["data"]["entity"].get("trackList") or [])
    out = f"embed {st}, {n} songs, keys={keys}, token={'yes' if tok else 'no'}"
    if tok:
        for url in (f"https://api.spotify.com/v1/playlists/{pid}/tracks?offset=100&limit=100&fields=total,items(track(name))",
                    f"https://api.spotify.com/v1/playlists/{pid}?fields=tracks.total"):
            try:
                s2, body = _get(url, {"Authorization": "Bearer " + tok})
                out += f" | {url.split('/v1/')[1][:40]} -> {s2} {body[:160]}"
            except Exception as e:
                out += f" | {url.split('/v1/')[1][:40]} -> {e} {getattr(e, 'read', lambda: b'')()[:200]!r}"
    return out


def chosic_page():
    st, html = _get("https://www.chosic.com/spotify-playlist-exporter/")
    found = sorted(set(_re.findall(r'https?://[^"\'\s]*chosic\.com/[^"\'\s]*(?:api|ajax|admin-ajax|json)[^"\'\s]*', html)))[:8]
    actions = sorted(set(_re.findall(r'action["\']?\s*[:=]\s*["\']([a-z_\-]+)["\']', html)))[:10]
    scripts = [s for s in _re.findall(r'<script[^>]+src="([^"]+)"', html) if "chosic" in s][:8]
    return f"chosic {st}, {len(html)} bytes, endpoints={found}, actions={actions}, scripts={scripts}"


check("Spotify embed token probe", spotify_embed_token)
check("Chosic exporter probe", chosic_page)
