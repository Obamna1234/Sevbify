"""The encrypted link between Sevbify on a computer and Sevbify on a phone (same Wi-Fi only).

Handshake (version 1). The phone ("client") connects to the computer ("server"):

  client -> server   hello  {"t": "hello", "v": [1], "mode": "pair" | "resume", "dev": "",
                              "tag": <resume only: device_tag(its long-term key, nonce): which phone, without
                                      saying a fixed id in the open>,
                              "epk": <client's one-time P-256 public key, SEC1 uncompressed, base64>,
                              "nonce": <32 random bytes, base64>}
  server -> client   hello  {"t": "hello", "v": 1, "epk": ..., "nonce": ...}

Both sides then compute
  secret  = ECDH(one-time keys)                                  (forward secrecy)
  psk     = the 32-byte code from the QR code ("pair"), or the device's long-term key ("resume")
  salt    = SHA-256("sevbify-pair-v1" | mode | "|" | dev | "|" | c_nonce | s_nonce | c_epk | s_epk
                    | SHA-256(client hello frame) | SHA-256(server hello frame))
            (the hello frames exactly as sent: 4-byte length + JSON bytes, so the offered and chosen versions are
            covered too: nobody in between can remove a newer version from the list unnoticed)
  prk     = HMAC-SHA256(salt, secret | psk)                       (HKDF-Extract)
  keys    = HKDF-Expand(prk, "sevbify v1 keys", 64) -> c2s key (32) | s2c key (32)

Everything after the hellos is AES-256-GCM, each direction with its own key and a counter nonce (4 zero bytes then
an 8-byte big-endian counter, starting at 0), so a frame can't be replayed, reordered or reflected. Someone without
the QR code (or the long-term key) can't make a frame the other side accepts, so the first good frame also proves
who is talking. Frames are length-prefixed: 4-byte big-endian length, then ciphertext + 16-byte tag.

Before the keys exist, a computer may answer the hello with a plain {"t": "error", "code": ...}. Nothing checks it,
so a phone only shows it ("Scan the code again") and never deletes its pairing because of it.

Plain-text inside a frame: one kind byte (1 = JSON message, 2 = raw file data) and the payload.

Only standard primitives are used (P-256, SHA-256, HMAC, AES-GCM), so the phone apps implement exactly the same
with their system libraries (Android: java.security / javax.crypto; iPhone: CryptoKit). `test_vector()` gives fixed
inputs and outputs those implementations are checked against.
"""
import base64
import hashlib
import hmac
import os
import struct

from Cryptodome.Cipher import AES
from Cryptodome.Protocol.DH import key_agreement
from Cryptodome.PublicKey import ECC

VERSION = 1
SUPPORTED = (1,)
LABEL = b"sevbify-pair-v1"
MAX_FRAME = 1 << 20            # 1 MiB of ciphertext per frame
KIND_JSON, KIND_DATA = 1, 2


class LinkError(Exception):
    """The other side isn't a Sevbify we trust, or the connection broke the protocol."""


def b64e(b):
    return base64.b64encode(b).decode("ascii")


def b64d(s, size=None, limit=4096):
    if not isinstance(s, str) or len(s) > limit:
        raise LinkError("bad field")
    try:
        out = base64.b64decode(s, validate=True)
    except Exception:
        raise LinkError("bad base64")
    if size is not None and len(out) != size:
        raise LinkError("bad length")
    return out


def new_keypair():
    return ECC.generate(curve="P-256")


def public_bytes(key):
    return key.public_key().export_key(format="SEC1", compress=False)       # 65 bytes, 0x04 | X | Y


def load_public(raw):
    if len(raw) != 65 or raw[0] != 4:
        raise LinkError("bad key")
    try:
        return ECC.import_key(raw, curve_name="P-256")                     # checks the point is on the curve
    except Exception:
        raise LinkError("bad key")


