"""
SEVBY download engine, used by Sevbify's "Get music" page.

This file is generated from the SEVBY desktop app (MIT licence, https://github.com/Obamna1234/sevby)
with all the window code removed, so it can run inside Sevbify without customtkinter.
Do not edit it by hand: change SEVBY and regenerate it instead.

What it does for each "Artist - Title" line: look on Bandcamp first, fall back to YouTube (via yt-dlp),
and save a 128 kbps MP3 with title, artist, album, year, track number and cover art (via ffmpeg).
Only download music you have the right to download.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


# An updated yt-dlp (downloaded from About & updates) wins over the copy bundled in the app.
YTDLP_UPDATE_DIR = Path.home() / ".sevby_ytdlp"
YTDLP_ACTIVE = ""
try:
    _upd = YTDLP_UPDATE_DIR / "yt-dlp"
    if _upd.is_file():
        import importlib.machinery

        sys.path.insert(0, str(_upd))
        if getattr(sys, "frozen", False):
            # packaged apps look inside their own bundle first; make the path search go first for this
            if importlib.machinery.PathFinder in sys.meta_path:
                sys.meta_path.remove(importlib.machinery.PathFinder)
            sys.meta_path.insert(0, importlib.machinery.PathFinder)
        YTDLP_ACTIVE = str(_upd)
except Exception:
    YTDLP_ACTIVE = ""

# yt-dlp as a Python module (works inside the packaged .exe, no PATH needed)
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

_HAS_DND = False  # no drag-and-drop in the engine



def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


VERSION = "1.0.1"  # version of the SEVBY engine this file was taken from
APP_NAME = "SEVBY"
CONFIG_PATH = Path.home() / ".sevby_config.json"
LOG_PATH = Path.home() / ".sevby_log.txt"  # copy of the last run's log, handy for bug reports
BANDCAMP_API = "https://bandcamp.com/api/fuzzysearch/2/app_autocomplete"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Must match the Redirect URI typed into the Spotify developer app
SPOTIFY_REDIRECT = "http://127.0.0.1:8888"
SPOTIFY_PORT = 8888
SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative"

# Pause / Stop flags shared between the buttons and the worker thread
STOP_EVENT = threading.Event()
PAUSE_EVENT = threading.Event()


class _Stopped(Exception):
    """Raised inside a yt-dlp progress hook to abort the current download."""


# \u2500\u2500 Config helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


# \u2500\u2500 Bandcamp search \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def fix_bc_url(url: str) -> str:
    if not url:
        return ""
    if url.count("https://") > 1:
        url = "https://" + url.split("https://")[-1]
    return url


def _split_query(query: str) -> tuple[str, str]:
    """Return (artist, title). Artist is '' if no separator found."""
    for sep in (" - ", " \u2013 ", " \u2014 "):
        if sep in query:
            a, t = query.split(sep, 1)
            return a.strip(), t.strip()
    return "", query.strip()


def bc_score(result: dict, query: str) -> float:
    q = query.lower().strip()
    name = (result.get("name") or "").lower()
    band = (result.get("band_name") or "").lower()
    q_clean = q.replace("\u2013", " ").replace("\u2014", " ").replace("-", " ").replace(",", " ")
    tokens = [t for t in q_clean.split() if len(t) > 1]
    score = 0.0
    for tok in tokens:
        if tok in band:
            score += 35
        if tok in name:
            score += 20
    _, title_guess = _split_query(q)
    title_guess = title_guess.lower()
    if title_guess and title_guess in name:
        score += 40
    if result.get("type") == "t":
        score += 5
    if any(w in name for w in ("remix", "cover", "bootleg", "tribute")):
        if not any(w in q for w in ("remix", "cover", "bootleg")):
            score -= 25
    return score


def _artist_matches(result: dict, query: str) -> bool:
    """Guard against wrong-artist hits: at least one artist word must be in the band name."""
    artist, _ = _split_query(query)
    if not artist:
        return True
    band = (result.get("band_name") or "").lower()
    words = [w for w in re.split(r"[\s,&]+", artist.lower()) if len(w) > 1]
    return any(w in band for w in words) if words else True


SIMPLE_UA = "Mozilla/5.0 (compatible; BandcampSongLinker/1.0)"
BCSEARCH_API = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"

# Which request style worked last time (tried first on the next search)
_bc_pref = [0]


def _describe_block(status: int | None, body: str) -> str:
    """Short human-readable reason for a non-JSON reply."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:140]
    low = body.lower()
    hint = ""
    if "javascript" in low and ("challenge" in low or "enable" in low):
        hint = " (Bandcamp is showing a JavaScript bot check)"
    elif "avg" in low:
        hint = " (looks like an AVG block page)"
    elif "cloudflare" in low or "just a moment" in low or "captcha" in low:
        hint = " (looks like a bot check)"
    elif "<html" in low:
        hint = " (got a web page instead of JSON)"
    st = f"HTTP {status}: " if status else ""
    return f"{st}{text or 'empty reply'}{hint}"


def _fetch(url: str, headers: dict, data: bytes | None = None) -> tuple[str | None, str | None]:
    """Return (json_text, None) or (None, reason)."""
    req = urllib.request.Request(url, headers=headers, data=data)
    status = None
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return None, _describe_block(e.code, body)
    except Exception as e:
        return None, f"network error: {e}"
    if not raw or raw[0] not in "{[":
        return None, _describe_block(status, raw)
    return raw, None


def _fetch_curl(url: str, headers: dict, data: bytes | None = None) -> tuple[str | None, str | None]:
    """Same request through the system curl (a different, standard HTTP client)."""
    exe = shutil.which("curl.exe") or shutil.which("curl")
    if not exe:
        return None, "curl not available"
    cmd = [exe, "-sS", "-L", "--max-time", "20", url]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if data is not None:
        cmd += ["--data-binary", data.decode("utf-8")]
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=flags)
    except Exception as e:
        return None, f"curl failed: {e}"
    raw = r.stdout.decode("utf-8", errors="replace").strip()
    if not raw or raw[0] not in "{[":
        return None, _describe_block(None, raw or r.stderr.decode("utf-8", errors="replace"))
    return raw, None


def _norm_fuzzy(data: dict) -> list[dict]:
    return [
        {
            "type": r.get("type") or "",
            "name": r.get("name") or "",
            "band_name": r.get("band_name") or "",
            "album_name": r.get("album_name") or "",
            "url": r.get("url") or "",
        }
        for r in (data.get("results") or [])
    ]


def _norm_bcsearch(data) -> list[dict]:
    block = data.get("auto") if isinstance(data, dict) else None
    items = (block or {}).get("results") if isinstance(block, dict) else None
    if items is None and isinstance(data, dict):
        items = data.get("results")
    out = []
    for r in items or []:
        url = r.get("item_url_path") or r.get("item_url_root") or r.get("url") or ""
        out.append(
            {
                "type": r.get("type") or "",
                "name": r.get("name") or "",
                "band_name": r.get("band_name") or "",
                "album_name": r.get("album_name") or "",
                "url": url,
            }
        )
    return out


def _bandcamp_request(q: str) -> tuple[list, str | None]:
    """Try several request styles; return (results, None) or ([], reason)."""
    qs = urllib.parse.urlencode({"q": q, "param_with_locations": "true"})
    fuzzy_url = f"{BANDCAMP_API}?{qs}"
    post_body = json.dumps(
        {"search_text": q, "search_filter": "t", "full_page": False, "fan_id": None}
    ).encode()

    strategies = [
        # 0: exactly what the working bandcamp_search.py does
        lambda: (
            _fetch(fuzzy_url, {"User-Agent": SIMPLE_UA, "Accept": "application/json"}),
            _norm_fuzzy,
        ),
        # 1: look like a normal browser
        lambda: (
            _fetch(
                fuzzy_url,
                {
                    "User-Agent": BROWSER_UA,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://bandcamp.com/",
                    "Origin": "https://bandcamp.com",
                },
            ),
            _norm_fuzzy,
        ),
        # 2: the website's own search API
        lambda: (
            _fetch(
                BCSEARCH_API,
                {
                    "User-Agent": BROWSER_UA,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Referer": "https://bandcamp.com/",
                    "Origin": "https://bandcamp.com",
                },
                data=post_body,
            ),
            _norm_bcsearch,
        ),
        # 3: same plain request through the system curl
        lambda: (
            _fetch_curl(fuzzy_url, {"User-Agent": SIMPLE_UA, "Accept": "application/json"}),
            _norm_fuzzy,
        ),
    ]

    order = [_bc_pref[0]] + [i for i in range(len(strategies)) if i != _bc_pref[0]]
    first_reason = None
    for idx in order:
        (raw, reason), norm = strategies[idx]()
        if raw is not None:
            try:
                results = norm(json.loads(raw))
            except Exception as e:
                reason = f"could not read reply: {e}"
            else:
                _bc_pref[0] = idx
                return results, None
        if first_reason is None:
            first_reason = reason
        time.sleep(0.4)
    return [], first_reason or "unknown error"


def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower().replace("&", " and "))


def _bc_subdomains(artist: str) -> list[str]:
    """Likely Bandcamp subdomains for an artist name."""
    first = re.split(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bx\b)\s*", artist, flags=re.I)[0]
    low = re.sub(r"['\u2019`]", "", first.lower()).strip()
    out: list[str] = []
    for s in (re.sub(r"[^a-z0-9]", "", low), re.sub(r"[^a-z0-9]+", "-", low).strip("-")):
        if s and s not in out:
            out.append(s)
    return out


def _bc_title_slugs(title: str) -> list[str]:
    """Likely URL slugs for a track title."""
    no_paren = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", title).strip()
    variants = [title, no_paren, re.split(r"\s+[-\u2013\u2014]\s+", no_paren)[0].strip()]
    out: list[str] = []
    for v in variants:
        low = re.sub(r"['\u2019`]", "", v.lower())
        slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
        if slug and slug not in out:
            out.append(slug)
    return out


