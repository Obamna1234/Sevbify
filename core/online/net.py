"""Small HTTP client for Sevbify's online features.

- Respects the Settings -> "Online features" switch (raises OnlineDisabled).
- Caches JSON responses and images on disk, so things you have looked at
  before still show when you are offline.
- Spaces out requests per website so we stay within each service's limits.
- Never used on the UI thread: call it from a background task.
"""
import hashlib
import http.client
import ipaddress
import json
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "Sevbify/5.0 (desktop music player; +https://github.com/Obamna1234/Sevbify)"


# Only web addresses are ever opened. Links come from outside (podcast feeds, imported playlists), and a
# "file:" link would otherwise read a file on this computer.
WEB_SCHEMES = ("http", "https")
MAX_RESPONSE_BYTES = 40 * 1024 * 1024     # pages, feeds, JSON and pictures; anything bigger isn't one of them


def is_web_url(url):
    """True for an http(s) address with a host (what Sevbify may open or fetch)."""
    try:
        p = urllib.parse.urlparse((url or "").strip())
    except ValueError:
        return False
    return p.scheme.lower() in WEB_SCHEMES and bool(p.netloc)


LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".localdomain", ".intranet", ".corp")


def is_outside_link(url):
    """A web link that doesn't name a device on your own network or this computer, judged from the link alone
    (no lookup, so it's quick enough to check everywhere: songs, episodes, covers from feeds and files)."""
    if not is_web_url(url):
        return False
    try:
        host = (urllib.parse.urlparse(url.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if not host or host == "localhost" or host.endswith(LOCAL_SUFFIXES) or "." not in host and ":" not in host:
        return False
    try:
        ipaddress.ip_address(host.strip("[]"))
        return is_public_ip(host.strip("[]"))     # written as an address
    except ValueError:
        pass
    if host.replace(".", "").isdigit() or host.startswith("0x"):
        return False                         # odd number forms (decimal, hex): refused, never a real site
    return True


_HOST_OK = {}             # host -> (public?, when checked)


def is_public_host(host):
    """False for an address on your own network or computer (192.168.x.x, 10.x, 127.0.0.1, 169.254.x.x, ...).
    Links from outside (podcast feeds, imported files, web answers) must never make Sevbify reach your router,
    printer or other devices at home."""
    host = (host or "").strip("[]").lower()
    if not host or host == "localhost" or host.endswith((".local", ".lan", ".home.arpa", ".internal")):
        return False
    hit = _HOST_OK.get(host)
    if hit and time.time() - hit[1] < 600:
        return hit[0]
    try:
        addrs = {info[4][0].split("%")[0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        # Can't look it up: only allowed when a proxy does the looking up; otherwise refused (and not remembered,
        # so it is tried again next time).
        return _using_proxy()
    ok = bool(addrs) and all(is_public_ip(a) for a in addrs)
    _HOST_OK[host] = (ok, time.time())
    return ok


def is_public_ip(a):
    """An address on the open internet (not your home network, this computer, carrier-NAT/Tailscale, ...)."""
    try:
        ip = ipaddress.ip_address(str(a).split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _using_proxy():
    return any(os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"))


class _CheckedHTTPS(urllib.request.HTTPSHandler):
    """Checks the address actually connected to, so a website can't answer "public" first and "your router"
    when the connection is made (DNS rebinding)."""

    def https_open(self, req):
        return self.do_open(_checked(http.client.HTTPSConnection), req, context=self._context)


class _CheckedHTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_checked(http.client.HTTPConnection), req)


def _checked(base):
    class Conn(base):
        def connect(self):
            super().connect()
            if _using_proxy() or getattr(self, "_tunnel_host", None):
                return                      # connected to your proxy; it reaches the site
            try:
                peer = self.sock.getpeername()[0]
            except OSError:
                return
            if not is_public_ip(peer):
                self.sock.close()
                raise OSError("That link points to a device on your own network, so Sevbify didn't open it.")
    return Conn


def check_public_url(url):
    if not is_web_url(url):
        raise ServiceError("Only web (http/https) addresses can be opened.")
    if not is_public_host(urllib.parse.urlparse(url).hostname):
        raise ServiceError("That link points to a device on your own network, so Sevbify didn't open it.")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another public web address (never file:, ftp: or your own network)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = urllib.parse.urljoin(req.full_url, newurl)
        if not is_web_url(newurl) or not is_public_host(urllib.parse.urlparse(newurl).hostname):
            raise urllib.error.HTTPError(newurl, code, "redirect refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class OfflineError(Exception):
    """No connection (or the service could not be reached) and nothing cached."""


class OnlineDisabled(OfflineError):
    """The user switched online features off in Settings."""


class ServiceError(Exception):
    """The service answered, but with an error (bad key, not found, limit reached…)."""


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class NetClient:
    # Minimum seconds between requests to the same host.
    MIN_INTERVAL = {"api.deezer.com": 0.12, "ws.audioscrobbler.com": 0.25,
                    "musicbrainz.org": 1.05, "en.wikipedia.org": 0.1,
                    "archive.org": 0.2, "api.jamendo.com": 0.2}

    def __init__(self, cache_dir, enabled=lambda: True, timeout=12, opener=None):
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.timeout = timeout
        self._opener = opener          # tests inject a fake opener: (url) -> bytes
        self._ctx = _ssl_context()
        self._web = urllib.request.build_opener(_CheckedHTTPS(context=self._ctx), _CheckedHTTP, _SafeRedirect)
        self._lock = threading.Lock()
        self._last_request = {}
        self.online = None             # None = unknown, True/False after a request
        self.last_error = ""
        os.makedirs(os.path.join(cache_dir, "json"), exist_ok=True)
        os.makedirs(os.path.join(cache_dir, "images"), exist_ok=True)

    # ------------------------------------------------------------------
    @staticmethod
    def build_url(url, params=None):
        if not params:
            return url
        return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})

    def _cache_path(self, kind, url, ext):
        h = hashlib.sha1(url.encode("utf-8"), usedforsecurity=False).hexdigest()   # a file name, not security
        return os.path.join(self.cache_dir, kind, h + ext)

    def _throttle(self, url):
        host = urllib.parse.urlparse(url).hostname or ""
        gap = self.MIN_INTERVAL.get(host, 0.05)
        with self._lock:
            wait = self._last_request.get(host, 0) + gap - time.monotonic()
            self._last_request[host] = max(time.monotonic(), self._last_request.get(host, 0) + gap)
        if wait > 0:
            time.sleep(wait)

    def _fetch(self, url):
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        if not is_web_url(url):
            raise ServiceError("Only web (http/https) addresses can be opened.")
        self._throttle(url)
        try:
            if self._opener is not None:
                data = self._opener(url)
            else:
                check_public_url(url)
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                           "Accept": "application/json, */*"})
                with self._web.open(req, timeout=self.timeout) as r:
                    data = r.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ServiceError(f"{urllib.parse.urlparse(url).hostname} sent far more than expected")
            self.online = True
            self.last_error = ""
            return data
        except urllib.error.HTTPError as e:
            self.online = True            # we reached the server
            raise ServiceError(f"HTTP {e.code} from {urllib.parse.urlparse(url).hostname}") from e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            self.online = False
            self.last_error = str(getattr(e, "reason", e))
            raise OfflineError(f"Can't reach {urllib.parse.urlparse(url).hostname}: {self.last_error}") from e

    # ------------------------------------------------------------------
    def get_json(self, url, params=None, ttl=24 * 3600, use_cache=True):
        """GET a JSON document. Fresh cache is used first; stale cache is the
        fallback when the network is unavailable."""
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        full = self.build_url(url, params)
        path = self._cache_path("json", full, ".json")
        cached = None
        if use_cache and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if time.time() - cached.get("t", 0) < ttl:
                    return cached["data"]
            except (OSError, ValueError):
                cached = None
        try:
            data = json.loads(self._fetch(full).decode("utf-8"))
        except OnlineDisabled:
            raise                      # switched off: show nothing online, not even cached
        except OfflineError:
            if cached is not None:     # just offline: last known answer is better than nothing
                return cached["data"]
            raise
        except ValueError as e:
            raise ServiceError(f"Unexpected reply from {urllib.parse.urlparse(full).hostname}") from e
        if use_cache:
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"t": time.time(), "data": data}, f)
                os.replace(tmp, path)
            except OSError:
                pass
        return data

    def get_text(self, url, params=None, ttl=3600):
        """GET a web page as text (cached like JSON; the cache is used when offline)."""
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        full = self.build_url(url, params)
        path = self._cache_path("pages", full, ".html")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        try:
            text = self._fetch(full).decode("utf-8", errors="replace")
        except OfflineError:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            raise
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        return text

    def cached_image(self, url):
        """The already-downloaded picture for `url`, or None (never goes online)."""
        if not url:
            return None
        path = self._cache_path("images", url, ".img")
        return path if os.path.exists(path) else None

    def get_image(self, url, ttl=60 * 24 * 3600):
        """Download an image (cover art, artist photo) and return the local file path."""
        if not url:
            return None
        path = self._cache_path("images", url, ".img")
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            return path
        try:
            data = self._fetch(url)
        except OnlineDisabled:
            raise
        except OfflineError:
            if os.path.exists(path):
                return path
            raise
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return path

    MAX_DOWNLOAD_BYTES = 3 * 1024 ** 3      # an episode or chapter is never bigger (a full day of audio is ~1 GB)

    def download(self, url, dest_path, progress=None, cancelled=lambda: False, chunk=64 * 1024):
        """Download a file (only used for sources that allow downloading)."""
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        if not is_web_url(url):
            raise ServiceError("Only web (http/https) addresses can be downloaded.")
        check_public_url(url)
        self._throttle(url)
        tmp = dest_path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._web.open(req, timeout=self.timeout * 3) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    if cancelled():
                        raise InterruptedError("Download cancelled")
                    block = r.read(chunk)
                    if not block:
                        break
                    f.write(block)
                    done += len(block)
                    if done > self.MAX_DOWNLOAD_BYTES:
                        raise OSError("the file is far bigger than an episode can be")
                    if progress:
                        progress(done, total)
            os.replace(tmp, dest_path)
            return dest_path
        except (urllib.error.URLError, OSError) as e:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if isinstance(e, InterruptedError):
                raise
            raise OfflineError(f"Download failed: {getattr(e, 'reason', e)}") from e

    def clear_cache(self):
        """Settings → Clear cache: every saved answer, picture and page (feeds, imported playlist pages)."""
        for kind in ("json", "images", "pages"):
            folder = os.path.join(self.cache_dir, kind)
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass
