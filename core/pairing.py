"""Pair a phone with this computer by scanning a QR code, then send songs and folders either way (same Wi-Fi only).

Privacy and safety, in short:
- Nothing goes through the internet or any server: the phone connects straight to this computer on your own network.
  Only local-network addresses may connect (see LOCAL_NETWORKS); everything else is refused.
- Everything is encrypted (see pair_crypto). The QR code holds a one-time code that works once, for 5 minutes,
  and only while the "Pair a phone" card is open; a phone that scanned it gets its own key for later, which you can
  remove at any time (Settings → Your phone).
- Files are only saved after you accept them on the receiving side, and only what you accepted: each offered file
  once, never more bytes than offered, and only when there is room on the disk. Only music files (and their cover
  pictures / lyrics / playlists) are taken, with safe file names, inside the folder for that phone, never
  overwriting anything.
- Someone else on the network can't tie it up: a connection has 10 seconds in all to prove it has the key, at most
  two unproven connections per address, and they never take the places of paired phones.

Messages (JSON frames, see pair_crypto); unknown messages are ignored, so newer and older versions get along:
  phone -> computer   {"t": "pair", "name", "platform", "app", "features"}   (first message after scanning the code)
  computer -> phone   {"t": "paired", "dev", "ltk", "name", "app", "features", "pc_id", "port"}
  phone -> computer   {"t": "resume", "name", "platform", "app", "features"} (later connections)
  computer -> phone   {"t": "welcome", "name", "app", "features", "pc_id", "port"}
  either way          {"t": "ping"} / {"t": "pong"}
  sender -> receiver  {"t": "offer", "id", "title", "items": [{"path": "Album/01 Song.mp3", "size"}]}
  receiver -> sender  {"t": "answer", "id", "accept": true|false}
  sender -> receiver  {"t": "file", "id", "i"} + data frames + {"t": "file_end", "id", "i", "sha256"}
  sender -> receiver  {"t": "offer_end", "id"}         receiver -> sender {"t": "received", "id", "saved": n}
  either way          {"t": "cancel", "id"}
Files go one at a time per direction: after {"t": "file"} only that file's data frames follow until its
{"t": "file_end"}; a second "file" while one is open breaks the connection. An offer id is 1-40 characters
[A-Za-z0-9_-] and is never reused on a connection.
"""
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import struct
import threading
import time
import unicodedata
import urllib.parse

from . import pair_crypto as pc

FEATURES = ["send_files"]
PAIR_WINDOW_SECONDS = 300
MAX_PAIR_FAILS_PER_ADDRESS = 3       # wrong code / bad first message, per address, per QR code
MAX_PAIR_FAILS = 100                 # in all, per QR code (the card then offers a new code)
HANDSHAKE_SECONDS = 10               # for the whole handshake, however slowly the bytes come
IDLE_TIMEOUT = 300
MAX_HANDSHAKES = 6                   # connections still proving who they are
MAX_HANDSHAKES_PER_ADDRESS = 2
MAX_SESSIONS = 8                     # paired phones connected at once
MAX_FIRST_FRAME = 8 * 1024
MAX_HELLO = 1024
CHUNK = 256 * 1024
MAX_FILES = 3000
MAX_FILE_SIZE = 4 * 1024 ** 3
MAX_TOTAL = 40 * 1024 ** 3
MAX_JSON = 2 * 1024 * 1024
MAX_REL_PATH = 200
DISK_MARGIN = 200 * 1024 ** 2
DECLINES_BEFORE_PAUSE = 3
DECLINE_PAUSE_SECONDS = 600
DEFAULT_PORT_RANGE = (49200, 49900)
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma", ".aiff", ".aif", ".alac", ".ape",
             ".mka", ".webm"}
EXTRA_EXT = {".jpg": 30 * 1024 ** 2, ".jpeg": 30 * 1024 ** 2, ".png": 30 * 1024 ** 2, ".lrc": 1024 ** 2,
             ".m3u": 1024 ** 2, ".m3u8": 1024 ** 2}
_SUPERSCRIPT = "¹²³"
WINDOWS_RESERVED = ({"con", "prn", "aux", "nul", "conin$", "conout$", "clock$"}
                    | {f"com{c}" for c in "0123456789" + _SUPERSCRIPT}
                    | {f"lpt{c}" for c in "0123456789" + _SUPERSCRIPT})
OFFER_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
# Your own network only (written out, so it doesn't depend on the Python version's idea of "private").
LOCAL_NETWORKS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8",
    "100.64.0.0/10",                                   # carrier-grade NAT / Tailscale-style home VPNs
    "fc00::/7", "fe80::/10", "::1/128")]


