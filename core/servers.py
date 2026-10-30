"""Your own music servers: Jellyfin and Nextcloud (or any WebDAV server). No UI code.

Privacy and safety:
- Sevbify talks only to the server address you type. Nothing goes through anyone else.
- Jellyfin: your password is used once to sign in, then only the sign-in token is kept (you can revoke it in
  Jellyfin's Dashboard → Devices). Nextcloud: use an app password (Settings → Security → "Create new app
  password"), which you can revoke at any time; it's kept only on this device and never put in playlists, profile
  files or logs.
- Only https:// addresses, except plain http:// on your own network (192.168.x.x, 10.x.x.x, *.local ...).
- A server song is saved in playlists by server id + item, never with the token or password in it.
"""
import base64
import ipaddress
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from core.online.models import OnlineTrack

CLIENT = "Sevbify"
AUDIO_EXT = {"mp3", "m4a", "aac", "flac", "ogg", "opus", "wav", "wma", "aiff", "aif", "alac"}
MAX_SONGS = 20000
SOURCES = ("jellyfin", "webdav")


class ServerError(Exception):
    pass


# --- addresses ---------------------------------------------------------------------------------------------
def _private_host(host):
    host = (host or "").strip("[]").lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".lan") or host.endswith(".home.arpa"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def clean_address(url):
    """The server's base address, checked: https anywhere, http only on your own network."""
    url = (url or "").strip().rstrip("/")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    if not p.hostname or p.username or p.password:
        raise ServerError("Type the server's address, like https://music.example.com (no name or password in it).")
    if p.scheme.lower() == "http" and not _private_host(p.hostname):
        raise ServerError("Use https:// for a server on the internet (plain http would send your login unprotected). "
                          "http:// is fine for a server on your own network.")
    return f"{p.scheme.lower()}://{p.netloc}{p.path.rstrip('/')}"


def _same_server(base, url):
    a, b = urllib.parse.urlparse(base), urllib.parse.urlparse(url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


# --- HTTP ---------------------------------------------------------------------------------------------------
def _request(url, method="GET", headers=None, body=None, timeout=20, opener=None, limit=50_000_000):
    if opener is not None:
        return opener(method, url, headers or {}, body)
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": CLIENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(limit + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ServerError("The server didn't accept the sign-in (check the name and password).") from e
        raise ServerError(f"The server answered HTTP {e.code}.") from e
    except (urllib.error.URLError, OSError) as e:
        raise ServerError(f"Couldn't reach the server ({getattr(e, 'reason', e)}).") from e
    if len(data) > limit:
        raise ServerError("The server sent far more than expected.")
    return data


# --- Jellyfin -----------------------------------------------------------------------------------------------
def _jf_auth(device_id, token=""):
    value = (f'MediaBrowser Client="{CLIENT}", Device="{CLIENT}", DeviceId="{device_id}", Version="1"'
             + (f', Token="{token}"' if token else ""))
    return {"Authorization": value, "X-Emby-Authorization": value}


def jellyfin_sign_in(address, username, password, opener=None):
    """{"type", "url", "user", "user_id", "token", "device_id", "name"}: the password itself isn't kept."""
    base = clean_address(address)
    device = uuid.uuid4().hex
    body = json.dumps({"Username": username, "Pw": password}).encode()
    data = json.loads(_request(base + "/Users/AuthenticateByName", "POST",
                               {**_jf_auth(device), "Content-Type": "application/json"}, body, opener=opener))
    token, user = data.get("AccessToken") or "", data.get("User") or {}
    if not token or not user.get("Id"):
        raise ServerError("Jellyfin didn't return a sign-in.")
    return {"id": uuid.uuid4().hex[:12], "type": "jellyfin", "url": base, "user": username,
            "user_id": str(user["Id"]), "token": token, "device_id": device,
            "name": (data.get("ServerId") and f"Jellyfin ({urllib.parse.urlparse(base).hostname})") or "Jellyfin"}


def _jf_songs(server, opener=None):
    base, out, start = server["url"], [], 0
    while start < MAX_SONGS:
        q = urllib.parse.urlencode({"IncludeItemTypes": "Audio", "Recursive": "true", "StartIndex": start,
                                    "Limit": 500, "SortBy": "AlbumArtist,Album,ParentIndexNumber,IndexNumber",
                                    "Fields": "RunTimeTicks,AlbumId"})
        data = json.loads(_request(f"{base}/Users/{urllib.parse.quote(server['user_id'])}/Items?{q}",
                                   headers=_jf_auth(server["device_id"], server["token"]), opener=opener))
        items = data.get("Items") or []
        for it in items:
            if not it.get("Id"):
                continue
            artist = it.get("AlbumArtist") or ", ".join(it.get("Artists") or []) or "Unknown Artist"
            album_id = it.get("AlbumId") or it["Id"]
            out.append(OnlineTrack(title=it.get("Name") or "Unknown", artist=artist, album=it.get("Album") or "",
                                   duration_ms=int((it.get("RunTimeTicks") or 0) // 10_000), source="jellyfin",
                                   source_id=it["Id"], page_url=server["id"],
                                   stream_url=f"{base}/Audio/{it['Id']}/stream?static=true",
                                   cover_url=f"{base}/Items/{album_id}/Images/Primary?maxHeight=300"))
        start += len(items)
        if not items or start >= int(data.get("TotalRecordCount") or 0):
            break
    return out


# --- Nextcloud / WebDAV -------------------------------------------------------------------------------------
def webdav_address(address, username, folder=""):
    """Nextcloud: https://cloud.example.com → https://cloud.example.com/remote.php/dav/files/<user>/<folder>."""
    base = clean_address(address)
    if "/remote.php/" not in base and "/dav" not in base.lower():
        base = f"{base}/remote.php/dav/files/{urllib.parse.quote(username)}"
    folder = (folder or "").strip("/")
    return base + ("/" + "/".join(urllib.parse.quote(p) for p in folder.split("/")) if folder else "")


def _basic(server):
    raw = f"{server['user']}:{server['password']}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def webdav_connect(address, username, app_password, folder="", opener=None):
    url = webdav_address(address, username, folder)
    server = {"id": uuid.uuid4().hex[:12], "type": "webdav", "url": url, "user": username, "password": app_password,
              "name": f"Nextcloud ({urllib.parse.urlparse(url).hostname})"}
    _propfind(server, url, opener=opener)                # checks the address and the sign-in
    return server


_DAV = "{DAV:}"


def _propfind(server, url, opener=None):
    body = (b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:getcontenttype/>'
            b'</d:prop></d:propfind>')
    data = _request(url if url.endswith("/") else url + "/", "PROPFIND",
                    {**_basic(server), "Depth": "1", "Content-Type": "application/xml"}, body, opener=opener)
    if b"<!DOCTYPE" in data[:2000] or b"<!ENTITY" in data[:5000]:
        raise ServerError("The server's answer wasn't a normal folder listing.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ServerError("The server's answer wasn't a folder listing (is the address right?).") from e
    out = []
    for r in root.iter(_DAV + "response"):
        href = (r.findtext(_DAV + "href") or "").strip()
        is_dir = r.find(f".//{_DAV}resourcetype/{_DAV}collection") is not None
        if href:
            out.append((urllib.parse.urljoin(url, href), is_dir))
    return out


def _guess(name, parents):
    base = os.path.splitext(name)[0]
    clean = re.sub(r"^\s*\d{1,3}\s*[-._)]?\s*", "", base).strip()
    if " - " in clean:
        a, t = clean.split(" - ", 1)
        return a.strip(), t.strip()
    artist = parents[-2] if len(parents) >= 2 else (parents[0] if parents else "Unknown Artist")
    return artist, clean or base


def _webdav_songs(server, opener=None):
    root = server["url"].rstrip("/") + "/"
    out, todo, seen = [], [(root, [])], set()
    while todo and len(out) < MAX_SONGS and len(seen) < 5000:
        url, parents = todo.pop(0)
        if url in seen or len(parents) > 8:
            continue
        seen.add(url)
        for href, is_dir in _propfind(server, url, opener=opener):
            if not _same_server(root, href) or not href.startswith(root):
                continue                                   # never follow links to other places
            if href.rstrip("/") == url.rstrip("/"):
                continue
            name = urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])
            if is_dir:
                todo.append((href if href.endswith("/") else href + "/", parents + [name]))
            elif name.rsplit(".", 1)[-1].lower() in AUDIO_EXT:
                artist, title = _guess(name, parents)
                out.append(OnlineTrack(title=title, artist=artist, album=parents[-1] if len(parents) >= 2 else "",
                                       source="webdav", source_id=href[len(root):], page_url=server["id"],
                                       stream_url=href))
    return out


# --- shared -------------------------------------------------------------------------------------------------
def songs(server, opener=None):
    if server.get("type") == "jellyfin":
        return _jf_songs(server, opener)
    if server.get("type") == "webdav":
        return _webdav_songs(server, opener)
    raise ServerError("Unknown kind of server.")


def find(servers, track):
    """The saved server a server song belongs to (its page_url holds the server's id), or None."""
    if getattr(track, "source", "") not in SOURCES:
        return None
    return next((s for s in servers if s.get("id") == track.page_url), None)


def headers_for(server):
    if server["type"] == "jellyfin":
        return {"X-Emby-Token": server["token"]}
    return _basic(server)


def playable(server, track, for_vlc=False):
    """(url, headers) to stream a server song. VLC can't send custom headers, so for the computer app the
    sign-in goes in the address instead (it stays inside this computer: it's never saved or logged)."""
    url = track.stream_url
    if not _same_server(server["url"], url):
        raise ServerError("That song doesn't belong to this server.")
    if not for_vlc:
        return url, headers_for(server)
    if server["type"] == "jellyfin":
        return url + ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(server["token"]), {}
    p = urllib.parse.urlparse(url)
    cred = urllib.parse.quote(server["user"], safe="") + ":" + urllib.parse.quote(server["password"], safe="")
    return urllib.parse.urlunparse(p._replace(netloc=f"{cred}@{p.netloc}")), {}


def download(server, track, out_dir, limit=1_500_000_000, opener=None):
    """Save one of the server's songs into out_dir/<Artist>/ as "Artist - Title.ext". Returns the path."""
    from core import downloader
    url, headers = playable(server, track)
    path_ext = os.path.splitext(urllib.parse.urlparse(track.source_id if server["type"] == "webdav" else "")[2])[1]
    ext = path_ext.lower().lstrip(".") if path_ext.lower().lstrip(".") in AUDIO_EXT else ""
    folder = os.path.join(out_dir, downloader.artist_folder(track.artist))
    os.makedirs(folder, exist_ok=True)
    base = downloader.song_line(track.artist, track.title).replace("/", "-").replace("\\", "-")[:150]
    tmp = os.path.join(folder, base + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": CLIENT, **headers})
    try:
        with (opener(url, headers) if opener else urllib.request.urlopen(req, timeout=60)) as r, open(tmp, "wb") as f:
            ctype = (getattr(r, "headers", {}) or {}).get("Content-Type", "") or ""
            got = 0
            while True:
                block = r.read(256 * 1024)
                if not block:
                    break
                got += len(block)
                if got > limit:
                    raise ServerError("The song is far bigger than expected.")
                f.write(block)
        if not ext:
            ext = {"audio/mpeg": "mp3", "audio/flac": "flac", "audio/x-flac": "flac", "audio/mp4": "m4a",
                   "audio/aac": "m4a", "audio/ogg": "ogg", "audio/opus": "opus", "audio/wav": "wav",
                   "audio/x-wav": "wav"}.get(ctype.split(";")[0].strip().lower(), "mp3")
        final = os.path.join(folder, f"{base}.{ext}")
        os.replace(tmp, final)
        return final
    except urllib.error.URLError as e:
        raise ServerError(f"Couldn't download from the server ({getattr(e, 'reason', e)}).") from e
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def public(server):
    """A server's details without its secret (for lists on screen)."""
    return {k: v for k, v in server.items() if k not in ("token", "password", "device_id")}
