"""Signed updates: the computer app only installs an update signed with Sevbify's own release key.

Each release has a small file, Sevbify-update-signatures.json, made by the release build with a secret key that
only exists as a GitHub secret (UPDATE_SIGNING_KEY) and in the owner's offline backup, never in this code. For each
download it holds an Ed25519 signature over the release's tag, the file's name and its SHA-256. Sevbify checks that
signature with the public key below before installing anything, so a file swapped on the release page (or a fake
release published from a stolen GitHub account) is refused.

Phones are protected already: Android only installs an update signed with the same app key, and the iPhone app is
installed through SideStore / AltStore.
"""
import base64
import json

# The public half of Sevbify's update key (safe to publish; it can only check signatures, not make them).
PUBLIC_KEY_HEX = "883c057e4f27718282450a065ac6df9799cf25b825e10412f48e5714b6fd20bd"
SIGNATURES_NAME = "Sevbify-update-signatures.json"
MAX_SIGNATURES_BYTES = 64 * 1024


class SignatureError(Exception):
    pass


def message(tag, name, sha256):
    return f"sevbify-update-v1\n{tag}\n{name}\n{sha256.lower()}".encode("utf-8")


def _verifier(public_hex=None):
    from Cryptodome.Signature import eddsa
    return eddsa.new(eddsa.import_public_key(bytes.fromhex(public_hex or PUBLIC_KEY_HEX)), "rfc8032")


def sign(seed_hex, tag, name, sha256):
    """Used by the release build (tools/sign_release.py). seed_hex: the 32-byte private key as hex."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa
    key = ECC.construct(curve="Ed25519", seed=bytes.fromhex(seed_hex.strip()))
    return base64.b64encode(eddsa.new(key, "rfc8032").sign(message(tag, name, sha256))).decode("ascii")


def public_from_seed(seed_hex):
    from Cryptodome.PublicKey import ECC
    key = ECC.construct(curve="Ed25519", seed=bytes.fromhex(seed_hex.strip()))
    return key.public_key().export_key(format="raw").hex()


def check(signatures_text, tag, name, sha256, public_hex=None):
    """Raise SignatureError unless signatures_text signs (tag, name, sha256) with Sevbify's key."""
    if not signatures_text or len(signatures_text) > MAX_SIGNATURES_BYTES:
        raise SignatureError("This update has no valid signature, so it wasn't installed.")
    try:
        data = json.loads(signatures_text)
        entry = data["files"][name]
        if str(data.get("tag")) != tag or str(entry.get("sha256", "")).lower() != sha256.lower():
            raise ValueError("mismatch")
        _verifier(public_hex).verify(message(tag, name, sha256), base64.b64decode(entry["signature"], validate=True))
    except SignatureError:
        raise
    except Exception:
        raise SignatureError("This update isn't signed with Sevbify's release key, so it wasn't installed. "
                             "Download Sevbify from its official release page instead.")


def parse_release_url(url):
    """(signatures URL, tag, file name) for a GitHub release download link, or raise SignatureError."""
    import re
    m = re.fullmatch(r"(https://github\.com/Obamna1234/Sevbify/releases/download/)([^/?#]+)/([^/?#]+)", url or "")
    if not m:
        raise SignatureError("That isn't a Sevbify release download, so it wasn't installed.")
    return m.group(1) + m.group(2) + "/" + SIGNATURES_NAME, m.group(2), m.group(3)