def _probe_bc_track(url: str) -> dict | None:
    """Read a Bandcamp track page through yt-dlp (no download). None if it doesn't exist."""
    if yt_dlp is None:
        return None
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "logger": _QuietLogger(),
        "socket_timeout": 15,
        "retries": 1,
        "no_color": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _guess_bandcamp(query: str) -> dict | None:
    """When Bandcamp's search is blocked: try the artist's own track page and verify it."""
    artist, title = _split_query(query)
    if not artist or not title or yt_dlp is None:
        return None
    want = _norm_text(re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", title))
    artist_words = [w for w in re.split(r"[\s,&]+", artist.lower()) if len(w) > 1]
    for sub in _bc_subdomains(artist):
        for slug in _bc_title_slugs(title):
            if STOP_EVENT.is_set():
                return None
            url = f"https://{sub}.bandcamp.com/track/{slug}"
            info = _probe_bc_track(url)
            if not info:
                continue
            raw_title = info.get("track") or info.get("title") or ""
            got_title = _norm_text(raw_title)
            got_artist = (info.get("artist") or info.get("uploader") or "").lower()
            if not got_title or not want:
                continue
            title_ok = want in got_title or got_title in want
            artist_ok = any(w in got_artist for w in artist_words) or sub in _norm_text(got_artist)
            if version_set(raw_title) != version_set(title):
                continue
            if title_ok and artist_ok:
                return {
                    "found": True,
                    "name": raw_title,
                    "band_name": info.get("artist") or "",
                    "url": info.get("webpage_url") or url,
                    "guessed": True,
                }
    return None


def search_bandcamp(query: str, use_api: bool = True) -> dict:
    """Find the best TRACK on Bandcamp for 'Artist - Title'."""
    if not use_api:
        return _guess_bandcamp(query) or {"found": False}

    results, err = _bandcamp_request(query)
    if err and not results:
        guess = _guess_bandcamp(query)
        if guess:
            return guess
        return {"found": False, "error": err}

    tracks = [r for r in results if r.get("type") == "t"]

    if not tracks:
        _, title = _split_query(query)
        if title and title != query:
            more, err2 = _bandcamp_request(title)
            tracks = [r for r in more if r.get("type") == "t"]
            if err2 and not tracks:
                return {"found": False, "error": err2}

    best = bc_choose(tracks, query)
    if not best:
        return {"found": False}
    url = fix_bc_url(best.get("url") or "")
    if not url:
        return {"found": False}
    return {
        "found": True,
        "name": best.get("name") or "",
        "band_name": best.get("band_name") or "",
        "url": url,
    }


# \u2500\u2500 Spotify (PKCE login = Client ID only, works for private playlists) \u2500\u2500\u2500\u2500\u2500\u2500

def _http_json(req: urllib.request.Request, timeout: int = 20) -> dict:
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                # Spotify rate limit (can happen on very large playlists): wait as told, retry
                try:
                    wait = int(e.headers.get("Retry-After", "2"))
                except (TypeError, ValueError):
                    wait = 2
                time.sleep(min(max(wait, 1), 60))
                continue
            try:
                body = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                body = ""
            raise RuntimeError(f"HTTP {e.code} {body}".strip()) from e
    raise RuntimeError("HTTP 429 too many requests")


def _token_post(fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _http_json(req, timeout=20)


def spotify_login_pkce(client_id: str, log, timeout: int = 180) -> dict | None:
    """Open the browser once for Spotify login. Returns token dict or None."""
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in qs or "error" in qs:
                got["code"] = (qs.get("code") or [""])[0]
                got["error"] = (qs.get("error") or [""])[0]
                got["state"] = (qs.get("state") or [""])[0]
                body = (
                    "<html><body style='font-family:sans-serif;background:#1a1a1a;"
                    "color:#eee;text-align:center;padding-top:80px'>"
                    "<h2>SEVBY connected to Spotify</h2>"
                    "<p>You can close this tab and go back to the app.</p>"
                    "</body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    try:
        server = HTTPServer(("127.0.0.1", SPOTIFY_PORT), Handler)
    except OSError as e:
        log(f"Could not open local login port {SPOTIFY_PORT}: {e}")
        return None
    server.timeout = 1

    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": SPOTIFY_REDIRECT,
            "scope": SPOTIFY_SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
    )
    log("Opening your browser to log in to Spotify (one-time)\u2026")
    webbrowser.open(f"https://accounts.spotify.com/authorize?{params}")

    deadline = time.time() + timeout
    try:
        while time.time() < deadline and not got:
            server.handle_request()
    finally:
        server.server_close()

    if not got:
        log("Spotify login timed out.")
        return None
    if got.get("error") or not got.get("code"):
        log(f"Spotify login was cancelled or failed: {got.get('error') or 'no code'}")
        return None
    if got.get("state") != state:
        log("Spotify login state mismatch \u2014 aborted.")
        return None

    try:
        return _token_post(
            {
                "grant_type": "authorization_code",
                "code": got["code"],
                "redirect_uri": SPOTIFY_REDIRECT,
                "client_id": client_id,
                "code_verifier": verifier,
            }
        )
    except Exception as e:
        log(f"Spotify token exchange failed: {e}")
        return None


def spotify_client_credentials(client_id: str, client_secret: str) -> str | None:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        return _http_json(req).get("access_token")
    except Exception:
        return None


def get_spotify_access_token(client_id: str, client_secret: str, log) -> str | None:
    """Refresh token -> browser login -> (fallback) client credentials."""
    cfg = load_config()

    # 1) Saved refresh token (no browser needed)
    rt = cfg.get("refresh_token")
    if rt and cfg.get("refresh_client_id") == client_id:
        try:
            tok = _token_post(
                {"grant_type": "refresh_token", "refresh_token": rt, "client_id": client_id}
            )
            if tok.get("access_token"):
                if tok.get("refresh_token"):
                    cfg["refresh_token"] = tok["refresh_token"]
                    save_config(cfg)
                return tok["access_token"]
        except Exception:
            log("Saved Spotify login expired \u2014 logging in again.")

    # 2) Browser login (works for private playlists)
    tok = spotify_login_pkce(client_id, log)
    if tok and tok.get("access_token"):
        cfg = load_config()
        cfg["client_id"] = client_id
        cfg["refresh_client_id"] = client_id
        if tok.get("refresh_token"):
            cfg["refresh_token"] = tok["refresh_token"]
        save_config(cfg)
        return tok["access_token"]

    # 3) Optional fallback: old client-credentials (public playlists only)
    if client_secret:
        log("Trying public-playlist access with Client Secret\u2026")
        return spotify_client_credentials(client_id, client_secret)
    return None


# Extra info about each song ("Artist - Title" string -> tags, length, cover URL).
# Filled from Spotify playlists; used for tagging and for picking the right YouTube video.
SONG_META: dict[str, dict] = {}


def _spotify_meta(track: dict) -> dict:
    album = track.get("album") or {}
    images = album.get("images") or []
    release = album.get("release_date") or ""
    return {
        "artist": ", ".join(a.get("name", "") for a in (track.get("artists") or []) if a.get("name")),
        "album_artist": ", ".join(
            a.get("name", "") for a in (album.get("artists") or []) if a.get("name")
        ),
        "title": track.get("name") or "",
        "album": album.get("name") or "",
        "year": release[:4] if release[:4].isdigit() else "",
        "track": track.get("track_number") or 0,
        "track_total": album.get("total_tracks") or 0,
        "duration": (track.get("duration_ms") or 0) / 1000.0,
        "cover_url": images[0].get("url", "") if images else "",
    }


def fetch_spotify_tracks(playlist_url: str, token: str) -> list[str]:
    m = re.search(r"playlist[/:]([a-zA-Z0-9]+)", playlist_url)
    if not m:
        raise ValueError("Could not find a playlist ID in that URL.")
    pid = m.group(1)

    last_err: Exception | None = None
    for endpoint in ("items", "tracks"):  # Spotify renamed this endpoint; try both
        tracks: list[str] = []
        url = f"https://api.spotify.com/v1/playlists/{pid}/{endpoint}?limit=100"
        try:
            while url:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                data = _http_json(req)
                for item in data.get("items") or []:
                    track = item.get("track") or item.get("item") or {}
                    name = track.get("name") or ""
                    artists = ", ".join(
                        a.get("name", "") for a in (track.get("artists") or []) if a.get("name")
                    )
                    if name and artists:
                        label = f"{artists} - {name}"
                        tracks.append(label)
                        SONG_META[label] = _spotify_meta(track)
                url = data.get("next")
            return tracks
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(
        f"Could not read that playlist ({last_err}). "
        "Make sure you logged in with the account that can see it."
    )


def spotify_playlist_name(playlist_url: str, token: str) -> str:
    m = re.search(r"playlist[/:]([a-zA-Z0-9]+)", playlist_url)
    if not m:
        return ""
    req = urllib.request.Request(
        f"https://api.spotify.com/v1/playlists/{m.group(1)}?fields=name",
        headers={"Authorization": f"Bearer {token}"},
    )
    return (_http_json(req).get("name") or "").strip()


# \u2500\u2500 Song list parsing \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

_TITLE_COLS = ("track name", "track", "title", "name", "song", "song name", "track title")
_ARTIST_COLS = ("artist name(s)", "artist name", "artist", "artists", "artist(s)", "album artist")


def _structured_to_lines(text: str) -> list[str] | None:
    """Turn an M3U playlist, or a CSV / tab-separated export (Apple Music, TuneMyMusic, Soundiiz,
    Exportify...) into 'Artist - Title' lines. Returns None if the text isn't one of those."""
    import csv
    import io

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    # M3U / M3U8: "#EXTINF:123,Artist - Title"
    if lines[0].strip().upper().startswith("#EXTM3U") or any(ln.startswith("#EXTINF:") for ln in lines[:5]):
        out = []
        for ln in lines:
            if ln.startswith("#EXTINF:") and "," in ln:
                t = ln.split(",", 1)[1].strip()
                if t:
                    out.append(t)
        return out or None
    # CSV / TSV with a header row naming a title column and an artist column
    head = lines[0]
    delim = "\t" if head.count("\t") >= 1 else ("," if head.count(",") >= 1 else None)
    if not delim:
        return None
    try:
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    except csv.Error:
        return None
    cols = [c.strip().lower() for c in rows[0]]
    ti = next((cols.index(c) for c in _TITLE_COLS if c in cols), None)
    ai = next((cols.index(c) for c in _ARTIST_COLS if c in cols), None)
    if ti is None or ai is None or ti == ai:
        return None
    out = []
    for r in rows[1:]:
        if len(r) <= max(ti, ai):
            continue
        title = r[ti].strip()
        artist = re.split(r"\s*[;/]\s*", r[ai].strip())[0].strip()
        if title and artist:
            out.append(f"{artist} - {title}")
        elif title:
            out.append(title)
    return out or None


_SMALL_WORDS = {"a", "an", "the", "of", "and", "or", "but", "in", "on", "at", "to", "for", "by", "vs", "with", "from"}


def _smart_case(part: str) -> str:
    """'the black sheep' -> 'The Black Sheep' (small words stay lower-case except the first one)."""
    words = part.split(" ")
    out = []
    for i, w in enumerate(words):
        if not w:
            out.append(w)
            continue
        if i > 0 and w in _SMALL_WORDS:
            out.append(w)
            continue
        out.append("/".join(seg[:1].upper() + seg[1:] for seg in w.split("/")))
    return " ".join(out)


def fix_case(line: str) -> str:
    """Only for lines typed entirely in lower case: give 'artist - title' normal capital letters.
    Lines that already contain a capital letter are left exactly as written."""
    if not line or line != line.lower() or not any(c.isalpha() for c in line):
        return line
    for sep in (" - ", " \u2013 ", " \u2014 "):
        if sep in line:
            a, t = line.split(sep, 1)
            return _smart_case(a.strip()) + sep + _smart_case(t.strip())
    return _smart_case(line)


def parse_song_lines(text: str) -> list[str]:
    structured = _structured_to_lines(text)
    if structured is not None:
        return structured
    songs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("===") or line.startswith("http"):
            continue
        if "  \u2192  " in line:
            line = line.split("  \u2192  ")[0].strip()
        songs.append(fix_case(line))
    return songs


def load_songs_from_file(path: str) -> list[str]:
    data = Path(path).read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):  # Apple Music on Windows can save UTF-16
        raw = data.decode("utf-16", errors="replace")
    else:
        raw = data.decode("utf-8-sig", errors="replace")
    return parse_song_lines(raw)


# -- Apple Music: read a PUBLIC shared playlist / album link (no sign-in) ----------------------------

def _apple_artist(obj) -> str:
    if isinstance(obj, dict):
        return str(obj.get("name") or "").strip()
    if isinstance(obj, list):
        return ", ".join(x for x in (_apple_artist(o) for o in obj) if x)
    return str(obj or "").strip()


def _apple_from_jsonld(html: str) -> tuple[str, list[str]]:
    """Songs from the page's built-in schema.org data (MusicPlaylist / MusicAlbum)."""
    name, songs = "", []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict):
                continue
            tracks = node.get("track") or node.get("tracks")
            if not isinstance(tracks, list) or not tracks:
                continue
            owner = _apple_artist(node.get("byArtist"))
            found = []
            for t in tracks:
                if not isinstance(t, dict):
                    continue
                title = str(t.get("name") or "").strip()
                artist = _apple_artist(t.get("byArtist")) or owner
                if title and artist:
                    found.append(f"{artist} - {title}")
            if len(found) > len(songs):
                songs, name = found, str(node.get("name") or "").strip()
    return name, songs