def ecdh(private, peer_public):
    return key_agreement(eph_priv=private, eph_pub=peer_public, kdf=lambda z: z)    # 32-byte X coordinate


def hkdf_expand(prk, info, length):
    out, block, i = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([i]), hashlib.sha256).digest()
        out += block
        i += 1
    return out[:length]


def derive_keys(secret, psk, mode, dev, c_nonce, s_nonce, c_epk, s_epk, c_hello, s_hello):
    """-> (client-to-server key, server-to-client key). c_hello / s_hello: the hello frames as sent."""
    salt = hashlib.sha256(LABEL + mode.encode() + b"|" + dev.encode() + b"|" + c_nonce + s_nonce + c_epk
                          + s_epk + hashlib.sha256(c_hello).digest() + hashlib.sha256(s_hello).digest()).digest()
    prk = hmac.new(salt, secret + psk, hashlib.sha256).digest()
    okm = hkdf_expand(prk, b"sevbify v1 keys", 64)
    return okm[:32], okm[32:]


class Channel:
    """Encrypts what we send and checks/decrypts what we get, with per-direction counters."""

    def __init__(self, send_key, recv_key):
        self.send_key, self.recv_key = send_key, recv_key
        self.send_n = 0
        self.recv_n = 0

    @staticmethod
    def _nonce(n):
        return b"\0\0\0\0" + struct.pack(">Q", n)

    def seal(self, kind, payload):
        if self.send_n >= (1 << 63):
            raise LinkError("too many frames")
        c = AES.new(self.send_key, AES.MODE_GCM, nonce=self._nonce(self.send_n))
        self.send_n += 1
        ct, tag = c.encrypt_and_digest(bytes([kind]) + payload)
        body = ct + tag
        return struct.pack(">I", len(body)) + body

    def open(self, body):
        if len(body) < 17 or len(body) > MAX_FRAME + 64:
            raise LinkError("bad frame size")
        c = AES.new(self.recv_key, AES.MODE_GCM, nonce=self._nonce(self.recv_n))
        try:
            plain = c.decrypt_and_verify(body[:-16], body[-16:])
        except ValueError:
            raise LinkError("frame failed its check")
        self.recv_n += 1
        return plain[0], plain[1:]


def test_vector():
    """Fixed handshake inputs -> keys and a first frame, for the phone apps' tests (Kotlin/Swift do the same)."""
    c_priv = ECC.construct(curve="P-256", d=int("11" * 32, 16))
    s_priv = ECC.construct(curve="P-256", d=int("22" * 32, 16))
    c_epk, s_epk = public_bytes(c_priv), public_bytes(s_priv)
    secret = ecdh(c_priv, load_public(s_epk))
    psk = bytes(range(32))
    c_nonce, s_nonce = b"\x01" * 32, b"\x02" * 32
    c_hello, s_hello = b"\0\0\0\x02{}", b"\0\0\0\x03[1]"
    c2s, s2c = derive_keys(secret, psk, "pair", "", c_nonce, s_nonce, c_epk, s_epk, c_hello, s_hello)
    frame = Channel(c2s, s2c).seal(KIND_JSON, b'{"t":"ping"}')
    return {"c_hello": c_hello.hex(), "s_hello": s_hello.hex(), "c_epk": c_epk.hex(), "s_epk": s_epk.hex(), "secret": secret.hex(), "psk": psk.hex(),
            "c_nonce": c_nonce.hex(), "s_nonce": s_nonce.hex(), "c2s": c2s.hex(), "s2c": s2c.hex(),
            "first_frame": frame.hex()}


def device_tag(ltk, c_nonce):
    """A one-time tag that tells the computer which paired phone is calling, without a fixed id anyone on the
    network could follow: HMAC-SHA256(long-term key, "sevbify-dev-tag" | nonce), first 16 bytes, hex."""
    return hmac.new(ltk, b"sevbify-dev-tag" + c_nonce, hashlib.sha256).digest()[:16].hex()


def random_bytes(n):
    return os.urandom(n)