class Refused(Exception):
    pass


# --- network helpers ----------------------------------------------------------------------------------------------
def is_private_address(addr):
    """Only your own network may connect: private, link-local and loopback addresses."""
    try:
        ip = ipaddress.ip_address(str(addr).split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return any(ip.version == n.version and ip in n for n in LOCAL_NETWORKS)


def local_addresses():
    """This computer's addresses on the local network (no internet lookup: a UDP 'connect' sends nothing)."""
    found = []
    for probe in ("192.168.0.1", "10.0.0.1", "172.16.0.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((probe, 9))
            a = s.getsockname()[0]
            s.close()
            if a not in found and is_private_address(a) and not a.startswith("127."):
                found.append(a)
        except OSError:
            pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            a = info[4][0]
            if a not in found and is_private_address(a) and not a.startswith("127."):
                found.append(a)
    except OSError:
        pass
    return found[:4]


# --- names --------------------------------------------------------------------------------------------------------
def _plain(text):
    """NFC, without control/format characters (right-to-left overrides, zero-width characters...)."""
    text = unicodedata.normalize("NFC", str(text or ""))
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn"))


def clean_name(name, fallback="Phone"):
    """A device name safe to show anywhere (also in Qt rich text): no markup characters, at most 40 characters."""
    name = re.sub(r"[<>&]", "", _plain(name))[:40].strip()
    return name or fallback


# --- QR link ------------------------------------------------------------------------------------------------------
def pair_link(addresses, port, code, pc_id, name):
    q = {"v": str(pc.VERSION), "a": ",".join(addresses), "p": str(port),
         "s": pc.b64e(code).rstrip("=").replace("+", "-").replace("/", "_"), "id": pc_id, "n": name[:40]}
    return "sevbify://pair?" + urllib.parse.urlencode(q)


def parse_pair_link(link):
    """-> dict(addresses, port, code, id, name, v) or raises ValueError (the phone side does the same)."""
    if not isinstance(link, str) or len(link) > 600:
        raise ValueError("not a Sevbify pairing code")
    u = urllib.parse.urlparse(link)
    if u.scheme != "sevbify" or u.netloc != "pair":
        raise ValueError("not a Sevbify pairing code")
    q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
    code = q.get("s", "").replace("-", "+").replace("_", "/")
    try:
        code = pc.b64d(code + "=" * (-len(code) % 4), 32)
        port = int(q.get("p", "0"))
    except (pc.LinkError, ValueError):
        raise ValueError("bad pairing code")
    addresses = [a for a in q.get("a", "").split(",") if a and is_private_address(a)][:4]
    if not addresses or not 1024 <= port <= 65535:
        raise ValueError("bad pairing code")
    return {"addresses": addresses, "port": port, "code": code, "id": q.get("id", "")[:32],
            "name": clean_name(q.get("n", ""), "Computer"), "v": int(q.get("v", "1")) if q.get("v", "1").isdigit() else 1}


# --- paired devices -------------------------------------------------------------------------------------------------
class DeviceStore:
    """Paired phones in <data folder>/paired_devices.json (readable only by you): name, key, when; and this computer's
    id and port (kept, so phones find it again after a restart)."""

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "paired_devices.json")
        self.lock = threading.RLock()
        self.devices = {}
        self.pc_id = ""
        self.port = 0
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.devices = {k: v for k, v in (data.get("devices") or {}).items()
                            if isinstance(v, dict) and re.fullmatch(r"[0-9a-f]{32}", k)}
            self.pc_id = str(data.get("pc_id") or "")
            self.port = int(data.get("port") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            self.devices = {}
        changed = False
        if not re.fullmatch(r"[0-9a-f]{16}", self.pc_id):
            self.pc_id = secrets.token_hex(8)
            changed = True
        if not DEFAULT_PORT_RANGE[0] <= self.port <= DEFAULT_PORT_RANGE[1]:
            self.port = secrets.randbelow(DEFAULT_PORT_RANGE[1] - DEFAULT_PORT_RANGE[0]) + DEFAULT_PORT_RANGE[0]
            changed = True
        if changed and os.path.isdir(os.path.dirname(self.path) or "."):
            self._save()

    def _save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"pc_id": self.pc_id, "port": self.port, "devices": self.devices}, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)

    def add(self, name, platform):
        with self.lock:
            dev = secrets.token_hex(16)
            ltk = secrets.token_bytes(32)
            self.devices[dev] = {"name": clean_name(name), "platform": clean_name(platform, "")[:20],
                                 "ltk": pc.b64e(ltk), "added": int(time.time()), "last_seen": int(time.time())}
            self._save()
            return dev, ltk

    def key(self, dev):
        with self.lock:
            d = self.devices.get(dev)
            return pc.b64d(d["ltk"], 32) if d else None

    def has(self, dev):
        with self.lock:
            return dev in self.devices

    def seen(self, dev):
        with self.lock:
            if dev in self.devices:
                self.devices[dev]["last_seen"] = int(time.time())
                self._save()

    def remove(self, dev):
        with self.lock:
            if self.devices.pop(dev, None) is not None:
                self._save()
                return True
            return False

    def listing(self):
        with self.lock:
            return [dict(id=k, name=v.get("name", "Phone"), platform=v.get("platform", ""), added=v.get("added", 0),
                         last_seen=v.get("last_seen", 0)) for k, v in self.devices.items()]

    def name(self, dev):
        with self.lock:
            return (self.devices.get(dev) or {}).get("name", "Phone")