def _apple_from_server_data(html: str) -> list[str]:
    """Fallback: pull (title, artist) pairs out of the page's embedded app data."""
    m = re.search(r'<script[^>]*id="serialized-server-data"[^>]*>(.*?)</script>', html, re.S | re.I)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    out: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            title, artist = o.get("title"), o.get("artistName")
            if isinstance(title, str) and isinstance(artist, str) and title and artist and "contentDescriptor" in o:
                kind = ((o.get("contentDescriptor") or {}).get("kind") or "")
                if kind in ("song", ""):
                    line = f"{artist} - {title}"
                    if line not in out:
                        out.append(line)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def fetch_apple_playlist(url: str) -> tuple[str, list[str]]:
    """(name, ['Artist - Title', ...]) for a shared Apple Music playlist or album link.
    Only works for links anyone can open (Share > Copy Link). Raises ValueError with a plain message."""
    url = (url or "").strip().split()[0] if (url or "").strip() else ""
    if "music.apple.com" not in url.lower():
        raise ValueError("That doesn't look like an Apple Music link (it should contain music.apple.com).")
    url = re.sub(r"//embed\.music\.apple\.com", "//music.apple.com", url, flags=re.I)
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Apple Music said no (HTTP {e.code}). Is the playlist public (Share > Copy Link)?")
    except Exception as e:
        raise ValueError(f"Couldn't reach Apple Music ({e}). Check your internet connection.")
    name, songs = _apple_from_jsonld(html)
    if not songs:
        songs = _apple_from_server_data(html)
    if not name:
        mt = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html, re.I)
        if mt:
            import html as _h

            name = re.split(r"\s+(?:on|by)\s+Apple Music", _h.unescape(mt.group(1)))[0].strip(" \u200e\u200f-")
    if not songs:
        raise ValueError("I couldn't find any songs on that page. The playlist may be private, or Apple changed "
                         "its page. Try another export method (see the README).")
    return name, songs


# \u2500\u2500 Downloading (Bandcamp + YouTube, both via yt-dlp) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def ffmpeg_path() -> str:
    """Bundled ffmpeg first (inside the app / next to it), then whatever is on PATH."""
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, exe)
        if os.path.isfile(p):
            return p
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    p = os.path.join(base, exe)
    if os.path.isfile(p):
        return p
    return shutil.which("ffmpeg") or "ffmpeg"


def ytdlp_age_days() -> int | None:
    """How old the installed yt-dlp is (YouTube breaks old versions), or None if unknown."""
    try:
        from datetime import datetime

        ver = yt_dlp.version.__version__  # e.g. 2025.09.26
        d = datetime.strptime(".".join(ver.split(".")[:3]), "%Y.%m.%d")
        return (datetime.now() - d).days
    except Exception:
        return None


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180]


def have_ytdlp() -> bool:
    return yt_dlp is not None or shutil.which("yt-dlp") is not None


class _QuietLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _ffmpeg_location() -> str | None:
    ff = ffmpeg_path()
    if ff and ff != "ffmpeg":
        return os.path.dirname(ff)
    return None


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def _stop_hook(_d) -> None:
    """yt-dlp calls this while downloading; raising aborts the download."""
    if STOP_EVENT.is_set():
        raise _Stopped()


def _cleanup_partial(out_dir: str, safe: str) -> None:
    """Remove half-finished files for one song after a Stop."""
    try:
        has_mp3 = os.path.exists(os.path.join(out_dir, f"{safe}.mp3"))
        for name in os.listdir(out_dir):
            if not name.startswith(safe + "."):
                continue
            low = name.lower()
            if low.endswith((".part", ".ytdl", ".temp")) or (
                not has_mp3 and low.endswith((".jpg", ".jpeg", ".webp", ".png", ".webm", ".m4a", ".opus"))
            ):
                try:
                    os.remove(os.path.join(out_dir, name))
                except OSError:
                    pass
    except OSError:
        pass


_LAST_INFO: dict = {}  # metadata of the most recent yt-dlp download (used for cover repair)

# "Best available" keeps YouTube's original audio (M4A/AAC) instead of re-encoding to MP3.
QUALITY = {"best": False, "free": False, "jamendo_id": ""}  # HQ options stay off in SEVBY
HQ_SONGS: list[str] = []  # songs that came from YouTube in this run (for the "find better quality" file)


def hq_search_links(song: str) -> list[tuple[str, str]]:
    """Search pages where a better-quality copy can be bought (we only build links, nothing is fetched)."""
    q = urllib.parse.quote_plus(song)
    return [
        ("Bandcamp", f"https://bandcamp.com/search?q={q}"),
        ("Qobuz", f"https://www.qobuz.com/us-en/search?q={q}"),
        ("7digital", f"https://us.7digital.com/search?q={q}"),
    ]


def write_hq_links(out_dir: str, log) -> None:
    """Write a small text file with buy/search links for the songs that only came from YouTube."""
    if not HQ_SONGS:
        return
    path = os.path.join(out_dir, "SEVBY - find better quality.txt")
    lines = [
        "SEVBY - songs that came from YouTube (about 128-160 kbps at best).",
        "If you love one, these links search stores that sell lossless / 320 kbps copies.",
        "Buying from the artist on Bandcamp is the best way to support them.",
        "",
    ]
    for song in HQ_SONGS:
        lines.append(song)
        for name, url in hq_search_links(song):
            lines.append(f"  {name}: {url}")
        lines.append("")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log(f"{len(HQ_SONGS)} song(s) came from YouTube. Links to find better-quality copies: {path}")
    except OSError:
        pass


def _run_ff(args: list[str]):
    """Run the bundled ffmpeg quietly. Returns CompletedProcess or None if ffmpeg is missing."""
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        return subprocess.run(
            [ffmpeg_path(), "-hide_banner", *args],
            capture_output=True,
            timeout=90,
            creationflags=flags,
        )
    except Exception:
        return None


def _has_cover(mp3: str) -> bool:
    """True if the MP3 contains embedded art (ffmpeg lists it as a Video stream)."""
    r = _run_ff(["-i", mp3])
    if r is None:
        return True  # can't check \u2192 don't touch the file
    return "Video:" in (r.stderr or b"").decode("utf-8", errors="replace")


def _thumb_urls(info: dict | None) -> list[str]:
    if not info:
        return []
    urls: list[str] = []
    if info.get("thumbnail"):
        urls.append(info["thumbnail"])
    thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url")]
    thumbs.sort(key=lambda t: ((t.get("preference") or 0), (t.get("width") or 0)), reverse=True)
    for t in thumbs:
        if t["url"] not in urls:
            urls.append(t["url"])
    return urls[:5]


def _to_jpg(src: str) -> str | None:
    if src.lower().endswith((".jpg", ".jpeg")):
        return src
    dst = os.path.join(tempfile.gettempdir(), f"sevby_cover_{os.getpid()}.jpg")
    r = _run_ff(["-y", "-i", src, "-q:v", "2", dst])
    return dst if r is not None and r.returncode == 0 and os.path.isfile(dst) else None


