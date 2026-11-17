"""Pair a phone with this computer by scanning a QR code, then send songs and folders either way (same Wi-Fi only).

Privacy and safety, in short:
- Nothing goes through the internet or any server: the phone connects straight to this computer on your own network.
  Connections from outside private network addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x, link-local) are refused.
- Everything is encrypted (see pair_crypto). The QR code holds a one-time code that works once, for 5 minutes,
  and only while the "Pair a phone" window is open; a phone that scanned it gets its own key for later, which you can
  remove at any time (Settings → Paired phones).
- Files are only saved after you accept them on the receiving side; only music files (and their cover pictures /
  lyrics) are taken, with safe file names, inside the folder for that phone, never overwriting anything.

Messages (JSON frames, see pair_crypto); unknown messages are ignored, so newer and older versions get along:
  phone -> computer   {"t": "pair", "name", "platform", "app"}   (first message after pairing with the QR code)
  computer -> phone   {"t": "paired", "dev", "ltk", "name", "app", "features"}
  phone -> computer   {"t": "resume", "name", "platform", "app"} (later connections)
  computer -> phone   {"t": "welcome", "name", "app", "features"}
  either way          {"t": "ping"} / {"t": "pong"}
  sender -> receiver  {"t": "offer", "id", "title", "items": [{"path": "Album/01 Song.mp3", "size"}]}
  receiver -> sender  {"t": "answer", "id", "accept": true|false}
  sender -> receiver  {"t": "file", "id", "i"} + data frames + {"t": "file_end", "id", "i", "sha256"}
  sender -> receiver  {"t": "offer_end", "id"}         receiver -> sender {"t": "received", "id", "saved": n}
  either way          {"t": "cancel", "id"}
"""
import datetime
import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import struct
import threading
import time
import urllib.parse

from . import pair_crypto as pc

FEATURES = ["send_files"]
PAIR_WINDOW_SECONDS = 300
MAX_PAIR_TRIES = 5
HANDSHAKE_TIMEOUT = 10
IDLE_TIMEOUT = 300
MAX_CONNECTIONS = 4
CHUNK = 256 * 1024
MAX_FILES = 3000
MAX_FILE_SIZE = 4 * 1024 ** 3
MAX_TOTAL = 40 * 1024 ** 3
MAX_JSON = 2 * 1024 * 1024
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma", ".aiff", ".aif", ".alac", ".ape",
             ".mka", ".webm"}
EXTRA_EXT = {".jpg": 30 * 1024 ** 2, ".jpeg": 30 * 1024 ** 2, ".png": 30 * 1024 ** 2, ".lrc": 1024 ** 2,
             ".m3u": 1024 ** 2, ".m3u8": 1024 ** 2}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


# --- network helpers ----------------------------------------------------------------------------------------------
def is_private_address(addr):
    """Only your own network may connect: private, link-local and loopback addresses."""
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_link_local or ip.is_loopback


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


# --- QR link ------------------------------------------------------------------------------------------------------
def pair_link(addresses, port, code, pc_id, name):
    q = {"v": str(pc.VERSION), "a": ",".join(addresses), "p": str(port), "s": pc.b64e(code).rstrip("=")
         .replace("+", "-").replace("/", "_"), "id": pc_id, "n": name[:40]}
    return "sevbify://pair?" + urllib.parse.urlencode(q)


def parse_pair_link(link):
    """-> dict(addresses, port, code, id, name, v) or raises ValueError (the phone side does the same)."""
    u = urllib.parse.urlparse(link)
    if u.scheme != "sevbify" or u.netloc != "pair" or len(link) > 600:
        raise ValueError("not a Sevbify pairing code")
    q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
    s = q.get("s", "")
    code = urllib.parse.unquote(s).replace("-", "+").replace("_", "/")
    code = pc.b64d(code + "=" * (-len(code) % 4), 32)
    addresses = [a for a in q.get("a", "").split(",") if a and is_private_address(a)]
    port = int(q.get("p", "0"))
    if not addresses or not 1024 <= port <= 65535:
        raise ValueError("bad pairing code")
    return {"addresses": addresses, "port": port, "code": code, "id": q.get("id", ""), "name": q.get("n", ""),
            "v": int(q.get("v", "1"))}


# --- paired devices -------------------------------------------------------------------------------------------------
class DeviceStore:
    """Paired phones in <data folder>/paired_devices.json (readable only by you): name, key, when."""

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "paired_devices.json")
        self.lock = threading.Lock()
        self.devices = {}
        self.pc_id = ""
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.devices = {k: v for k, v in (data.get("devices") or {}).items()
                            if isinstance(v, dict) and re.fullmatch(r"[0-9a-f]{32}", k)}
            self.pc_id = str(data.get("pc_id") or "")
        except (OSError, ValueError):
            self.devices = {}
        if not re.fullmatch(r"[0-9a-f]{16}", self.pc_id):
            self.pc_id = secrets.token_hex(8)
            self._save()

    def _save(self):
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pc_id": self.pc_id, "devices": self.devices}, f, indent=1)
        os.replace(tmp, self.path)

    def add(self, name, platform):
        with self.lock:
            dev = secrets.token_hex(16)
            ltk = secrets.token_bytes(32)
            self.devices[dev] = {"name": clean_name(name), "platform": str(platform)[:20], "ltk": pc.b64e(ltk),
                                 "added": int(time.time()), "last_seen": int(time.time())}
            self._save()
            return dev, ltk

    def key(self, dev):
        d = self.devices.get(dev)
        return pc.b64d(d["ltk"], 32) if d else None

    def seen(self, dev, name=None):
        with self.lock:
            if dev in self.devices:
                self.devices[dev]["last_seen"] = int(time.time())
                if name:
                    self.devices[dev]["name"] = clean_name(name)
                self._save()

    def remove(self, dev):
        with self.lock:
            if self.devices.pop(dev, None) is not None:
                self._save()
                return True
            return False

    def listing(self):
        return [dict(id=k, name=v.get("name", "Phone"), platform=v.get("platform", ""), added=v.get("added", 0),
                     last_seen=v.get("last_seen", 0)) for k, v in self.devices.items()]


def clean_name(name):
    name = re.sub(r"[\x00-\x1f\x7f]", "", str(name or ""))[:40].strip()
    return name or "Phone"


# --- safe file names -------------------------------------------------------------------------------------------------
def safe_part(part):
    part = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", part).strip().rstrip(". ")
    if not part or part in (".", "..") or part.split(".")[0].lower() in WINDOWS_RESERVED:
        part = "_" + part if part not in ("", ".", "..") else "_"
    return part[:120]


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
    return os.path.join(*parts)


def allowed_size(rel, size):
    ext = os.path.splitext(rel)[1].lower()
    limit = EXTRA_EXT.get(ext, MAX_FILE_SIZE)
    return isinstance(size, int) and 0 <= size <= limit


def unique_path(path):
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"
        n += 1
    return path


# --- a connection ----------------------------------------------------------------------------------------------------
class Link:
    """One encrypted connection (either end)."""

    def __init__(self, sock, channel):
        self.sock, self.ch = sock, channel
        self.send_lock = threading.Lock()
        self.closed = False

    @staticmethod
    def read_exact(sock, n):
        buf = bytearray()
        while len(buf) < n:
            part = sock.recv(min(65536, n - len(buf)))
            if not part:
                raise ConnectionError("closed")
            buf += part
        return bytes(buf)

    def send_json(self, msg):
        self._send(pc.KIND_JSON, json.dumps(msg, separators=(",", ":")).encode())

    def send_data(self, data):
        self._send(pc.KIND_DATA, data)

    def _send(self, kind, payload):
        with self.send_lock:
            self.sock.sendall(self.ch.seal(kind, payload))

    def recv(self):
        (n,) = struct.unpack(">I", self.read_exact(self.sock, 4))
        if n > pc.MAX_FRAME + 64:
            raise pc.LinkError("frame too big")
        kind, payload = self.ch.open(self.read_exact(self.sock, n))
        if kind == pc.KIND_JSON:
            if len(payload) > MAX_JSON:
                raise pc.LinkError("message too big")
            try:
                msg = json.loads(payload)
            except ValueError:
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


def _plain_send(sock, msg):
    data = json.dumps(msg, separators=(",", ":")).encode()
    sock.sendall(struct.pack(">I", len(data)) + data)


def _plain_recv(sock):
    (n,) = struct.unpack(">I", Link.read_exact(sock, 4))
    if n > 4096:
        raise pc.LinkError("hello too big")
    try:
        msg = json.loads(Link.read_exact(sock, n))
    except ValueError:
        raise pc.LinkError("bad hello")
    if not isinstance(msg, dict):
        raise pc.LinkError("bad hello")
    return msg


# --- sending and receiving files ----------------------------------------------------------------------------------------
class Receiver:
    """Saves an accepted offer into `folder`: each file as .part, checked (size, SHA-256), then renamed."""

    def __init__(self, offer, folder):
        self.id = offer["id"]
        self.folder = folder
        self.items = offer["items"]
        self.current = None
        self.saved = []

    def start_file(self, i):
        if not isinstance(i, int) or not 0 <= i < len(self.items):
            raise pc.LinkError("bad file index")
        self.abort_file()
        rel, size = self.items[i]
        target = os.path.join(self.folder, rel)
        real_folder = os.path.realpath(self.folder)
        if os.path.commonpath([real_folder, os.path.realpath(os.path.dirname(target))]) != real_folder:
            raise pc.LinkError("bad path")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        part = unique_path(target + ".part")
        self.current = {"i": i, "target": target, "part": part, "size": size, "got": 0,
                        "hash": hashlib.sha256(), "f": open(part, "xb")}

    def data(self, chunk):
        c = self.current
        if c is None:
            raise pc.LinkError("data without a file")
        c["got"] += len(chunk)
        if c["got"] > c["size"]:
            self.abort_file()
            raise pc.LinkError("file bigger than offered")
        c["hash"].update(chunk)
        c["f"].write(chunk)

    def end_file(self, i, sha):
        c = self.current
        if c is None or c["i"] != i:
            raise pc.LinkError("file end out of order")
        c["f"].close()
        ok = c["got"] == c["size"] and isinstance(sha, str) and secrets.compare_digest(c["hash"].hexdigest(), sha)
        if not ok:
            os.remove(c["part"])
            self.current = None
            return None
        final = unique_path(c["target"])
        os.replace(c["part"], final)
        self.current = None
        self.saved.append(final)
        return final

    def abort_file(self):
        c = self.current
        if c is not None:
            try:
                c["f"].close()
                os.remove(c["part"])
            except OSError:
                pass
        self.current = None


def check_offer(msg):
    """The offer as [(safe relative path, size)], or None when it isn't acceptable."""
    items = msg.get("items")
    if not isinstance(msg.get("id"), str) or len(msg["id"]) > 40 or not isinstance(items, list):
        return None
    if not 0 < len(items) <= MAX_FILES:
        return None
    out, total, seen = [], 0, set()
    for it in items:
        if not isinstance(it, dict):
            return None
        rel = safe_relative(it.get("path"))
        size = it.get("size")
        if rel is None or not allowed_size(rel, size) or rel.lower() in seen:
            continue                                   # skip what we don't take, keep the rest
        seen.add(rel.lower())
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
    total); on_received(session, id, paths); on_sent(session, id, ok); on_closed(session)."""

    def __init__(self, link, dev, name, platform, app, features, receive_folder, events):
        self.link, self.dev, self.name, self.platform, self.app = link, dev, name, platform, app
        self.features = features
        self.receive_folder = receive_folder
        self.events = events
        self.receiving = {}          # offer id -> Receiver (accepted)
        self.pending_offers = {}     # offer id -> items (waiting for you)
        self.sending = {}            # offer id -> {"items", "answer": Event, "accepted": bool}
        self.last_heard = time.time()

    # receiving side
    def answer(self, offer_id, accept):
        items = self.pending_offers.pop(offer_id, None)
        if items is None:
            return
        if accept:
            folder = os.path.join(self.receive_folder, safe_part(f"From {self.name}"))
            os.makedirs(folder, exist_ok=True)
            self.receiving[offer_id] = Receiver({"id": offer_id, "items": items}, folder)
        try:
            self.link.send_json({"t": "answer", "id": offer_id, "accept": bool(accept)})
        except OSError:
            pass

    # sending side
    def send_paths(self, paths, title=""):
        """Offer files/folders; runs on a background thread. Returns the offer id."""
        items = offer_from_paths(paths)
        oid = secrets.token_hex(8)
        if not items:
            raise ValueError("No music files to send")
        state = {"items": items, "answer": threading.Event(), "accepted": False, "cancel": False}
        self.sending[oid] = state
        threading.Thread(target=self._send_worker, args=(oid, title), daemon=True,
                         name="sevbify-pair-send").start()
        return oid

    def cancel(self, oid):
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
            total = sum(s for _r, s, _f in st["items"]) or 1
            done = 0
            for i, (rel, size, full) in enumerate(st["items"]):
                if st["cancel"] or self.link.closed:
                    return
                h = hashlib.sha256()
                self.link.send_json({"t": "file", "id": oid, "i": i})
                sent = 0
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
                self.link.send_json({"t": "file_end", "id": oid, "i": i, "sha256": h.hexdigest()})
            self.link.send_json({"t": "offer_end", "id": oid})
            ok = True
        except (OSError, pc.LinkError):
            ok = False
        finally:
            self._event("on_sent", oid, ok)

    def _event(self, name, *args):
        fn = getattr(self.events, name, None)
        if fn is not None:
            try:
                fn(self, *args)
            except Exception:
                pass

    # reader
    def handle(self, msg):
        self.last_heard = time.time()
        if isinstance(msg, (bytes, bytearray)):
            rec = next((r for r in self.receiving.values() if r.current is not None), None)
            if rec is None:
                raise pc.LinkError("unexpected data")
            rec.data(msg)
            return
        t = msg["t"]
        if t == "ping":
            self.link.send_json({"t": "pong"})
        elif t == "offer":
            items = check_offer(msg)
            if items is None or len(self.pending_offers) + len(self.receiving) >= 4:
                self.link.send_json({"t": "answer", "id": str(msg.get("id"))[:40], "accept": False})
                return
            self.pending_offers[msg["id"]] = items
            self._event("on_offer", msg["id"], str(msg.get("title") or "")[:100], items)
        elif t == "answer":
            st = self.sending.get(msg.get("id"))
            if st:
                st["accepted"] = msg.get("accept") is True
                st["answer"].set()
        elif t == "file":
            rec = self.receiving.get(msg.get("id"))
            if rec is None:
                raise pc.LinkError("file for an offer that wasn't accepted")
            rec.start_file(msg.get("i"))
        elif t == "file_end":
            rec = self.receiving.get(msg.get("id"))
            if rec is None:
                raise pc.LinkError("unexpected file end")
            rec.end_file(msg.get("i"), msg.get("sha256"))
            total = sum(s for _r, s in rec.items) or 1
            done = sum(os.path.getsize(p) for p in rec.saved if os.path.exists(p))
            self._event("on_progress", rec.id, done, total)
        elif t == "offer_end":
            rec = self.receiving.pop(msg.get("id"), None)
            if rec is not None:
                rec.abort_file()
                self.link.send_json({"t": "received", "id": rec.id, "saved": len(rec.saved)})
                self._event("on_received", rec.id, list(rec.saved))
        elif t == "cancel":
            oid = msg.get("id")
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
        except (OSError, ConnectionError, pc.LinkError, struct.error):
            pass
        finally:
            for rec in self.receiving.values():
                rec.abort_file()
            for st in self.sending.values():
                st["cancel"] = True
                st["answer"].set()
            self.link.close()
            self._event("on_closed")


# --- the computer's side --------------------------------------------------------------------------------------------
class PairServer:
    """Listens on the local network for paired phones (and for new ones while the pairing window is open)."""

    def __init__(self, data_dir, receive_folder, pc_name, app_version, events, port=0):
        self.store = DeviceStore(data_dir)
        self.receive_folder = receive_folder
        self.pc_name = clean_name(pc_name)
        self.app_version = str(app_version)
        self.events = events
        self.port = port
        self.sock = None
        self.sessions = {}
        self.lock = threading.Lock()
        self._pairing = None          # {"code", "until", "tries"}
        self._conns = 0
        self._stop = threading.Event()

    # pairing window
    def open_pairing(self):
        """A fresh one-time code -> the QR link. Valid for 5 minutes, once."""
        code = secrets.token_bytes(32)
        self._pairing = {"code": code, "until": time.time() + PAIR_WINDOW_SECONDS, "tries": 0}
        return pair_link(local_addresses() or ["127.0.0.1"], self.port, code, self.store.pc_id, self.pc_name)

    def close_pairing(self):
        self._pairing = None

    # listening
    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) if os.name != "nt" else None
        s.bind(("0.0.0.0", self.port))
        s.listen(8)
        self.sock = s
        self.port = s.getsockname()[1]
        threading.Thread(target=self._accept_loop, daemon=True, name="sevbify-pair-listen").start()
        return self.port

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
            if not is_private_address(addr[0]) or self._conns >= MAX_CONNECTIONS:
                conn.close()
                continue
            with self.lock:
                self._conns += 1
            threading.Thread(target=self._serve, args=(conn, addr), daemon=True, name="sevbify-pair-conn").start()

    def _serve(self, conn, addr):
        try:
            conn.settimeout(HANDSHAKE_TIMEOUT)
            sess = self._handshake(conn)
            if sess is None:
                conn.close()
                return
            with self.lock:
                old = self.sessions.get(sess.dev)
                self.sessions[sess.dev] = sess
            if old is not None:
                old.link.close()
            fn = getattr(self.events, "on_connected", None)
            if fn:
                fn(sess)
            sess.run()
            with self.lock:
                if self.sessions.get(sess.dev) is sess:
                    del self.sessions[sess.dev]
        except Exception:
            try:
                conn.close()
            except OSError:
                pass
        finally:
            with self.lock:
                self._conns -= 1

    def _handshake(self, conn):
        hello = _plain_recv(conn)
        if hello.get("t") != "hello":
            return None
        versions = [v for v in (hello.get("v") or []) if isinstance(v, int)] if isinstance(hello.get("v"), list) else []
        common = sorted(set(versions) & set(pc.SUPPORTED))
        if not common:
            _plain_send(conn, {"t": "error", "code": "version", "supported": list(pc.SUPPORTED)})
            return None
        mode = hello.get("mode")
        dev = hello.get("dev") or ""
        if mode == "pair":
            p = self._pairing
            if p is None or time.time() > p["until"] or p["tries"] >= MAX_PAIR_TRIES:
                _plain_send(conn, {"t": "error", "code": "not_pairing"})
                return None
            p["tries"] += 1
            psk, dev = p["code"], ""
        elif mode == "resume" and isinstance(dev, str) and re.fullmatch(r"[0-9a-f]{32}", dev):
            psk = self.store.key(dev)
            if psk is None:
                _plain_send(conn, {"t": "error", "code": "unknown_device"})
                return None
        else:
            return None
        c_epk = pc.b64d(hello.get("epk"), 65)
        c_nonce = pc.b64d(hello.get("nonce"), 32)
        peer = pc.load_public(c_epk)
        mine = pc.new_keypair()
        s_epk, s_nonce = pc.public_bytes(mine), pc.random_bytes(32)
        _plain_send(conn, {"t": "hello", "v": common[-1], "epk": pc.b64e(s_epk), "nonce": pc.b64e(s_nonce)})
        c2s, s2c = pc.derive_keys(pc.ecdh(mine, peer), psk, mode, dev, c_nonce, s_nonce, c_epk, s_epk)
        link = Link(conn, pc.Channel(send_key=s2c, recv_key=c2s))
        first = link.recv()                    # fails unless the phone has the same keys (the QR code / its key)
        name = clean_name(first.get("name"))
        platform = str(first.get("platform") or "")[:20]
        app = str(first.get("app") or "")[:30]
        features = [f for f in (first.get("features") or []) if isinstance(f, str)][:20] \
            if isinstance(first.get("features"), list) else []
        if mode == "pair":
            if first.get("t") != "pair":
                return None
            self._pairing = None                # the QR code works once
            dev, ltk = self.store.add(name, platform)
            link.send_json({"t": "paired", "dev": dev, "ltk": pc.b64e(ltk), "name": self.pc_name,
                            "app": self.app_version, "features": FEATURES, "pc_id": self.store.pc_id})
            fn = getattr(self.events, "on_paired", None)
            if fn:
                fn(dev, name)
        else:
            if first.get("t") != "resume":
                return None
            self.store.seen(dev, name)
            link.send_json({"t": "welcome", "name": self.pc_name, "app": self.app_version, "features": FEATURES,
                            "pc_id": self.store.pc_id})
        conn.settimeout(IDLE_TIMEOUT)
        return Session(link, dev, name, platform, app, features, self.receive_folder, self.events)

    def forget(self, dev):
        """Remove a paired phone: its key stops working straight away."""
        self.store.remove(dev)
        sess = self.sessions.pop(dev, None)
        if sess is not None:
            sess.link.close()

    def connected(self):
        return list(self.sessions.values())


# --- the phone's side (reference; the phone apps do the same in Kotlin/Swift; also used by the tests) ----------------
def connect(address, port, *, code=None, dev=None, ltk=None, name="Phone", platform="test", app="0",
            receive_folder=None, events=None, timeout=10):
    """Pair with a QR code (code=...) or reconnect (dev=..., ltk=...). Returns (session, info)."""
    sock = socket.create_connection((address, port), timeout=timeout)
    try:
        mode = "pair" if code is not None else "resume"
        mine = pc.new_keypair()
        c_epk, c_nonce = pc.public_bytes(mine), pc.random_bytes(32)
        _plain_send(sock, {"t": "hello", "v": list(pc.SUPPORTED), "mode": mode, "dev": dev or "",
                           "epk": pc.b64e(c_epk), "nonce": pc.b64e(c_nonce)})
        reply = _plain_recv(sock)
        if reply.get("t") == "error":
            raise pc.LinkError(str(reply.get("code")))
        s_epk = pc.b64d(reply.get("epk"), 65)
        s_nonce = pc.b64d(reply.get("nonce"), 32)
        psk = code if mode == "pair" else ltk
        c2s, s2c = pc.derive_keys(pc.ecdh(mine, pc.load_public(s_epk)), psk, mode, dev or "" if mode == "resume"
                                  else "", c_nonce, s_nonce, c_epk, s_epk)
        link = Link(sock, pc.Channel(send_key=c2s, recv_key=s2c))
        link.send_json({"t": mode, "name": name, "platform": platform, "app": app, "features": FEATURES})
        info = link.recv()
        if info.get("t") not in ("paired", "welcome"):
            raise pc.LinkError("unexpected reply")
        if info["t"] == "paired":
            dev = info.get("dev")
            ltk = pc.b64d(info.get("ltk"), 32)
        sess = Session(link, dev, clean_name(info.get("name")), "computer", str(info.get("app"))[:30],
                       info.get("features") or [], receive_folder or ".", events)
        return sess, {"dev": dev, "ltk": ltk, "name": sess.name, "pc_id": info.get("pc_id")}
    except Exception:
        sock.close()
        raise