# --- safe file names -------------------------------------------------------------------------------------------------
def safe_part(part):
    part = re.sub(r'[<>:"/\\|?*]', "_", _plain(part)).strip().rstrip(". ")
    if not part or part in (".", ".."):
        return "_"
    if part.split(".")[0].rstrip(" .").lower() in WINDOWS_RESERVED:
        part = "_" + part
    return part[:120].rstrip(". ") or "_"


def safe_relative(path):
    """'Album/01 Song.mp3' from whatever the sender wrote; None when it isn't something we take."""
    if not isinstance(path, str) or len(path) > 600:
        return None
    parts = [p for p in re.split(r"[\\/]+", path) if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts) or len(parts) > 6:
        return None
    parts = [safe_part(p) for p in parts]
    ext = os.path.splitext(parts[-1])[1].lower()
    if ext not in AUDIO_EXT and ext not in EXTRA_EXT:
        return None
    rel = os.path.join(*parts)
    return rel if len(rel) <= MAX_REL_PATH else None


def allowed_size(rel, size):
    ext = os.path.splitext(rel)[1].lower()
    limit = EXTRA_EXT.get(ext, MAX_FILE_SIZE)
    return type(size) is int and 0 <= size <= limit


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    for n in range(2, 1000):
        candidate = f"{base} ({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
    raise OSError("too many files with this name")


# --- a connection ----------------------------------------------------------------------------------------------------
def read_exact(sock, n, deadline=None):
    buf = bytearray()
    while len(buf) < n:
        if deadline is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                raise pc.LinkError("too slow")
            sock.settimeout(min(left, 5.0))
        part = sock.recv(min(65536, n - len(buf)))
        if not part:
            raise ConnectionError("closed")
        buf += part
    return bytes(buf)


class Link:
    """One encrypted connection (either end)."""

    def __init__(self, sock, channel):
        self.sock, self.ch = sock, channel
        self.send_lock = threading.Lock()
        self.closed = False

    def send_json(self, msg):
        self._send(pc.KIND_JSON, json.dumps(msg, separators=(",", ":")).encode())

    def send_data(self, data):
        self._send(pc.KIND_DATA, data)

    def _send(self, kind, payload):
        with self.send_lock:
            self.sock.sendall(self.ch.seal(kind, payload))

    def recv(self, limit=None, deadline=None):
        (n,) = struct.unpack(">I", read_exact(self.sock, 4, deadline))
        if n > (limit if limit is not None else pc.MAX_FRAME + 64):
            raise pc.LinkError("frame too big")
        kind, payload = self.ch.open(read_exact(self.sock, n, deadline))
        if kind == pc.KIND_JSON:
            if len(payload) > MAX_JSON:
                raise pc.LinkError("message too big")
            try:
                msg = json.loads(payload)
            except (ValueError, RecursionError):
                raise pc.LinkError("bad message")
            if not isinstance(msg, dict) or not isinstance(msg.get("t"), str):
                raise pc.LinkError("bad message")
            return msg
        if kind == pc.KIND_DATA:
            return payload
        raise pc.LinkError("unknown frame")

    def close(self):
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def _plain_frame(msg):
    data = json.dumps(msg, separators=(",", ":")).encode()
    return struct.pack(">I", len(data)) + data


def _plain_recv(sock, deadline=None):
    """-> (message, the frame's bytes as received)."""
    head = read_exact(sock, 4, deadline)
    (n,) = struct.unpack(">I", head)
    if n > MAX_HELLO:
        raise pc.LinkError("hello too big")
    body = read_exact(sock, n, deadline)
    try:
        msg = json.loads(body)
    except (ValueError, RecursionError):
        raise pc.LinkError("bad hello")
    if not isinstance(msg, dict):
        raise pc.LinkError("bad hello")
    return msg, head + body