def _find_or_fetch_cover(out_dir: str, safe: str, info: dict | None) -> str | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(out_dir, safe + ext)
        if os.path.isfile(p):
            jpg = _to_jpg(p)
            if jpg:
                return jpg
    for url in _thumb_urls(info):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": SIMPLE_UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
        except Exception:
            continue
        if len(data) < 1000:
            continue
        ext = ".webp" if data[:4] == b"RIFF" else (".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg")
        tmp = os.path.join(tempfile.gettempdir(), f"sevby_thumb_{os.getpid()}{ext}")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
        except OSError:
            continue
        jpg = _to_jpg(tmp)
        if jpg:
            return jpg
    return None


def _embed_cover(mp3: str, img: str) -> bool:
    tmp = mp3[:-4] + ".sevby-tmp.mp3"
    r = _run_ff([
        "-y", "-i", mp3, "-i", img,
        "-map", "0:a", "-map", "1:v", "-c", "copy",
        "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        tmp,
    ])
    ok = r is not None and r.returncode == 0 and os.path.isfile(tmp)
    if ok:
        try:
            os.replace(tmp, mp3)
            return True
        except OSError:
            pass
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except OSError:
        pass
    return False


def _ensure_cover(out_dir: str, safe: str, info: dict | None, log) -> None:
    """After a download: make sure the MP3 really has its cover art; repair it if not."""
    mp3 = os.path.join(out_dir, f"{safe}.mp3")
    if not os.path.isfile(mp3):
        return
    try:
        if not _has_cover(mp3):
            img = _find_or_fetch_cover(out_dir, safe, info)
            if img and _embed_cover(mp3, img):
                if log:
                    log("  Cover art was missing \u2014 added it.")
            elif log:
                log("  Note: no cover art could be found for this track.")
    finally:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = os.path.join(out_dir, safe + ext)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# Set by Sevbify: which audio to keep when saving the original (smaller files: a lower-bitrate original), and
# the MP3 quality when converting (yt-dlp/ffmpeg: a bitrate like "160" or a VBR level "0"-"9").
AUDIO_FORMAT_ORIGINAL = "bestaudio[ext=m4a]/bestaudio/best"
MP3_QUALITY = "0"


def _run_ytdlp_module(
    target: str, out_dir: str, safe: str, cookies: bool, embed: bool = True, original: bool = False
) -> tuple[bool, str]:
    opts = {
        "format": AUDIO_FORMAT_ORIGINAL if original else "bestaudio/best",
        "noplaylist": True,
        "outtmpl": os.path.join(out_dir, safe.replace("%", "%%") + ".%(ext)s"),
        "writethumbnail": embed,
        "postprocessors": [] if original else (
            [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": MP3_QUALITY},
                {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ]
            if embed
            else [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": MP3_QUALITY}]
        ),
        "quiet": True,
        "no_warnings": True,
        "logger": _QuietLogger(),
        "socket_timeout": 30,
        "retries": 3,
        "progress_hooks": [_stop_hook],
        "no_color": True,
    }
    loc = _ffmpeg_location()
    if loc:
        opts["ffmpeg_location"] = loc
    if cookies:
        opts["cookiesfrombrowser"] = ("chrome",)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=True)
        if isinstance(info, dict) and info.get("entries"):
            entries = [e for e in info["entries"] if e]
            info = entries[0] if entries else info
        _LAST_INFO["info"] = info if isinstance(info, dict) else None
        return True, ""
    except Exception as e:
        if STOP_EVENT.is_set():
            return False, "stopped"
        msg = _strip_ansi(str(e)).strip().splitlines()
        return False, (msg[-1] if msg else "unknown error")


def _run_ytdlp_cli(
    target: str, out_dir: str, safe: str, cookies: bool, embed: bool = True, original: bool = False
) -> tuple[bool, str]:
    out_template = os.path.join(out_dir, f"{safe}.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist", "--no-colors", "-x",
        "--audio-format", "mp3", "--audio-quality", "0",
    ]
    if embed:
        cmd += ["--embed-thumbnail", "--embed-metadata", "--convert-thumbnails", "jpg"]
    cmd += [
        "-o", out_template, target,
    ]
    loc = _ffmpeg_location()
    if loc:
        cmd.extend(["--ffmpeg-location", loc])
    if cookies:
        cmd.extend(["--cookies-from-browser", "chrome"])
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=240, creationflags=flags
        )
        if r.returncode == 0:
            return True, ""
        err = (r.stderr or r.stdout or "").strip().splitlines()
        return False, (err[-1] if err else "unknown error")
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except FileNotFoundError:
        return False, "yt-dlp not found \u2014 run: pip install -U yt-dlp"
    except Exception as e:
        return False, str(e)


def _download(
    target: str, out_dir: str, safe: str, allow_cookies: bool, log=None, embed: bool = True,
    original: bool = False,
) -> tuple[bool, str]:
    _LAST_INFO.clear()
    if yt_dlp is None:
        original = False  # keeping the original audio needs the yt-dlp module
    base = _run_ytdlp_module if yt_dlp is not None else _run_ytdlp_cli
    runner = lambda t, o, sf, ck, em: base(t, o, sf, ck, em, original)
    ok, err = runner(target, out_dir, safe, False, embed)
    if not ok and not STOP_EVENT.is_set() and any(k in err.lower() for k in ("403", "forbidden")):
        time.sleep(3)  # YouTube sometimes refuses one request; try once more
        ok, err = runner(target, out_dir, safe, False, embed)
    if not ok and not STOP_EVENT.is_set() and allow_cookies and any(
        k in err.lower() for k in ("sign in", "bot", "cookie", "age", "confirm", "403", "forbidden")
    ):
        ok, err2 = runner(target, out_dir, safe, True, embed)
        err = err2 or err
    if not ok and not STOP_EVENT.is_set() and _NET_ERR_RE.search(err or ""):
        for delay in (5, 15):
            if log:
                log(f"  Network problem \u2013 retrying in {delay} s\u2026")
            for _ in range(delay * 5):
                if STOP_EVENT.is_set():
                    break
                time.sleep(0.2)
            if STOP_EVENT.is_set():
                break
            ok, err = runner(target, out_dir, safe, False, embed)
            if ok or not _NET_ERR_RE.search(err or ""):
                break
        if not ok and _NET_ERR_RE.search(err or "") and log:
            log("  Tip: the internet connection dropped. Run the list again later.")
    if STOP_EVENT.is_set() and not ok:
        _cleanup_partial(out_dir, safe)
        err = "stopped"
    elif ok and embed and not original:
        _ensure_cover(out_dir, safe, _LAST_INFO.get("info"), log)
    return ok, err


def _already_exists(out_dir: str, safe: str) -> bool:
    return existing_song(out_dir, safe) is not None


# \u2500\u2500 Tags & cover art \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def meta_for(song: str) -> dict:
    """Tag info for a song: full Spotify details if we have them, else parsed from 'Artist - Title'."""
    if song in SONG_META:
        return SONG_META[song]
    artist, title = _split_query(song)
    meta = {"title": title}
    if artist:
        meta["artist"] = re.sub(r"\s*,\s*", ", ", artist)
    return meta


def _crop_box(src: str) -> tuple[int, int, int, int, int, int] | None:
    """Find black bars with ffmpeg's cropdetect. Returns (W, H, x, y, iw, ih) or None."""
    r = _run_ff(["-loop", "1", "-framerate", "10", "-t", "0.8", "-i", src,
                 "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"])
    if r is None:
        return None
    text = (r.stderr or b"").decode("utf-8", errors="replace")
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", text)
    size = re.search(r"Stream #\d+:\d+.*?Video:.*?, (\d{2,5})x(\d{2,5})", text)
    if not crops or not size:
        return None
    w, h, x, y = (int(v) for v in crops[-1])
    return w, h, x, y, int(size.group(1)), int(size.group(2))


def _square_jpg(src: str) -> str | None:
    """Make a square cover from a video thumbnail: trim black bars that are the same on both sides,
    then crop the centre square if the picture is nearly square, else show it whole on a black square."""
    dst = os.path.join(tempfile.gettempdir(), f"sevby_square_{os.getpid()}.jpg")
    vf = []
    box = _crop_box(src)
    cw = ch = None
    if box:
        w, h, x, y, iw, ih = box
        left, right, top, bottom = x, iw - (x + w), y, ih - (y + h)
        tx = x if (abs(left - right) <= 3 and left >= iw * 0.02) else 0
        ty = y if (abs(top - bottom) <= 3 and top >= ih * 0.02) else 0
        cw, ch = iw - 2 * tx, ih - 2 * ty
        if tx or ty:
            vf.append(f"crop={cw}:{ch}:{tx}:{ty}")
    if cw is None:
        r0 = _run_ff(["-i", src])
        m = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", (r0.stderr or b"").decode("utf-8", "replace")) if r0 else None
        if m:
            cw, ch = int(m.group(1)), int(m.group(2))
    if cw and ch:
        if cw / ch <= 1.25 and ch / cw <= 1.25:
            side = min(cw, ch)
            vf.append(f"crop={side}:{side}")
        else:
            side = max(cw, ch)
            vf.append(f"scale={side}:{side}:force_original_aspect_ratio=decrease,pad={side}:{side}:(ow-iw)/2:(oh-ih)/2:black")
    else:
        vf.append("crop=min(iw\\,ih):min(iw\\,ih)")
    r = _run_ff(["-y", "-i", src, "-vf", ",".join(vf), "-frames:v", "1", "-q:v", "2", dst])
    return dst if r is not None and r.returncode == 0 and os.path.isfile(dst) else None


