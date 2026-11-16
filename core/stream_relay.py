"""Streams a song's web link to the player through Sevbify, the same way Sevbify's downloads fetch it.

Seen on a home connection on Windows (beta.47 log): YouTube refused the song links when the player (VLC) or a
plain Python request asked for them, while the very same link downloaded fine through yt-dlp, so every song
had to be saved to a file before it could start (16-20 s). yt-dlp's own networking is what YouTube accepts, so
the player is given a 127.0.0.1 address instead, and this relay fetches the audio through yt-dlp, piece by
piece as the player asks (seeking works: the player's Range requests are passed on).

Only this computer can reach the relay (127.0.0.1, random port), every address carries a random secret, and
only https links on the song sites' own servers are relayed.
"""
import http.server
import secrets
import shutil
import threading
import urllib.parse

_lock = threading.Lock()
_server = None
_secret = secrets.token_hex(16)
_links = {}              # id -> (url, headers)
ALLOWED_HOSTS = ("googlevideo.com", "sndcdn.com", "soundcloud.cloud", "bcbits.com", "youtube.com")


def allowed(url):
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def _open(url, headers):
    """The response, fetched with yt-dlp's networking (what its downloads use)."""
    from core import downloader
    e = downloader.engine()
    if e.yt_dlp is None:
        import urllib.request
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30)
    from yt_dlp.networking import Request
    ydl = e.yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "socket_timeout": 30})
    return ydl.urlopen(Request(url, headers=headers))


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):        # never print the addresses
        pass

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        parts = self.path.split("/")
        target = None
        if len(parts) == 3 and secrets.compare_digest(parts[1], _secret):
            target = _links.get(parts[2])
        if target is None:
            self.send_error(404)
            return
        url, headers = target
        extra = dict(headers)
        if self.headers.get("Range"):
            extra["Range"] = self.headers["Range"]
        try:
            resp = _open(url, extra)
        except Exception as e:
            code = getattr(e, "status", None) or getattr(getattr(e, "response", None), "status", None) or 502
            self.send_error(int(code) if 400 <= int(code) < 600 else 502)
            return
        try:
            status = getattr(resp, "status", 200) or 200
            hdrs = getattr(resp, "headers", {}) or {}
            self.send_response(status)
            for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                value = hdrs.get(name)
                if value:
                    self.send_header(name, value)
            if not hdrs.get("Accept-Ranges"):
                self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if not head:
                try:
                    shutil.copyfileobj(resp, self.wfile, 64 * 1024)
                except OSError:
                    pass                   # the player stopped or seeked
        finally:
            try:
                resp.close()
            except Exception:
                pass


def _start():
    global _server
    with _lock:
        if _server is None:
            _server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            _server.daemon_threads = True
            threading.Thread(target=_server.serve_forever, daemon=True, name="sevbify-stream-relay").start()
    return _server.server_address[1]


def local_address(url, headers=None):
    """A 127.0.0.1 address the player can open for this link, or "" if the link isn't one we relay."""
    if not allowed(url):
        return ""
    port = _start()
    link_id = secrets.token_hex(8)
    with _lock:
        if len(_links) > 50:
            _links.clear()
        _links[link_id] = (url, dict(headers or {}))
    return f"http://127.0.0.1:{port}/{_secret}/{link_id}"


def stop():
    global _server
    with _lock:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
            _server = None
        _links.clear()
