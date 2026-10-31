"""Plays songs from your own music server (Jellyfin, Nextcloud/WebDAV) without giving VLC your sign-in.

VLC can't send a sign-in header, and a sign-in put in the address can end up in logs. So Sevbify runs a tiny
relay on this computer only (127.0.0.1, a random port, a random secret in every address): VLC asks the relay,
and the relay asks your server with the sign-in in a header. Nothing outside this computer can reach the relay,
and other programs on it can't guess its addresses.
"""
import http.server
import secrets
import shutil
import threading
import urllib.error
import urllib.request

from . import servers

_lock = threading.Lock()
_server = None
_secret = secrets.token_hex(16)
_songs = {}              # id -> (url, headers)


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):        # never print the addresses
        pass

    def _target(self):
        parts = self.path.split("/")
        if len(parts) != 3 or not secrets.compare_digest(parts[1], _secret):
            return None
        return _songs.get(parts[2])

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        target = self._target()
        if target is None:
            self.send_error(404)
            return
        url, headers = target
        extra = {"User-Agent": servers.CLIENT, **headers}
        if self.headers.get("Range"):
            extra["Range"] = self.headers["Range"]
        req = urllib.request.Request(url, headers=extra, method="HEAD" if head else "GET")
        try:
            resp = servers._open(req, 30)
        except urllib.error.HTTPError as e:
            self.send_error(e.code)
            return
        except OSError:
            self.send_error(502)
            return
        with resp:
            self.send_response(resp.status)
            for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified"):
                if resp.headers.get(name):
                    self.send_header(name, resp.headers[name])
            self.end_headers()
            if not head:
                try:
                    shutil.copyfileobj(resp, self.wfile, 64 * 1024)
                except OSError:
                    pass                   # VLC stopped or seeked


def _start():
    global _server
    with _lock:
        if _server is None:
            _server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            _server.daemon_threads = True
            threading.Thread(target=_server.serve_forever, daemon=True, name="sevbify-server-relay").start()
    return _server.server_address[1]


def local_address(server, track):
    """A 127.0.0.1 address VLC can play for this server song (no sign-in in it)."""
    url, headers = servers.playable(server, track)
    port = _start()
    song_id = secrets.token_hex(8)
    with _lock:
        if len(_songs) > 200:
            _songs.clear()
        _songs[song_id] = (url, headers)
    return f"http://127.0.0.1:{port}/{_secret}/{song_id}"


def stop():
    global _server
    with _lock:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
            _server = None
        _songs.clear()