def _fetch_image(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": SIMPLE_UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except Exception:
        return None
    if len(data) < 1000:
        return None
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else (".webp" if data[:4] == b"RIFF" else ".jpg")
    tmp = os.path.join(tempfile.gettempdir(), f"sevby_cover_dl_{os.getpid()}{ext}")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
    except OSError:
        return None
    return _to_jpg(tmp)


def _apply_tags(mp3: str, meta: dict, cover: str | None = None, wipe: bool = False) -> bool:
    """Write ID3 tags (and optionally a cover) into an MP3 without re-encoding."""
    tmp = mp3[:-4] + ".sevby-tmp.mp3"
    args = ["-y", "-i", mp3]
    if cover:
        args += ["-i", cover, "-map", "0:a", "-map", "1:v"]
    else:
        args += ["-map", "0"]  # keep the audio and any cover already inside
    args += ["-c", "copy", "-id3v2_version", "3", "-write_id3v1", "1"]
    if wipe:
        args += ["-map_metadata", "-1"]  # drop yt-dlp / YouTube junk tags
    track = meta.get("track") or 0
    tags = {
        "title": meta.get("title"),
        "artist": meta.get("artist"),
        "album_artist": meta.get("album_artist") or meta.get("artist"),
        "album": meta.get("album"),
        "date": meta.get("year"),
        "track": (f"{track}/{meta['track_total']}" if track and meta.get("track_total")
                  else (str(track) if track else None)),
    }
    for k, v in tags.items():
        if v:
            args += ["-metadata", f"{k}={v}"]
    if cover:
        args += ["-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)"]
    args.append(tmp)
    r = _run_ff(args)
    if r is not None and r.returncode == 0 and os.path.isfile(tmp):
        try:
            os.replace(tmp, mp3)
            return True
        except OSError:
            pass
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except OSError:
        pass
    return False


def _apply_tags_m4a(path: str, meta: dict, cover: str | None = None) -> bool:
    """Write MP4/M4A tags (and optionally a cover) without re-encoding the audio."""
    tmp = path[:-4] + ".sevby-tmp.m4a"
    args = ["-y", "-i", path]
    if cover:
        args += ["-i", cover, "-map", "0:a", "-map", "1:v", "-disposition:v:0", "attached_pic"]
    else:
        args += ["-map", "0:a"]
    args += ["-c", "copy", "-map_metadata", "-1"]  # drop YouTube junk tags
    track = meta.get("track") or 0
    tags = {
        "title": meta.get("title"),
        "artist": meta.get("artist"),
        "album_artist": meta.get("album_artist") or meta.get("artist"),
        "album": meta.get("album"),
        "date": meta.get("year"),
        "track": (f"{track}/{meta['track_total']}" if track and meta.get("track_total")
                  else (str(track) if track else None)),
    }
    for k, v in tags.items():
        if v:
            args += ["-metadata", f"{k}={v}"]
    args.append(tmp)
    r = _run_ff(args)
    if r is not None and r.returncode == 0 and os.path.isfile(tmp):
        try:
            os.replace(tmp, path)
            return True
        except OSError:
            pass
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except OSError:
        pass
    return False


def _finalize_original(out_dir: str, safe: str, info: dict | None, meta: dict, log) -> str:
    """Tag a YouTube download that kept its original audio. Returns a short quality label.
    M4A is tagged as-is. Anything else (Opus/WebM) is converted to MP3 like the standard mode."""
    src = None
    for ext in ("m4a", "mp4", "webm", "opus", "ogg", "mp3"):
        cand = os.path.join(out_dir, f"{safe}.{ext}")
        if os.path.isfile(cand):
            src = cand
            break
    if not src:
        return "?"
    abr = (info or {}).get("abr")
    kbps = f" ~{int(round(abr))} kbps" if abr else ""
    ext = src.rsplit(".", 1)[-1].lower()
    if ext in ("m4a", "mp4"):
        if ext == "mp4":
            new = os.path.join(out_dir, f"{safe}.m4a")
            try:
                os.replace(src, new)
                src = new
            except OSError:
                pass
        try:
            cover = _fetch_image(meta["cover_url"]) if meta.get("cover_url") else None
            if not cover:
                raw = _find_or_fetch_cover(out_dir, safe, info)
                cover = _square_jpg(raw) if raw else None
            if not _apply_tags_m4a(src, meta, cover):
                log("  Note: couldn't write tags for this track.")
            elif not cover:
                log("  Note: no cover art could be found for this track.")
        finally:
            _remove_loose_images(out_dir, safe)
        return f"YouTube original audio (M4A/AAC{kbps})"
    # Not M4A: convert to MP3 so tags and cover work everywhere
    mp3 = os.path.join(out_dir, f"{safe}.mp3")
    r = _run_ff(["-y", "-i", src, "-vn", "-c:a", "libmp3lame", "-q:a", "0", mp3])
    if r is not None and r.returncode == 0 and os.path.isfile(mp3):
        try:
            os.remove(src)
        except OSError:
            pass
        _finalize_youtube(out_dir, safe, info, meta, log)
        return "YouTube, converted to MP3 (no M4A version was available)"
    return "YouTube (kept as " + ext + ", could not convert)"


def _remove_loose_images(out_dir: str, safe: str) -> None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(out_dir, safe + ext)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _finalize_youtube(out_dir: str, safe: str, info: dict | None, meta: dict, log) -> None:
    """Give a YouTube download proper tags and a square cover (Spotify's if we have it)."""
    mp3 = os.path.join(out_dir, f"{safe}.mp3")
    if not os.path.isfile(mp3):
        return
    try:
        cover = _fetch_image(meta["cover_url"]) if meta.get("cover_url") else None
        if not cover:
            raw = _find_or_fetch_cover(out_dir, safe, info)
            cover = _square_jpg(raw) if raw else None
        if not _apply_tags(mp3, meta, cover, wipe=True):
            log("  Note: couldn't write tags for this track.")
        elif not cover:
            log("  Note: no cover art could be found for this track.")
    finally:
        _remove_loose_images(out_dir, safe)


# \u2500\u2500 YouTube matching \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

_UNWANTED = (
    "live", "remix", "cover", "karaoke", "instrumental", "sped up", "slowed", "reverb",
    "nightcore", "8d", "bass boosted", "mashup", "reaction", "acoustic", "tribute",
    "extended", "1 hour", "10 hours", "full album", "loop",
)


def _words(s: str) -> list[str]:
    return re.findall(r"\w+", (s or "").lower().replace("&", " and "))


def score_youtube_result(entry: dict, query: str, meta: dict, index: int = 0) -> float:
    """Higher = more likely the right recording. Uses length, title, channel, and 'bad version' words."""
    title = (entry.get("title") or "")
    chan = (entry.get("channel") or entry.get("uploader") or "")
    t_low = title.lower()
    wanted = " ".join([query, meta.get("title") or "", meta.get("artist") or ""]).lower()
    score = -0.5 * index

    # Length vs. the real track length (Spotify) - the strongest signal
    target = meta.get("duration") or 0
    dur = entry.get("duration")
    if not dur:
        score -= 20  # live streams / unknown length
    elif target:
        diff = abs(dur - target)
        score += 40 if diff <= 3 else 28 if diff <= 8 else 12 if diff <= 15 else -15 if diff <= 40 else -45
    else:
        score += -25 if dur > 600 else (-10 if dur < 60 else 0)

    # Title / artist words
    song_title = meta.get("title") or _split_query(query)[1]
    tw = set(_words(song_title))
    if tw:
        score += 25 * len(tw & set(_words(title))) / len(tw)
    aw = set(_words(meta.get("artist") or _split_query(query)[0]))
    if aw:
        score += 15 * len(aw & set(_words(title + " " + chan))) / len(aw)

    # Official-ish sources
    if chan.lower().endswith("- topic"):
        score += 20
    if "official audio" in t_low:
        score += 6
    elif "official" in t_low:
        score += 2

    # Wrong versions (unless the user actually asked for them)
    penalty = 0
    for w in _UNWANTED:
        if re.search(r"\b" + re.escape(w) + r"\b", t_low) and not re.search(
            r"\b" + re.escape(w) + r"\b", wanted
        ):
            penalty += 30
    score -= min(penalty, 60)
    return score


def rank_youtube_results(entries: list[dict], query: str, meta: dict) -> list[tuple[float, dict]]:
    scored = [(score_youtube_result(e, query, meta, i), e) for i, e in enumerate(entries)]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def search_youtube_candidates(query: str, n: int = 8) -> list[dict]:
    """Top YouTube search results (title, length, channel) without downloading anything."""
    if yt_dlp is None:
        return []
    opts = {
        "quiet": True, "no_warnings": True, "logger": _QuietLogger(), "no_color": True,
        "extract_flat": True, "skip_download": True, "socket_timeout": 30,
    }
    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            return [e for e in (info or {}).get("entries") or [] if e and (e.get("id") or e.get("url"))]
        except Exception:
            if STOP_EVENT.is_set():
                return []
            time.sleep(2)
    return []


def _fmt_len(sec) -> str:
    try:
        sec = int(sec)
        return f"{sec // 60}:{sec % 60:02d}"
    except Exception:
        return "?:??"


def download_bandcamp_mp3(bc_url: str, query: str, out_dir: str, log) -> bool:
    """Download a Bandcamp track page as MP3. Returns True on success."""
    safe = sanitize_filename(query)
    if _already_exists(out_dir, safe):
        log(f"  SKIP (exists): {safe}")
        return True
    ok, err = _download(bc_url, out_dir, safe, allow_cookies=False, log=log)
    if ok:
        log(f"  OK (Bandcamp) \u2192 {safe}.mp3" + ("  [Bandcamp stream, 128 kbps MP3]" if QUALITY["best"] else ""))
    elif err == "stopped":
        log("  Stopped.")
    else:
        log(f"  Bandcamp download failed: {err}")
    return ok


def _alt_youtube_queries(artist: str, title: str) -> list[str]:
    """Other ways to word the YouTube search when 'Artist - Title' finds nothing usable."""
    a, t = (artist or "").strip(), clean_title(title or "") or (title or "").strip()
    if not t:
        return []
    out = []
    if a:
        out += [f"{a} {t} official audio", f"{t} {a}", f"{a} - Topic {t}"]
    else:
        out += [f"{t} official audio"]
    return out


def download_youtube_mp3(query: str, out_dir: str, log, use_cookies: bool = True) -> bool:
    safe = sanitize_filename(query)
    if _already_exists(out_dir, safe):
        log(f"  SKIP (exists): {safe}")
        return True
    meta = dict(meta_for(query))
    if query not in SONG_META and meta.get("artist"):
        it = itunes_lookup(meta["artist"], meta.get("title") or "", query)
        if it:
            for k, v in it.items():
                if v and not meta.get(k) and not k.endswith("_canon"):
                    meta[k] = v
            apply_canon(meta, it)

    # Pick the best-matching video (right length, not a live/remix version) instead of the first hit.
    targets: list[str] = []
    ranked = rank_youtube_results(search_youtube_candidates(query), query, meta)
    # Drop videos whose title shares (almost) nothing with the wanted song title.
    _tw = set(_words(meta.get("title") or _split_query(query)[1]))
    if _tw:
        ranked = [(sc, e) for sc, e in ranked
                  if len(_tw & set(_words((e.get("title") or "")))) / len(_tw) >= 0.5]
    if not ranked:
        # Short or common titles ("Duel") can be crowded out of the first results: try other wordings, and
        # only accept a video whose title or channel also names the artist.
        _art = meta.get("artist") or _split_query(query)[0]
        _aw = set(_words(_art))
        _ti = meta.get("title") or _split_query(query)[1]
        for q2 in _alt_youtube_queries(_art, _ti):
            if STOP_EVENT.is_set():
                break
            r2 = rank_youtube_results(search_youtube_candidates(q2, 15), query, meta)
            r2 = [(sc, e) for sc, e in r2
                  if _tw and len(_tw & set(_words(e.get("title") or ""))) / len(_tw) >= 0.5
                  and _aw and len(_aw & set(_words((e.get("title") or "") + " " + (e.get("channel") or e.get("uploader") or "")))) / len(_aw) >= 0.5]
            if r2:
                log("  (found with a different search wording)")
                ranked = r2
                break
    if not ranked:
        log("  FAIL: no matching video found on YouTube")
        return False
    for score, entry in ranked[:2]:
        url = entry.get("url") or ""
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={entry.get('id')}"
        if not targets:
            log(
                f"  Match: {entry.get('title')} [{_fmt_len(entry.get('duration'))}]"
                + (f" \u2014 {entry.get('channel') or entry.get('uploader')}" if (entry.get('channel') or entry.get('uploader')) else "")
                + ("" if score >= 20 else "  (best guess)")
            )
        targets.append(url)

    original = bool(QUALITY["best"]) and yt_dlp is not None
    ok, err = False, "no result"
    for target in targets:
        ok, err = _download(target, out_dir, safe, allow_cookies=use_cookies, log=log, embed=False,
                            original=original)
        if ok or STOP_EVENT.is_set():
            break
    if ok and original:
        label = _finalize_original(out_dir, safe, _LAST_INFO.get("info"), meta, log)
        final = next((f"{safe}.{e}" for e in ("m4a", "mp3") if os.path.isfile(os.path.join(out_dir, f"{safe}.{e}"))), safe)
        log(f"  OK \u2192 {final}  [{label}]")
        HQ_SONGS.append(query)
    elif ok:
        _finalize_youtube(out_dir, safe, _LAST_INFO.get("info"), meta, log)
        log(f"  OK \u2192 {safe}.mp3")
        HQ_SONGS.append(query)
    elif err == "stopped":
        log("  Stopped.")
    else:
        log(f"  FAIL: {err}")
        if "403" in err or "forbidden" in err.lower():
            log("  Tip: YouTube changes often \u2014 update yt-dlp (pip install -U yt-dlp) and rebuild SEVBY.")
    return ok


# -- Matching rules shared with the Android app: Bandcamp choice, iTunes album info, skip rules ------

VERSION_WORDS = ("remix", "live", "instrumental", "acoustic", "cover", "edit", "mix", "version", "karaoke")
_COMPILATION_RE = re.compile(
    r"compilation|\bvol\b|volume|various|sampler|presents|best of|collection|anthology|\b\d{2,3}\b", re.I)
_NET_ERR_RE = re.compile(
    r"getaddrinfo|name or service not known|temporary failure|timed out|timeout|connection reset|"
    r"connection aborted|network is unreachable|remote end closed|urlopen error|connection refused|"
    r"no route to host|server disconnected", re.I)


def _alnum(s: str) -> str:
    """Letters and digits only, lower-case (so 'M.A.D.E.S' == 'mades')."""
    return re.sub(r"[\W_]+", "", (s or "").lower())


def clean_title(t: str) -> str:
    """Drop (feat. ...), (Remastered), (Original Mix), (Explicit) ... and a trailing '- 2011 Remaster'."""
    t = re.sub(
        r"[\(\[][^\)\]]*\b(feat|ft|featuring|remaster|remastered|original mix|original version|explicit|clean)\b[^\)\]]*[\)\]]",
        " ", t or "", flags=re.I)
    t = re.sub(r"\s+-\s+(\d{4}\s+)?remaster(ed)?(\s+\d{4})?\s*$", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def artists_of(artist: str) -> list[str]:
    parts = re.split(r"\s*[,&]\s*|\s+(?:feat\.?|ft\.?|featuring|x|and)\s+", artist or "", flags=re.I)
    out = [a for a in (_alnum(x) for x in parts) if a]
    return out or ([_alnum(artist)] if _alnum(artist) else [])


def version_set(text: str) -> set[str]:
    low = re.sub(r"\boriginal\s+(mix|version)\b", " ", (text or "").lower())
    return {w for w in VERSION_WORDS if re.search(r"\b" + w + r"\b", low)}


_LEAD_ARTICLE_RE = re.compile(r"^\s*(the|an|a)\s+", re.I)


def _title_key(t: str) -> str:
    """Letters and digits of a title, ignoring (feat. ...) / (Remastered) parts and a leading The / A / An."""
    return _alnum(_LEAD_ARTICLE_RE.sub("", clean_title(t)))


def _title_eq(a: str, b: str) -> bool:
    return bool(_title_key(a)) and _title_key(a) == _title_key(b)


def _strip_artist_prefix(name: str, artists: list[str]) -> str:
    m = re.match(r"^(.*?)\s+[-\u2013\u2014]\s+(.+)$", name or "")
    if m and any(a and (a in _alnum(m.group(1)) or _alnum(m.group(1)) in a) for a in artists if _alnum(m.group(1))):
        return m.group(2)
    return name or ""


def _host_label(url: str) -> str:
    m = re.match(r"https?://([^./]+)\.", url or "")
    return m.group(1).lower() if m else ""


_BC_BADVER_RE = re.compile(
    r"remake|re-?record|tribute|\bcovers?\b|bootleg|karaoke|\bdubs?\b|made famous|originally (performed|by)|"
    r"in the style of|\bversions?\b|rerecord|lullaby|8-?bit|piano (version|tribute)", re.I)


def _plain(s: str) -> str:
    """Lower-case letters and digits only, accents removed ('Sigur R\u00f3s' -> 'sigurros')."""
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").replace("&", " and "))
    return re.sub(r"[\W_]+", "", "".join(c for c in s if unicodedata.category(c) != "Mn").lower())


def _host_is_artist(url: str, cands: list[str]) -> bool:
    """True if the page's web address belongs to the artist: artist.bandcamp.com, or the artist's own
    domain such as store.sigurros.com. Pages run by DJs, fans or compilation accounts that merely credit
    the artist (a remix, a cover, a re-upload) are not accepted."""
    m = re.match(r"https?://([^/]+)", url or "")
    if not m:
        return False
    labels = m.group(1).lower().split(".")
    names = [labels[0]]
    if len(labels) >= 3 and not m.group(1).lower().endswith("bandcamp.com"):
        names.append(labels[-2])
    names = [_plain(n) for n in names if n]
    variants = []
    for a in cands:
        for v in (_plain(a), _plain(a.replace("&", " "))):
            if v and v not in variants:
                variants.append(v)
    for a in variants:
        for h in names:
            if h and (a == h or ((a in h or h in a) and min(len(a), len(h)) / max(len(a), len(h)) >= 0.75)):
                return True
    return False


def bc_choose(results: list[dict], query: str) -> dict | None:
    """Pick the right Bandcamp TRACK: same title, same artist, same kind of version."""
    artist, title = _split_query(query)
    if not artist or not title:
        return None  # a line without an artist is never matched (it goes to YouTube)
    want_artists = artists_of(artist)
    want_ver = version_set(title)
    pool: list[tuple[float, dict, bool]] = []
    for i, r in enumerate(results):
        url = r.get("url") or ""
        if "/track/" not in url:
            continue
        name = _strip_artist_prefix(r.get("name") or "", want_artists)
        if not _title_eq(name, title):
            continue
        band = _alnum(r.get("band_name") or "")
        # The page must belong to the artist itself (not "Queen Mary band", a tribute or a bootleg page):
        # the band name must equal the artist, or at least be mostly made of it.
        cands = want_artists + [_alnum(artist)]
        if not band or not any(
                a and (a == band or ((a in band or band in a) and min(len(a), len(band)) / max(len(a), len(band)) >= 0.75))
                for a in cands):
            continue
        if version_set(name) != want_ver:
            continue
        own = _host_is_artist(url, cands + [artist])
        album_txt = r.get("album_name") or ""
        if _BC_BADVER_RE.search(name + " " + album_txt) and not _BC_BADVER_RE.search(query):
            continue  # remake / tribute / cover / bootleg / "dubs" release
        if re.search(r"\blive\b|unplugged|in concert", album_txt, re.I) and "live" not in want_ver:
            continue
        score = -0.001 * i
        host = _host_label(url)
        if host and any(host == a or host in a or a in host for a in want_artists if len(a) > 2):
            score += 10
        album = r.get("album_name") or ""
        if album:
            score += -5 if _COMPILATION_RE.search(album) else 2
        pool.append((score, r, own))
    # 1. The artist's own page (artist.bandcamp.com or the artist's domain) wins.
    for score, r, own in sorted(pool, key=lambda x: x[0], reverse=True):
        if own:
            return r
    # 2. Another account (a label, a DJ, a fan, a compilation) is only trusted when its album is the
    #    same album Apple lists for this song. This stops re-uploads, covers and "various" pages that
    #    merely credit the artist.
    others = sorted((x for x in pool if not x[2]), key=lambda x: x[0], reverse=True)
    if others:
        try:
            it = itunes_lookup(artist, title, query)
        except Exception:
            it = None
        real_album = (it or {}).get("album") or ""
        if real_album:
            for score, r, own in others:
                if _title_eq(r.get("album_name") or "", real_album):
                    return r
    return None


_ITUNES_CACHE: dict = {}


def _device_country() -> str:
    try:
        import locale

        loc = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "")
        m = re.search(r"[_-]([A-Za-z]{2})$", loc)
        if m:
            return m.group(1).upper()
        names = {"australia": "AU", "united states": "US", "united kingdom": "GB", "canada": "CA",
                 "germany": "DE", "france": "FR", "new zealand": "NZ", "ireland": "IE"}
        for k, v in names.items():
            if k in loc.lower():
                return v
    except Exception:
        pass
    return "US"


def itunes_choose(results: list[dict], artist: str, title: str, line: str) -> dict | None:
    want_artists = artists_of(artist)
    want_ver = version_set(title)
    wants_live = "live" in want_ver
    best, best_score = None, -999.0
    for i, r in enumerate(results):
        if not _title_eq(r.get("trackName", ""), title):
            continue
        ra = _alnum(r.get("artistName", ""))
        if not ra or not any(a in ra or ra in a for a in want_artists):
            continue
        if version_set(r.get("trackName", "")) != want_ver:
            continue
        album = r.get("collectionName") or ""
        if re.search(r"\blive\b|unplugged|in concert", album, re.I) and not wants_live:
            continue
        score = 0.0
        cart = (r.get("collectionArtistName") or "")
        if cart and (cart.lower().startswith("various") or not any(
                a in _alnum(cart) or _alnum(cart) in a for a in want_artists)):
            score -= 10
        if _COMPILATION_RE.search(album):
            score -= 5
        if re.search(r"expanded|deluxe|anniversary|remaster|reissue|special edition|bonus", album, re.I):
            score -= 1
        if album and not re.search(r"\s-\s(single|ep)\s*$", album, re.I):
            score += 2
        score -= 0.0001 * i
        rd = (r.get("releaseDate") or "")[:10]
        key = (score, "".join(reversed(rd)) if False else 0)
        # ties go to the earliest release
        if score > best_score or (abs(score - best_score) < 0.001 and rd and best and rd < (best.get("releaseDate") or "9")[:10]):
            best, best_score = r, score
    return best


def apply_canon(meta: dict, it: dict | None) -> None:
    """Use Apple's spelling and capitals for the title / artist tags when they only differ from the typed
    line in capitals, punctuation or a leading 'The' ('kataklysm - black sheep' -> Kataklysm / The Black Sheep)."""
    if not it:
        return
    t, a = it.get("title_canon"), it.get("artist_canon")
    if t and meta.get("title") and _title_eq(t, meta["title"]):
        meta["title"] = t
    if a and meta.get("artist") and _alnum(a) == _alnum(meta["artist"]):
        meta["artist"] = a


def canonical_line(song: str) -> str:
    """'kataklysm - black sheep' / 'KATAKLYSM - The BLACK sheep' -> 'Kataklysm - The Black Sheep' when Apple Music
    knows the song and the only differences are capitals, punctuation or a leading 'The'. Otherwise unchanged."""
    if song in SONG_META or STOP_EVENT.is_set():
        return song
    artist, title = _split_query(song)
    if not artist or not title:
        return song
    try:
        it = itunes_lookup(artist, title, song)
    except Exception:
        return song
    meta = {"artist": artist, "title": title}
    apply_canon(meta, it)
    if meta["artist"] == artist and meta["title"] == title:
        return song
    return f"{meta['artist']} - {meta['title']}"


def itunes_lookup(artist: str, title: str, line: str = "") -> dict | None:
    """Album / year / track / cover / length for a song from the iTunes Search API (no key needed)."""
    key = (_alnum(artist), _alnum(title))
    if key in _ITUNES_CACHE:
        return _ITUNES_CACHE[key]
    found = None
    countries = [_device_country()] + (["US"] if _device_country() != "US" else [])
    for cc in countries:
        if STOP_EVENT.is_set():
            break
        q = urllib.parse.urlencode({"term": f"{artist} {clean_title(title)}", "media": "music",
                                    "entity": "song", "limit": 25, "country": cc})
        data = None
        for delay in (0, 5, 15):
            if delay:
                time.sleep(delay)
            data = _free_json("https://itunes.apple.com/search?" + q)
            if data is not None:
                break
        r = itunes_choose((data or {}).get("results") or [], artist, title, line)
        if r:
            album = re.sub(r"\s-\s(Single|EP)\s*$", "", r.get("collectionName") or "", flags=re.I).strip()
            art = r.get("artworkUrl100") or ""
            found = {
                "album": album or None,
                "year": (r.get("releaseDate") or "")[:4] or None,
                "track": r.get("trackNumber") or None,
                "track_total": r.get("trackCount") or None,
                "duration": (r.get("trackTimeMillis") or 0) / 1000.0 or None,
                "cover_url": re.sub(r"/\d+x\d+bb", "/1000x1000bb", art) if art else None,
                "title_canon": clean_title(r.get("trackName") or "") or None,
                "artist_canon": (r.get("artistName") or "").strip() or None,
            }
            break
    _ITUNES_CACHE[key] = found
    return found


def read_tags(path: str) -> dict:
    """Read album / date / track from a file with the bundled ffmpeg (it prints them when probing)."""
    r = _run_ff(["-i", path])
    out = {}
    if r is None:
        return out
    text = (r.stderr or b"").decode("utf-8", errors="replace")
    for key in ("album", "date", "track", "title", "artist"):
        m = re.search(r"^\s+" + key + r"\s*:\s*(.+)$", text, re.M | re.I)
        if m:
            out[key] = m.group(1).strip()
    return out


MIN_BYTES = 100 * 1024


def existing_song(out_dir: str, safe: str) -> str | None:
    """A finished copy of this song already in the folder (>= 100 KB). Smaller files are leftovers of an
    interrupted run: they are deleted so the song gets downloaded again."""
    found = None
    for ext in ("mp3", "m4a", "flac"):
        p = os.path.join(out_dir, f"{safe}.{ext}")
        if os.path.isfile(p):
            try:
                if os.path.getsize(p) >= MIN_BYTES:
                    found = found or p
                else:
                    os.remove(p)
            except OSError:
                pass
    return found


def _file_seconds(path: str) -> float | None:
    """Length of an audio file in seconds (read with the bundled ffmpeg), or None."""
    r = _run_ff(["-i", path])
    if r is None:
        return None
    text = (r.stderr or b"").decode("utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _expected_seconds(song: str) -> float | None:
    """The real length of the song, from Spotify / Apple details or an iTunes lookup (None if unknown)."""
    meta = meta_for(song)
    dur = meta.get("duration")
    if not dur and meta.get("artist"):
        try:
            it = itunes_lookup(meta["artist"], meta.get("title") or "", song)
        except Exception:
            it = None
        dur = (it or {}).get("duration")
    try:
        return float(dur) if dur else None
    except (TypeError, ValueError):
        return None


def _bandcamp_wrong_length(out_dir: str, safe: str, song: str, log) -> bool:
    """True (and the file is deleted) when the downloaded Bandcamp track is clearly a different version
    of the song (remix, edit, slowed, live ...) judging by its length. Unknown lengths are accepted."""
    path = os.path.join(out_dir, f"{safe}.mp3")
    if not os.path.isfile(path):
        return False
    want = _expected_seconds(song)
    got = _file_seconds(path)
    if not want or not got:
        return False
    if abs(got - want) <= max(12.0, 0.05 * want):
        return False
    log(f"  Bandcamp copy is {_fmt_len(got)} but the real song is {_fmt_len(want)} - "
        "probably a remix or other version, skipping it")
    try:
        os.remove(path)
    except OSError:
        pass
    _remove_loose_images(out_dir, safe)
    return True


def retag_bandcamp(out_dir: str, safe: str, query: str) -> tuple[str, str]:
    """Title and artist always come from the user's line. Album / year / track: Bandcamp, then iTunes.
    Returns (album, year) for the log."""
    mp3 = os.path.join(out_dir, f"{safe}.mp3")
    if not os.path.isfile(mp3):
        return "", ""
    meta = dict(meta_for(query))
    tags = read_tags(mp3)
    album = tags.get("album") or meta.get("album") or ""
    year = (tags.get("date") or "")[:4] or meta.get("year") or ""
    track = meta.get("track")
    total = meta.get("track_total")
    if not track and tags.get("track"):
        m = re.match(r"(\d+)(?:\s*/\s*(\d+))?", tags["track"])
        if m:
            track, total = int(m.group(1)), (int(m.group(2)) if m.group(2) else None)
    it = None
    if meta.get("artist") and (not album or not year or query not in SONG_META):
        it = itunes_lookup(meta.get("artist") or "", meta.get("title") or "", query)
        if query not in SONG_META:
            apply_canon(meta, it)
    if not album or not year:
        if it:
            album = album or it.get("album") or ""
            year = year or it.get("year") or ""
            track = track or it.get("track")
            total = total or it.get("track_total")
    meta.update(album=album or meta.get("title"), year=year or None, track=track, track_total=total)
    _apply_tags(mp3, meta, None, wipe=True)
    return (album or meta.get("title") or ""), year


def _fmt_album(album: str, year: str) -> str:
    if album and year:
        return f"{album} ({year})"
    return album or year or ""


def _src_result(res: dict) -> str:
    return res.get("note") or ""


def process_song(song: str, out_dir: str, opts: dict, state: dict, say, step=lambda _t: None) -> dict:
    """One song, start to finish. Used by the window and the command-line version.
    opts: use_bc, use_yt, free.  state: seen (set), bc_errors (int), bandcamp_down (bool).
    Returns {'status': ok|skip|dup|fail, 'source': ..., 'note': ..., 'path': ...}."""
    typed_safe = sanitize_filename(song)
    if typed_safe.lower() in state.setdefault("seen", set()):
        return {"status": "dup", "source": None, "note": "listed twice"}
    step("Checking the folder\u2026")
    if existing_song(out_dir, typed_safe):
        state.setdefault("seen", set()).add(typed_safe.lower())
        return {"status": "skip", "source": None, "note": "already downloaded"}
    # file name = the official spelling (Apple Music), however the line was typed
    song = canonical_line(song)
    safe = sanitize_filename(song)
    key = safe.lower()
    if key in state.setdefault("seen", set()) or typed_safe.lower() in state["seen"]:
        return {"status": "dup", "source": None, "note": "listed twice"}
    state["seen"].add(key)
    state["seen"].add(typed_safe.lower())

    if existing_song(out_dir, safe):
        return {"status": "skip", "source": None, "note": "already downloaded"}

    # 1. Bandcamp
    bc_note = ""
    if opts.get("use_bc"):
        step("Searching Bandcamp\u2026")
        if DEBUG.get("bc_blocked"):
            res = {"found": False, "error": "pretend-blocked (test switch)"}
        else:
            res = search_bandcamp(song, use_api=not state.get("bandcamp_down"))
        if res.get("found") and res.get("url"):
            state["bc_errors"] = 0
            say(f"  -> Bandcamp: {res['url']}")
            step("Downloading from Bandcamp\u2026")
            if download_bandcamp_mp3(res["url"], song, out_dir, say):
                if _bandcamp_wrong_length(out_dir, safe, song, say):
                    bc_note = " (Bandcamp copy was a different version)"
                else:
                    step("Looking up album info\u2026")
                    album, year = retag_bandcamp(out_dir, safe, song)
                    return {"status": "ok", "source": "Bandcamp", "path": existing_song(out_dir, safe) or "",
                            "note": "Bandcamp" + (f" \u00b7 {_fmt_album(album, year)}" if album or year else "")}
            else:
                if STOP_EVENT.is_set():
                    return {"status": "fail", "source": None, "note": "stopped"}
                bc_note = " (Bandcamp download failed)"
        elif res.get("error"):
            state["bc_errors"] = state.get("bc_errors", 0) + 1
            say(f"  -> Bandcamp search failed: {res['error']}")
            bc_note = " (Bandcamp blocked)"
            if state["bc_errors"] >= 3 and not state.get("bandcamp_down"):
                state["bandcamp_down"] = True
                say("  (Bandcamp search keeps refusing - trying artist pages only from now on)")
        else:
            state["bc_errors"] = 0
            say("  -> not on Bandcamp")
            bc_note = " (not on Bandcamp)"

    # 2. YouTube
    if opts.get("use_yt") and not STOP_EVENT.is_set():
        step("Searching YouTube\u2026")
        if download_youtube_mp3(song, out_dir, say):
            p = existing_song(out_dir, safe) or ""
            tags = read_tags(p) if p else {}
            album = tags.get("album") or ""
            year = (tags.get("date") or "")[:4]
            extra = _fmt_album(album, year)
            return {"status": "ok", "source": "YouTube", "path": p,
                    "note": "YouTube" + (f" \u00b7 {extra}" if extra else "") + bc_note}
        if STOP_EVENT.is_set():
            return {"status": "fail", "source": None, "note": "stopped"}
        return {"status": "fail", "source": None,
                "note": "not found on YouTube" if "not on" in bc_note or not opts.get("use_bc") else "couldn't be downloaded"}
    if opts.get("use_bc"):
        return {"status": "fail", "source": None, "note": bc_note.strip(" ()") or "not on Bandcamp"}
    return {"status": "fail", "source": None, "note": "no source selected"}



# -- Small web helper (used for iTunes album lookups) ------------------------------------------------

_FREE_UA = "SEVBY/" + VERSION + " (https://github.com/Obamna1234/sevby)"


def _http_get(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _FREE_UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _free_json(url: str):
    data = _http_get(url)
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", errors="replace"))
    except ValueError:
        return None



# -- Colours (same layout as the Android app, in green) --------------------------------------------
C_BG = "#141416"
C_SURFACE = "#1E1E22"
C_TEXT = "#F2F2F2"
C_MUTED = "#9A9AA2"
C_ACCENT = "#34E58A"
C_ACCENT_H = "#2BC474"
C_ON_ACCENT = "#141416"
C_ERR = "#FF6B6B"
C_ERR_BG = "#C94A4A"

# Test switches (About -> Advanced)
DEBUG = {"bc_blocked": False}


# -- yt-dlp version / updates ---------------------------------------------------------------------
def ytdlp_version() -> str:
    try:
        return str(yt_dlp.version.__version__)
    except Exception:
        return "not installed"


def ver_tuple(v: str) -> tuple:
    """'2026.08.19.1' -> (2026, 8, 19, 1), compared number by number."""
    out = []
    for part in re.split(r"[.\-]", str(v or "")):
        m = re.match(r"\d+", part)
        out.append(int(m.group()) if m else 0)
    return tuple(out)


def ytdlp_latest_tag() -> str | None:
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
            headers={"User-Agent": "SEVBY", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")).get("tag_name") or None
    except Exception:
        return None


APP_REPO_URL = "https://github.com/Obamna1234/sevby"
UPDATE_PRERELEASES = False  # HQ is a beta; the plain SEVBY build ignores pre-releases


def app_ver_cmp(a: str, b: str) -> int:
    """Compare two app versions. 1.0.1 > 1.0.0; a finished 1.0.0 beats 1.0.0-beta; 0.10.0 > 0.9.2."""
    def split(v):
        v = str(v or "").strip().lower().lstrip("v").split(" ")[0]
        core, _, pre = v.partition("-")
        nums = [int(x) if x.isdigit() else 0 for x in core.split(".")]
        parts = [x for x in re.split(r"[.\-]", pre) if x]
        return nums, parts
    ca, pa = split(a)
    cb, pb = split(b)
    n = max(len(ca), len(cb))
    ca += [0] * (n - len(ca))
    cb += [0] * (n - len(cb))
    if ca != cb:
        return 1 if ca > cb else -1
    if not pa and not pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    rank = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3}
    for i in range(max(len(pa), len(pb))):
        if i >= len(pa):
            return -1
        if i >= len(pb):
            return 1
        x, y = pa[i], pb[i]
        if x.isdigit() and y.isdigit():
            if int(x) != int(y):
                return 1 if int(x) > int(y) else -1
        elif x.isdigit() != y.isdigit():
            return 1 if x.isdigit() else -1
        elif x != y:
            rx, ry = rank.get(x, 2), rank.get(y, 2)
            return 1 if (rx, x) > (ry, y) else -1
    return 0


def app_pick_release(releases, include_pre: bool = False):
    """Newest desktop release from GitHub's /releases list: skips drafts, android-v... releases,
    releases with no files yet (still building) and (unless asked) pre-releases."""
    best = None
    plat = "windows" if sys.platform.startswith("win") else "macos" if sys.platform == "darwin" else "linux"
    for r in releases if isinstance(releases, list) else []:
        try:
            tag = str(r.get("tag_name") or "")
            if not tag or r.get("draft") or tag.lower().startswith("android"):
                continue
            if r.get("prerelease") and not include_pre:
                continue
            assets = [a for a in (r.get("assets") or []) if isinstance(a, dict)]
            if not assets:
                continue
            ver = tag.lstrip("vV")
            if not re.match(r"\d", ver):
                continue
            url = ""
            for a in assets:
                name = str(a.get("name") or "").lower()
                if plat in name or (plat == "windows" and name.endswith(".exe")):
                    url = a.get("browser_download_url") or ""
                    break
            rel = {"version": ver, "page": r.get("html_url") or APP_REPO_URL + "/releases", "url": url}
            if best is None or app_ver_cmp(ver, best["version"]) > 0:
                best = rel
        except Exception:
            continue
    return best


def app_latest_release():
    """(checked, release). checked is False when GitHub couldn't be reached."""
    try:
        path = APP_REPO_URL.split("github.com/")[1]
        req = urllib.request.Request(
            f"https://api.github.com/repos/{path}/releases?per_page=30",
            headers={"User-Agent": "SEVBY", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return True, app_pick_release(data, UPDATE_PRERELEASES)
    except Exception:
        return False, None


def download_ytdlp_update(tag: str) -> tuple[bool, str]:
    """Download the official yt-dlp release file into the user's folder. It is picked up on next start."""
    try:
        YTDLP_UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        dest = YTDLP_UPDATE_DIR / "yt-dlp"
        tmp = YTDLP_UPDATE_DIR / "yt-dlp.part"
        url = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp"
        req = urllib.request.Request(url, headers={"User-Agent": "SEVBY"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        import zipfile

        if not zipfile.is_zipfile(tmp):
            tmp.unlink(missing_ok=True)
            return False, "The download wasn't a valid yt-dlp file. Try again later."
        os.replace(tmp, dest)
        return True, "ok"
    except Exception as e:
        return False, f"Couldn't download the update ({e})."


def diagnostics_text() -> str:
    lines = [
        f"{APP_NAME} {VERSION}",
        f"Python {sys.version.split()[0]} on {sys.platform}" + (" (packaged app)" if getattr(sys, "frozen", False) else ""),
        f"yt-dlp {ytdlp_version()}" + (f"  [updated copy: {YTDLP_ACTIVE}]" if YTDLP_ACTIVE else "  [bundled copy]"),
        f"ffmpeg: {ffmpeg_path()}",
    ]
    try:
        out = subprocess.run([ffmpeg_path(), "-version"], capture_output=True, text=True, timeout=10,
                             creationflags=0x08000000 if os.name == "nt" else 0).stdout
        lines.append("  " + (out.splitlines()[0] if out else "no output"))
    except Exception as e:
        lines.append(f"  ffmpeg failed to run: {e}")
    lines.append(f"Edition: standard (MP3)")
    lines.append(f"Drag and drop: {'yes' if _HAS_DND else 'no'}")
    lines.append(f"Log file: {LOG_PATH}")
    return "\n".join(lines)


def network_test_text() -> str:
    tests = [
        ("Bandcamp", "https://bandcamp.com/"),
        ("YouTube", "https://www.youtube.com/"),
        ("iTunes", "https://itunes.apple.com/search?term=test&limit=1"),
        ("GitHub", "https://api.github.com/"),
    ]
    out = []
    for name, url in tests:
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                out.append(f"{name}: OK ({int((time.time() - t0) * 1000)} ms)")
        except urllib.error.HTTPError as e:
            out.append(f"{name}: reachable (HTTP {e.code})")
        except Exception as e:
            out.append(f"{name}: FAILED ({str(e)[:50]})")
    return "\n".join(out)