# --- sending and receiving files ----------------------------------------------------------------------------------------
class Receiver:
    """Saves an accepted offer into `folder`: each offered file at most once, as .part, checked (size, SHA-256), then
    renamed; never more bytes in all than offered."""

    def __init__(self, offer, folder):
        self.id = offer["id"]
        self.folder = folder
        self.items = offer["items"]
        self.offered = sum(s for _r, s in self.items)
        self.written = 0
        self.started = set()
        self.current = None
        self.saved = []

    def start_file(self, i):
        if type(i) is not int or not 0 <= i < len(self.items) or i in self.started:
            raise pc.LinkError("bad file index")
        if self.current is not None:
            raise pc.LinkError("a file is already open")
        self.started.add(i)
        rel, size = self.items[i]
        target = os.path.join(self.folder, rel)
        try:
            real_folder = os.path.realpath(self.folder)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.commonpath([real_folder, os.path.realpath(os.path.dirname(target))]) != real_folder:
                raise OSError("outside the folder")
            part = unique_path(target + ".part")
            f = open(part, "xb")
        except (OSError, ValueError):
            part, f = None, None                      # this one can't be saved (path too long...): skip its bytes
        self.current = {"i": i, "target": target, "part": part, "size": size, "got": 0,
                        "hash": hashlib.sha256(), "f": f}

    def data(self, chunk):
        c = self.current
        if c is None:
            raise pc.LinkError("data without a file")
        c["got"] += len(chunk)
        self.written += len(chunk)
        if c["got"] > c["size"] or self.written > self.offered:
            self.abort_file()
            raise pc.LinkError("more than offered")
        if c["f"] is not None:
            c["hash"].update(chunk)
            try:
                c["f"].write(chunk)
            except OSError:                           # disk full...: drop this file, keep the connection
                self._drop_part(c)

    @staticmethod
    def _drop_part(c):
        try:
            c["f"].close()
        except OSError:
            pass
        try:
            os.remove(c["part"])
        except OSError:
            pass
        c["f"] = None

    def end_file(self, i, sha):
        c = self.current
        if c is None or c["i"] != i:
            raise pc.LinkError("file end out of order")
        self.current = None
        if c["f"] is None:
            return None
        c["f"].close()
        ok = c["got"] == c["size"] and isinstance(sha, str) and secrets.compare_digest(c["hash"].hexdigest(), sha)
        if not ok:
            self._drop_part(c)
            return None
        try:
            final = unique_path(c["target"])
            os.replace(c["part"], final)
        except OSError:
            self._drop_part(c)
            return None
        self.saved.append(final)
        return final

    def abort_file(self):
        c = self.current
        if c is not None and c["f"] is not None:
            self._drop_part(c)
        self.current = None


def check_offer(msg):
    """The offer as [(safe relative path, size)], or None when it isn't acceptable."""
    items = msg.get("items")
    oid = msg.get("id")
    if not isinstance(oid, str) or not OFFER_ID.fullmatch(oid) or not isinstance(items, list):
        return None
    if not 0 < len(items) <= MAX_FILES:
        return None
    out, total, seen = [], 0, set()
    for it in items:
        if not isinstance(it, dict):
            return None
        rel = safe_relative(it.get("path"))
        size = it.get("size")
        if rel is None or not allowed_size(rel, size):
            continue                                   # skip what we don't take, keep the rest
        key = unicodedata.normalize("NFC", rel).casefold()
        if key in seen:
            continue
        seen.add(key)
        total += size
        out.append((rel, size))
    if not out or total > MAX_TOTAL:
        return None
    return out


def offer_from_paths(paths):
    """Files and folders -> offer items [(relative path, size, full path)] keeping folder names (a dropped
    'Album' folder arrives as 'Album/...')."""
    items = []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isdir(p):
            base = os.path.dirname(p.rstrip("\\/"))
            for root, _dirs, files in os.walk(p):
                for f in sorted(files):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, base).replace(os.sep, "/")
                    if safe_relative(rel) and not os.path.islink(full):
                        items.append((rel, os.path.getsize(full), full))
        elif os.path.isfile(p) and safe_relative(os.path.basename(p)):
            items.append((os.path.basename(p), os.path.getsize(p), p))
    return items[:MAX_FILES]


class Session:
    """A connected, trusted phone (or computer). Runs its reader on its own thread; `events` gets callbacks:
    on_offer(session, offer_id, title, items) -> call session.answer(...) later; on_progress(session, id, done,
    total); on_received(session, id, paths); on_sent(session, id, ok); on_cancelled(session, id); on_closed(session)."""

    def __init__(self, link, dev, name, platform, app, features, receive_folder, events):
        self.link, self.dev, self.name, self.platform, self.app = link, dev, name, platform, app
        self.features = features
        self.receive_folder = receive_folder
        self.events = events
        self.lock = threading.RLock()
        self.receiving = {}          # offer id -> Receiver (accepted)
        self.pending_offers = {}     # offer id -> items (waiting for you)
        self.used_ids = set()
        self.sending = {}            # offer id -> {"items", "answer": Event, "accepted": bool}
        self.send_queue_lock = threading.Lock()      # one transfer at a time from this side
        self.declines = []
        self.last_heard = time.time()

    # receiving side
    def answer(self, offer_id, accept):
        with self.lock:
            items = self.pending_offers.pop(offer_id, None)
            if items is None or self.link.closed:
                return False
            if accept:
                folder = os.path.join(self.receive_folder, safe_part(f"From {self.name}"))
                need = sum(s for _r, s in items) + DISK_MARGIN
                try:
                    os.makedirs(folder, exist_ok=True)
                    accept = shutil.disk_usage(folder).free >= need
                except OSError:
                    accept = False
                if accept:
                    self.receiving[offer_id] = Receiver({"id": offer_id, "items": items}, folder)
            else:
                self.declines = [t for t in self.declines if time.time() - t < DECLINE_PAUSE_SECONDS] + [time.time()]
        try:
            self.link.send_json({"t": "answer", "id": offer_id, "accept": bool(accept)})
        except OSError:
            pass
        return bool(accept)

    # sending side
    def send_paths(self, paths, title=""):
        """Offer files/folders; runs on a background thread. Returns the offer id."""
        items = offer_from_paths(paths)
        if not items:
            raise ValueError("No music files to send")
        oid = secrets.token_hex(8)
        state = {"items": items, "answer": threading.Event(), "accepted": False, "cancel": False}
        with self.lock:
            self.sending[oid] = state
        threading.Thread(target=self._send_worker, args=(oid, title), daemon=True,
                         name="sevbify-pair-send").start()
        return oid

    def cancel(self, oid):
        with self.lock:
            st = self.sending.get(oid)
        if st:
            st["cancel"] = True
            st["answer"].set()
        try:
            self.link.send_json({"t": "cancel", "id": oid})
        except OSError:
            pass

    def _send_worker(self, oid, title):
        st = self.sending[oid]
        ok = False
        try:
            self.link.send_json({"t": "offer", "id": oid, "title": str(title)[:100],
                                 "items": [{"path": rel, "size": size} for rel, size, _f in st["items"]]})
            if not st["answer"].wait(600) or not st["accepted"] or st["cancel"]:
                return
            with self.send_queue_lock:                 # files of one offer at a time
                total = sum(s for _r, s, _f in st["items"]) or 1
                done = 0
                for i, (rel, size, full) in enumerate(st["items"]):
                    if st["cancel"] or self.link.closed:
                        return
                    h = hashlib.sha256()
                    self.link.send_json({"t": "file", "id": oid, "i": i})
                    sent = 0
                    try:
                        with open(full, "rb") as f:
                            while sent < size:
                                chunk = f.read(min(CHUNK, size - sent))
                                if not chunk:
                                    break
                                h.update(chunk)
                                self.link.send_data(chunk)
                                sent += len(chunk)
                                done += len(chunk)
                                self._event("on_progress", oid, done, total)
                                if st["cancel"]:
                                    return
                    except OSError:
                        if self.link.closed:
                            raise
                    # a file that changed or vanished meanwhile ends short: the receiver drops it
                    self.link.send_json({"t": "file_end", "id": oid, "i": i, "sha256": h.hexdigest()})
                self.link.send_json({"t": "offer_end", "id": oid})
                ok = True
        except (OSError, pc.LinkError):
            ok = False
        finally:
            with self.lock:
                self.sending.pop(oid, None)
            self._event("on_sent", oid, ok)

    def _event(self, name, *args):
        fn = getattr(self.events, name, None)
        if fn is not None:
            try:
                fn(self, *args)
            except Exception:
                pass

    def _paused(self):
        recent = [t for t in self.declines if time.time() - t < DECLINE_PAUSE_SECONDS]
        return len(recent) >= DECLINES_BEFORE_PAUSE

    # reader
    def handle(self, msg):
        self.last_heard = time.time()
        if isinstance(msg, (bytes, bytearray)):
            with self.lock:
                rec = next((r for r in self.receiving.values() if r.current is not None), None)
                if rec is None:
                    raise pc.LinkError("unexpected data")
                rec.data(msg)
            return
        t = msg["t"]
        oid = msg.get("id")
        if oid is not None and (not isinstance(oid, str) or not OFFER_ID.fullmatch(oid)):
            raise pc.LinkError("bad id")
        if t == "ping":
            self.link.send_json({"t": "pong"})
        elif t == "offer":
            items = check_offer(msg)
            with self.lock:
                refuse = (items is None or oid in self.used_ids or self._paused()
                          or len(self.pending_offers) + len(self.receiving) >= 4)
                if oid is not None:
                    self.used_ids.add(oid)
                if not refuse:
                    self.pending_offers[oid] = items
            if refuse:
                if oid is not None:
                    self.link.send_json({"t": "answer", "id": oid, "accept": False})
                return
            self._event("on_offer", oid, _plain(msg.get("title") or "")[:100], items)
        elif t == "answer":
            with self.lock:
                st = self.sending.get(oid)
            if st:
                st["accepted"] = msg.get("accept") is True
                st["answer"].set()
        elif t == "file":
            with self.lock:
                rec = self.receiving.get(oid)
                if rec is None:
                    raise pc.LinkError("file for an offer that wasn't accepted")
                if any(r.current is not None for r in self.receiving.values()):
                    raise pc.LinkError("one file at a time")
                rec.start_file(msg.get("i"))
        elif t == "file_end":
            with self.lock:
                rec = self.receiving.get(oid)
                if rec is None:
                    raise pc.LinkError("unexpected file end")
                rec.end_file(msg.get("i"), msg.get("sha256"))
                done, total = rec.written, rec.offered or 1
            self._event("on_progress", oid, done, total)
        elif t == "offer_end":
            with self.lock:
                rec = self.receiving.pop(oid, None)
                if rec is not None:
                    rec.abort_file()
            if rec is not None:
                self.link.send_json({"t": "received", "id": rec.id, "saved": len(rec.saved)})
                self._event("on_received", rec.id, list(rec.saved))
        elif t == "cancel":
            with self.lock:
                rec = self.receiving.pop(oid, None)
                if rec is not None:
                    rec.abort_file()
                self.pending_offers.pop(oid, None)
                st = self.sending.get(oid)
            if st:
                st["cancel"] = True
                st["answer"].set()
            self._event("on_cancelled", oid)
        # anything else: a newer version's message; ignored

    def run(self):
        try:
            self.link.sock.settimeout(IDLE_TIMEOUT)
            while not self.link.closed:
                self.handle(self.link.recv())
        except Exception:
            pass
        finally:
            with self.lock:
                for rec in self.receiving.values():
                    rec.abort_file()
                self.receiving.clear()
                self.pending_offers.clear()
                for st in self.sending.values():
                    st["cancel"] = True
                    st["answer"].set()
            self.link.close()
            self._event("on_closed")


# --- the computer's side --------------------------------------------------------------------------------------------
class PairServer:
    """Listens on the local network for paired phones (and for a new one while the pairing card is open)."""

    def __init__(self, data_dir, receive_folder, pc_name, app_version, events, port=None):
        self.store = DeviceStore(data_dir)
        self.receive_folder = receive_folder
        self.pc_name = clean_name(pc_name, "Computer")
        self.app_version = str(app_version)[:30]
        self.events = events
        self.port = self.store.port if port is None else port
        self.sock = None
        self.sessions = {}
        self.lock = threading.Lock()
        self._pairing = None          # {"code", "until", "fails": {addr: n}, "fail_total"}
        self._handshakes = {}         # address -> connections still proving who they are
        self._stop = threading.Event()

    # pairing window
    def open_pairing(self):
        """A fresh one-time code -> the QR link. Valid for 5 minutes, once."""
        code = secrets.token_bytes(32)
        with self.lock:
            self._pairing = {"code": code, "until": time.time() + PAIR_WINDOW_SECONDS, "fails": {}, "fail_total": 0}
        return pair_link(local_addresses() or ["127.0.0.1"], self.port, code, self.store.pc_id, self.pc_name)

    def close_pairing(self):
        with self.lock:
            self._pairing = None

    def pairing_open(self):
        p = self._pairing
        return p is not None and time.time() <= p["until"]

    # listening
    def start(self):
        last = None
        for port in ([self.port] + [self.port + k for k in range(1, 6)]) if self.port else [0]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name == "nt":
                s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", 0) or socket.SO_REUSEADDR, 1) \
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE") else None
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
            except OSError as e:
                s.close()
                last = e
                continue
            s.listen(16)
            self.sock = s
            self.port = s.getsockname()[1]
            threading.Thread(target=self._accept_loop, daemon=True, name="sevbify-pair-listen").start()
            return self.port
        raise last or OSError("no free port")

    def stop(self):
        self._stop.set()
        try:
            self.sock.close()
        except (OSError, AttributeError):
            pass
        for sess in list(self.sessions.values()):
            sess.link.close()

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, addr = self.sock.accept()
            except OSError:
                if self._stop.is_set():
                    return
                time.sleep(0.2)
                continue
            ip = addr[0]
            with self.lock:
                busy = (not is_private_address(ip) or sum(self._handshakes.values()) >= MAX_HANDSHAKES
                        or self._handshakes.get(ip, 0) >= MAX_HANDSHAKES_PER_ADDRESS)
                if not busy:
                    self._handshakes[ip] = self._handshakes.get(ip, 0) + 1
            if busy:
                conn.close()
                continue
            threading.Thread(target=self._serve, args=(conn, ip), daemon=True, name="sevbify-pair-conn").start()

    def _done_handshake(self, ip):
        with self.lock:
            n = self._handshakes.get(ip, 1) - 1
            if n > 0:
                self._handshakes[ip] = n
            else:
                self._handshakes.pop(ip, None)

    def _serve(self, conn, ip):
        sess = None
        try:
            try:
                sess = self._handshake(conn, ip)
            finally:
                self._done_handshake(ip)
            if sess is None:
                return
            with self.lock:
                if not self.store.has(sess.dev) or (sess.dev not in self.sessions
                                                    and len(self.sessions) >= MAX_SESSIONS):
                    sess.link.close()
                    return
                old = self.sessions.get(sess.dev)
                self.sessions[sess.dev] = sess
            if old is not None:
                old.link.close()
            fn = getattr(self.events, "on_connected", None)
            if fn:
                fn(sess)
            sess.run()
        except Exception:
            pass
        finally:
            if sess is not None:
                with self.lock:
                    if self.sessions.get(sess.dev) is sess:
                        del self.sessions[sess.dev]
            try:
                conn.close()
            except OSError:
                pass

    def _refuse(self, conn, c_hello_frame=None):
        try:
            conn.sendall(_plain_frame({"t": "error", "code": "refused"}))
        except OSError:
            pass
        return None

    def _pair_failed(self, pairing, ip):
        with self.lock:
            if pairing is None:
                return
            pairing["fails"][ip] = pairing["fails"].get(ip, 0) + 1
            pairing["fail_total"] += 1

    def _handshake(self, conn, ip):
        deadline = time.monotonic() + HANDSHAKE_SECONDS
        hello, c_hello = _plain_recv(conn, deadline)
        if hello.get("t") != "hello":
            return None
        versions = [v for v in hello.get("v") if type(v) is int] if isinstance(hello.get("v"), list) else []
        common = sorted(set(versions) & set(pc.SUPPORTED))
        if not common:
            conn.sendall(_plain_frame({"t": "error", "code": "version", "supported": list(pc.SUPPORTED)}))
            return None
        mode = hello.get("mode")
        dev = hello.get("dev") or ""
        pairing = None
        if mode == "pair":
            with self.lock:
                pairing = self._pairing
                ok = (pairing is not None and time.time() <= pairing["until"]
                      and pairing["fails"].get(ip, 0) < MAX_PAIR_FAILS_PER_ADDRESS
                      and pairing["fail_total"] < MAX_PAIR_FAILS)
            if not ok:
                return self._refuse(conn)
            psk, dev = pairing["code"], ""
        elif mode == "resume" and isinstance(dev, str) and re.fullmatch(r"[0-9a-f]{32}", dev):
            psk = self.store.key(dev)
            if psk is None:
                return self._refuse(conn)
        else:
            return None
        try:
            c_epk = pc.b64d(hello.get("epk"), 65)
            c_nonce = pc.b64d(hello.get("nonce"), 32)
            peer = pc.load_public(c_epk)
        except pc.LinkError:
            return None
        mine = pc.new_keypair()
        s_epk, s_nonce = pc.public_bytes(mine), pc.random_bytes(32)
        s_hello = _plain_frame({"t": "hello", "v": common[-1], "epk": pc.b64e(s_epk), "nonce": pc.b64e(s_nonce)})
        conn.sendall(s_hello)
        c2s, s2c = pc.derive_keys(pc.ecdh(mine, peer), psk, mode, dev, c_nonce, s_nonce, c_epk, s_epk,
                                  c_hello, s_hello)
        link = Link(conn, pc.Channel(send_key=s2c, recv_key=c2s))
        try:
            first = link.recv(limit=MAX_FIRST_FRAME, deadline=deadline)   # only someone with the key gets past here
        except pc.LinkError:
            self._pair_failed(pairing, ip)
            raise
        name = clean_name(first.get("name"))
        platform = clean_name(first.get("platform"), "")[:20]
        app = clean_name(first.get("app"), "")[:30]
        features = [f for f in first.get("features") if isinstance(f, str)][:20] \
            if isinstance(first.get("features"), list) else []
        if mode == "pair":
            if first.get("t") != "pair":
                return None
            with self.lock:
                if self._pairing is not pairing:      # used meanwhile by someone else, or a new code was made
                    return None
                self._pairing = None                  # the QR code works once
            dev, ltk = self.store.add(name, platform)
            link.send_json({"t": "paired", "dev": dev, "ltk": pc.b64e(ltk), "name": self.pc_name,
                            "app": self.app_version, "features": FEATURES, "pc_id": self.store.pc_id,
                            "port": self.port})
            fn = getattr(self.events, "on_paired", None)
            if fn:
                fn(dev, name)
        else:
            if first.get("t") != "resume":
                return None
            self.store.seen(dev)
            name = self.store.name(dev)               # the name it had when you paired it
            link.send_json({"t": "welcome", "name": self.pc_name, "app": self.app_version, "features": FEATURES,
                            "pc_id": self.store.pc_id, "port": self.port})
        conn.settimeout(IDLE_TIMEOUT)
        return Session(link, dev, name, platform, app, features, self.receive_folder, self.events)

    def forget(self, dev):
        """Remove a paired phone: its key stops working straight away."""
        with self.lock:
            self.store.remove(dev)
            sess = self.sessions.pop(dev, None)
        if sess is not None:
            sess.link.close()

    def connected(self):
        with self.lock:
            return [s for s in self.sessions.values() if not s.link.closed]


# --- the phone's side (reference; the phone apps do the same in Kotlin/Swift; also used by the tests) ----------------
def connect(address, port, *, code=None, dev=None, ltk=None, name="Phone", platform="test", app="0",
            receive_folder=None, events=None, timeout=10):
    """Pair with a QR code (code=...) or reconnect (dev=..., ltk=...). Returns (session, info)."""
    sock = socket.create_connection((address, port), timeout=timeout)
    deadline = time.monotonic() + timeout
    try:
        mode = "pair" if code is not None else "resume"
        dev_field = (dev or "") if mode == "resume" else ""
        mine = pc.new_keypair()
        c_epk, c_nonce = pc.public_bytes(mine), pc.random_bytes(32)
        c_hello = _plain_frame({"t": "hello", "v": list(pc.SUPPORTED), "mode": mode, "dev": dev_field,
                                "epk": pc.b64e(c_epk), "nonce": pc.b64e(c_nonce)})
        sock.sendall(c_hello)
        reply, s_hello = _plain_recv(sock, deadline)
        if reply.get("t") == "error":
            raise pc.LinkError(str(reply.get("code")))        # only shown; never a reason to forget the pairing
        if reply.get("t") != "hello" or reply.get("v") not in pc.SUPPORTED:
            raise pc.LinkError("unexpected reply")
        s_epk = pc.b64d(reply.get("epk"), 65)
        s_nonce = pc.b64d(reply.get("nonce"), 32)
        psk = code if mode == "pair" else ltk
        c2s, s2c = pc.derive_keys(pc.ecdh(mine, pc.load_public(s_epk)), psk, mode, dev_field, c_nonce, s_nonce,
                                  c_epk, s_epk, c_hello, s_hello)
        link = Link(sock, pc.Channel(send_key=c2s, recv_key=s2c))
        link.send_json({"t": mode, "name": name, "platform": platform, "app": app, "features": FEATURES})
        info = link.recv(limit=MAX_FIRST_FRAME, deadline=deadline)
        if info.get("t") not in ("paired", "welcome"):
            raise pc.LinkError("unexpected reply")
        if info["t"] == "paired":
            dev = info.get("dev")
            ltk = pc.b64d(info.get("ltk"), 32)
        sock.settimeout(IDLE_TIMEOUT)
        if receive_folder is None:
            raise ValueError("receive_folder is needed")
        sess = Session(link, dev, clean_name(info.get("name"), "Computer"), "computer",
                       clean_name(info.get("app"), "")[:30], info.get("features") or [], receive_folder, events)
        return sess, {"dev": dev, "ltk": ltk, "name": sess.name, "pc_id": info.get("pc_id"), "port": info.get("port")}
    except Exception:
        sock.close()
        raise
