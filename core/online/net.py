"""Small HTTP client for Sevbify's online features.

- Respects the Settings -> "Online features" switch (raises OnlineDisabled).
- Caches JSON responses and images on disk, so things you have looked at
  before still show when you are offline.
- Spaces out requests per website so we stay within each service's limits.
- Never used on the UI thread: call it from a background task.
"""
import hashlib
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "Sevbify/5.0 (desktop music player; +https://github.com/Obamna1234/Sevbify)"


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
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()
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
        self._throttle(url)
        try:
            if self._opener is not None:
                data = self._opener(url)
            else:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                           "Accept": "application/json, */*"})
                with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as r:
                    data = r.read()
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

    def download(self, url, dest_path, progress=None, cancelled=lambda: False, chunk=64 * 1024):
        """Download a file (only used for sources that allow downloading)."""
        if not self.enabled():
            raise OnlineDisabled("Online features are switched off in Settings.")
        self._throttle(url)
        tmp = dest_path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout * 3, context=self._ctx) as r, open(tmp, "wb") as f:
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
        for kind in ("json", "images"):
            folder = os.path.join(self.cache_dir, kind)
            for name in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass
