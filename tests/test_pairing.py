"""Phone <-> computer pairing (QR code) and sending music: the real protocol over real local sockets."""
import hashlib
import os
import socket
import struct
import threading
import time

import pytest

pytest.importorskip("Cryptodome")

from core import pair_crypto as pc  # noqa: E402
from core import pairing as pr  # noqa: E402


class Events:
    def __init__(self, accept=True):
        self.accept = accept
        self.offers, self.received, self.sent, self.closed, self.paired, self.connected = [], [], [], [], [], []
        self.done = threading.Event()

    def on_offer(self, sess, oid, title, items):
        self.offers.append((oid, title, items))
        sess.answer(oid, self.accept)

    def on_received(self, sess, oid, paths):
        self.received.append(paths)
        self.done.set()

    def on_sent(self, sess, oid, ok):
        self.sent.append(ok)
        self.done.set()

    def on_closed(self, sess):
        self.closed.append(sess)

    def on_paired(self, dev, name):
        self.paired.append((dev, name))

    def on_connected(self, sess):
        self.connected.append(sess)


@pytest.fixture
def server(tmp_path):
    ev = Events()
    srv = pr.PairServer(str(tmp_path / "data"), str(tmp_path / "music"), "Test PC", "5.0.0-test", ev)
    srv.start()
    yield srv, ev
    srv.stop()


def _pair(srv, **kw):
    link = srv.open_pairing()
    info = pr.parse_pair_link(link)
    kw.setdefault("receive_folder", os.path.join(srv.receive_folder, "..", "phone"))
    return pr.connect("127.0.0.1", info["port"], code=info["code"], name="Pixel", platform="android", **kw)


RF = {"receive_folder": "unused"}


def _run(sess):
    t = threading.Thread(target=sess.run, daemon=True)
    t.start()
    return t


def _wait(cond, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_link_round_trip():
    link = pr.pair_link(["192.168.1.20", "10.0.0.5"], 50123, b"\x07" * 32, "abcdef0123456789", "Sev's PC")
    info = pr.parse_pair_link(link)
    assert info["addresses"] == ["192.168.1.20", "10.0.0.5"] and info["port"] == 50123
    assert info["code"] == b"\x07" * 32 and info["name"] == "Sev's PC"


def test_link_with_public_address_is_refused():
    link = pr.pair_link(["8.8.8.8"], 50123, b"\x07" * 32, "x", "PC")
    with pytest.raises(ValueError):
        pr.parse_pair_link(link)
    with pytest.raises(ValueError):
        pr.parse_pair_link("https://example.com/pair?s=abc")


def test_only_local_network_addresses():
    for a in ("192.168.0.4", "10.1.2.3", "172.20.0.1", "169.254.3.3", "127.0.0.1", "fe80::1", "fd00::5"):
        assert pr.is_private_address(a), a
    for a in ("8.8.8.8", "1.1.1.1", "2001:4860:4860::8888", "nonsense"):
        assert not pr.is_private_address(a), a


def test_pair_then_reconnect_with_the_saved_key(server):
    srv, ev = server
    sess, info = _pair(srv)
    assert info["dev"] in srv.store.devices and len(info["ltk"]) == 32 and ev.paired
    sess.link.close()
    sess2, info2 = pr.connect("127.0.0.1", srv.port, dev=info["dev"], ltk=info["ltk"], name="Pixel 9", **RF)
    assert info2["name"] == "Test PC" and info2["port"] == srv.port
    assert _wait(lambda: srv.connected())
    assert srv.connected()[0].name == "Pixel"          # keeps the name it was paired with
    sess2.link.close()


def test_the_qr_code_works_once(server):
    srv, _ev = server
    link = srv.open_pairing()
    info = pr.parse_pair_link(link)
    s, _ = pr.connect("127.0.0.1", srv.port, code=info["code"], **RF)
    s.link.close()
    with pytest.raises(pc.LinkError):
        pr.connect("127.0.0.1", srv.port, code=info["code"], **RF)


def test_wrong_code_is_refused_and_tries_are_limited_per_address(server):
    srv, _ev = server
    info = pr.parse_pair_link(srv.open_pairing())
    for _ in range(pr.MAX_PAIR_FAILS_PER_ADDRESS):
        with pytest.raises((pc.LinkError, OSError, ConnectionError)):
            s, _ = pr.connect("127.0.0.1", srv.port, code=os.urandom(32), **RF)
            s.link.recv()
    assert not srv.store.devices
    # this address is now refused, even with the right code; the code itself still works for other addresses
    with pytest.raises((pc.LinkError, OSError, ConnectionError)):
        pr.connect("127.0.0.1", srv.port, code=info["code"], **RF)
    assert srv._pairing is not None


def test_hellos_alone_dont_use_up_the_code(server):
    srv, _ev = server
    info = pr.parse_pair_link(srv.open_pairing())
    for _ in range(10):                     # someone sends pairing hellos and goes away
        sock = socket.create_connection(("127.0.0.1", srv.port))
        sock.sendall(pr._plain_frame({"t": "hello", "v": [1], "mode": "pair"}))
        sock.close()
    time.sleep(0.3)
    s, _ = pr.connect("127.0.0.1", srv.port, code=info["code"], **RF)
    s.link.close()


def test_no_pairing_without_the_window(server):
    srv, _ev = server
    with pytest.raises(pc.LinkError, match="refused"):
        pr.connect("127.0.0.1", srv.port, code=os.urandom(32), **RF)


def test_expired_window(server, monkeypatch):
    srv, _ev = server
    info = pr.parse_pair_link(srv.open_pairing())
    srv._pairing["until"] = time.time() - 1
    with pytest.raises(pc.LinkError):
        pr.connect("127.0.0.1", srv.port, code=info["code"], **RF)


def test_a_forgotten_phone_cant_reconnect(server):
    srv, _ev = server
    sess, info = _pair(srv)
    sess.link.close()
    srv.forget(info["dev"])
    with pytest.raises(pc.LinkError, match="refused"):          # same answer as any refusal: tells nothing
        pr.connect("127.0.0.1", srv.port, dev=info["dev"], ltk=info["ltk"], **RF)


def test_wrong_long_term_key_is_refused(server):
    srv, _ev = server
    sess, info = _pair(srv)
    sess.link.close()
    with pytest.raises((pc.LinkError, OSError, ConnectionError)):
        s, _ = pr.connect("127.0.0.1", srv.port, dev=info["dev"], ltk=os.urandom(32), **RF)
        s.link.recv()


def test_old_or_new_versions_get_a_clear_answer(server):
    srv, _ev = server
    sock = socket.create_connection(("127.0.0.1", srv.port))
    sock.sendall(pr._plain_frame({"t": "hello", "v": [99], "mode": "pair"}))
    reply, _raw = pr._plain_recv(sock)
    assert reply == {"t": "error", "code": "version", "supported": [1]}
    sock.close()


def test_garbage_is_dropped(server):
    srv, _ev = server
    sock = socket.create_connection(("127.0.0.1", srv.port))
    sock.sendall(struct.pack(">I", 10 ** 9) + b"x" * 10)
    sock.settimeout(5)
    try:
        assert sock.recv(10) == b""      # closed on us
    except ConnectionResetError:
        pass
    sock.close()


def _make_music(folder):
    os.makedirs(os.path.join(folder, "Album", "CD1"), exist_ok=True)
    files = {"Album/CD1/01 Song.mp3": os.urandom(700_000), "Album/cover.jpg": os.urandom(5000),
             "Album/notes.exe": b"MZ" * 10}
    for rel, data in files.items():
        with open(os.path.join(folder, *rel.split("/")), "wb") as f:
            f.write(data)
    return files


def test_phone_sends_a_folder_to_the_computer(server, tmp_path):
    srv, ev = server
    sess, info = _pair(srv)
    phone_ev = Events()
    sess.events = phone_ev
    _run(sess)
    src = str(tmp_path / "phone")
    files = _make_music(src)
    sess.send_paths([os.path.join(src, "Album")], "My album")
    assert ev.done.wait(20) and phone_ev.done.wait(20)
    assert phone_ev.sent == [True]
    saved = ev.received[0]
    base = os.path.join(srv.receive_folder, "From Pixel")
    assert sorted(os.path.relpath(p, base).replace(os.sep, "/") for p in saved) == \
        ["Album/CD1/01 Song.mp3", "Album/cover.jpg"]                       # the .exe isn't taken
    with open(os.path.join(base, "Album", "CD1", "01 Song.mp3"), "rb") as f:
        assert f.read() == files["Album/CD1/01 Song.mp3"]
    assert not [n for n in os.listdir(os.path.join(base, "Album", "CD1")) if n.endswith(".part")]
    sess.link.close()


def test_computer_sends_to_the_phone_and_declining_saves_nothing(server, tmp_path):
    srv, ev = server
    phone_ev = Events(accept=False)
    sess, _info = _pair(srv, receive_folder=str(tmp_path / "phone_music"), events=phone_ev)
    _run(sess)
    assert _wait(lambda: srv.connected())
    src = str(tmp_path / "pc")
    _make_music(src)
    pc_sess = srv.connected()[0]
    pc_sess.send_paths([os.path.join(src, "Album", "CD1", "01 Song.mp3")])
    assert ev.done.wait(20)
    assert ev.sent == [False] and phone_ev.offers and not phone_ev.received
    assert not os.path.exists(str(tmp_path / "phone_music"))
    # accepting this time
    phone_ev.accept = True
    ev.done.clear()
    pc_sess.send_paths([os.path.join(src, "Album", "CD1", "01 Song.mp3")])
    assert ev.done.wait(20) and phone_ev.done.wait(20)
    assert ev.sent[-1] is True and len(phone_ev.received[0]) == 1
    sess.link.close()


def test_slow_handshakes_cant_block_others(server, monkeypatch):
    srv, _ev = server
    monkeypatch.setattr(pr, "HANDSHAKE_SECONDS", 2)
    slow = []
    for _ in range(4):                       # drip a byte now and then, never finishing
        sock = socket.create_connection(("127.0.0.1", srv.port))
        sock.sendall(struct.pack(">I", 900) + b"{")
        slow.append(sock)
    # at most two per address got in; a paired phone from elsewhere still connects (here: the same test address,
    # after the slow ones are cut off at the deadline)
    time.sleep(2.5)
    sess, _ = _pair(srv)
    sess.link.close()
    for s in slow:
        s.close()


def test_unproven_first_frame_is_small(server):
    srv, _ev = server
    info = pr.parse_pair_link(srv.open_pairing())
    sock = socket.create_connection(("127.0.0.1", srv.port))
    mine = pc.new_keypair()
    sock.sendall(pr._plain_frame({"t": "hello", "v": [1], "mode": "pair", "dev": "",
                                  "epk": pc.b64e(pc.public_bytes(mine)), "nonce": pc.b64e(os.urandom(32))}))
    pr._plain_recv(sock)
    sock.sendall(struct.pack(">I", 500_000))         # announces a big first frame without the key
    sock.settimeout(5)
    try:
        assert sock.recv(10) == b""
    except ConnectionResetError:
        pass
    sock.close()


def test_receiver_takes_each_file_once_and_no_more_than_offered(tmp_path):
    rec = pr.Receiver({"id": "a", "items": [("a.mp3", 3), ("b.mp3", 3)]}, str(tmp_path))
    rec.start_file(0)
    rec.data(b"abc")
    assert rec.end_file(0, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(pc.LinkError):
        rec.start_file(0)                            # the same file again
    rec.start_file(1)
    with pytest.raises(pc.LinkError):
        rec.start_file(1)
    rec.abort_file()


def test_one_file_at_a_time_and_ids_not_reused(server, tmp_path):
    srv, ev = server
    sess, _ = _pair(srv)
    assert _wait(lambda: srv.connected())
    pc_sess = srv.connected()[0]
    oid = "abc123"
    sess.link.send_json({"t": "offer", "id": oid, "items": [{"path": "a.mp3", "size": 3}]})
    assert _wait(lambda: ev.offers)                   # accepted by the Events helper
    sess.link.send_json({"t": "offer", "id": oid, "items": [{"path": "b.mp3", "size": 3}]})   # reused id
    time.sleep(0.3)
    assert len(ev.offers) == 1
    sess.link.close()


def test_bad_ids_and_deep_json_close_the_session_cleanly(server):
    srv, _ev = server
    sess, _ = _pair(srv)
    assert _wait(lambda: srv.connected())
    sess.link.send_json({"t": "answer", "id": ["x"], "accept": True})
    assert _wait(lambda: not srv.connected())          # not left listed as connected
    sess2, info = _pair(srv)
    assert _wait(lambda: srv.connected())
    sess2.link._send(pc.KIND_JSON, b'{"t":"x","a":' + b"[" * 50000 + b"]" * 50000 + b"}")
    assert _wait(lambda: not srv.connected())
    sess2.link.close()


def test_declined_offers_pause_more_offers(server, tmp_path):
    srv, ev = server
    ev.accept = False
    sess, _ = _pair(srv)
    assert _wait(lambda: srv.connected())
    for k in range(pr.DECLINES_BEFORE_PAUSE + 2):
        sess.link.send_json({"t": "offer", "id": f"o{k}", "items": [{"path": "a.mp3", "size": 3}]})
    time.sleep(0.5)
    assert len(ev.offers) == pr.DECLINES_BEFORE_PAUSE
    sess.link.close()


def test_names_cant_carry_markup_or_tricks():
    assert pr.clean_name("Pixel <b>x</b> & <img src=a>") == "Pixel bx/b  img src=a"
    assert pr.clean_name("Sev's PC") == "Sev's PC"
    assert "\u202e" not in pr.clean_name("a\u202eb")
    assert pr.safe_part("a\u202e3pm.m3u") == "a3pm.m3u"
    for bad in ("CON .mp3", "COM\u00b9.mp3", "conin$.mp3", "LPT0.flac", "aux.mp3"):
        assert pr.safe_part(bad).startswith("_"), bad
    assert pr.safe_relative("x" * 150 + "/" + "y" * 100 + ".mp3") is None      # too long a path


def test_hostile_offers_are_cleaned():
    bad = {"id": "x", "items": [{"path": "../../etc/passwd.mp3", "size": 5}, {"path": "/abs/x.mp3", "size": 5},
                                {"path": "C:\\Windows\\a.mp3", "size": 5}, {"path": "CON.mp3", "size": 1},
                                {"path": "ok/song.flac", "size": 10}, {"path": "evil.exe", "size": 1},
                                {"path": "big.jpg", "size": 10 ** 9}, {"path": "neg.mp3", "size": -1}]}
    items = pr.check_offer(bad)
    paths = [p.replace(os.sep, "/") for p, _s in items]
    assert "ok/song.flac" in paths
    assert all(".." not in p and not p.startswith("/") and ":" not in p for p in paths)
    assert "_CON.mp3" in paths and not any(p.endswith(".exe") or p == "big.jpg" for p in paths)
    assert not any(p == "neg.mp3" for p in paths)


def test_receiver_refuses_more_data_than_offered(tmp_path):
    rec = pr.Receiver({"id": "a", "items": [("a.mp3", 3)]}, str(tmp_path))
    rec.start_file(0)
    with pytest.raises(pc.LinkError):
        rec.data(b"abcd")
    assert not [n for n in os.listdir(tmp_path) if n.startswith("a.mp3")]


def test_receiver_drops_a_file_whose_checksum_is_wrong(tmp_path):
    rec = pr.Receiver({"id": "a", "items": [("a.mp3", 3), ("b.mp3", 3)]}, str(tmp_path))
    rec.start_file(0)
    rec.data(b"abc")
    assert rec.end_file(0, "0" * 64) is None and not [n for n in os.listdir(tmp_path) if n.startswith("a.mp3")]
    rec.start_file(1)
    rec.data(b"abc")
    assert rec.end_file(1, hashlib.sha256(b"abc").hexdigest()).endswith("b.mp3")


def test_receiver_never_overwrites(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"mine")
    rec = pr.Receiver({"id": "a", "items": [("a.mp3", 3)]}, str(tmp_path))
    rec.start_file(0)
    rec.data(b"new")
    out = rec.end_file(0, hashlib.sha256(b"new").hexdigest())
    assert out.endswith("a (2).mp3") and (tmp_path / "a.mp3").read_bytes() == b"mine"


def test_frames_cant_be_replayed_or_reflected():
    a = pc.Channel(b"k" * 32, b"j" * 32)
    b = pc.Channel(b"j" * 32, b"k" * 32)
    f1 = a.seal(pc.KIND_JSON, b"one")[4:]
    assert b.open(f1) == (pc.KIND_JSON, b"one")
    with pytest.raises(pc.LinkError):
        b.open(f1)                                   # replay
    with pytest.raises(pc.LinkError):
        a.open(a.seal(pc.KIND_JSON, b"x")[4:])       # our own frame sent back


def test_crypto_test_vector_is_stable():
    v = pc.test_vector()
    assert v == pc.test_vector()                     # deterministic
    assert v["c2s"] != v["s2c"] and len(v["first_frame"]) == 2 * (4 + 1 + 12 + 16)
    # Pinned: the phone apps are checked against these exact values.
    assert v["c2s"] == EXPECTED["c2s"] and v["s2c"] == EXPECTED["s2c"] and v["first_frame"] == EXPECTED["first_frame"]


EXPECTED = {"c2s": "8638dfdad0487dfde8d45c9487939f51f72828040e0c707ec4dfc5bdb4725b52",
            "s2c": "12fb672e706357a42565dacd9cb252aa46de1e3101aa2d1a9018c942128aa67e",
            "first_frame": "0000001d66d891584379f9cd9fcd93c63311ea622004319f5c86f7e1c96a625ae2"}


def test_a_taken_port_falls_back_and_is_kept(tmp_path):
    store = pr.DeviceStore(str(tmp_path))
    blockers = []
    for k in range(6):                                  # the kept port and its neighbours are taken
        b = socket.socket()
        try:
            b.bind(("0.0.0.0", store.port + k))
            b.listen(1)
            blockers.append(b)
        except OSError:
            b.close()
    srv = pr.PairServer(str(tmp_path), str(tmp_path / "m"), "PC", "1", Events())
    try:
        port = srv.start()
        assert port not in [b.getsockname()[1] for b in blockers]
        assert pr.DeviceStore(str(tmp_path)).port in (port, store.port)
    finally:
        srv.stop()
        for b in blockers:
            b.close()
