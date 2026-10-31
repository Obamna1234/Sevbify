"""Where your music servers' sign-ins are kept.

The non-secret details (server address, user name, device id, display name) live in servers.json in
Sevbify's data folder. The *secret* part — the Jellyfin access token or the Nextcloud app password — is kept
in the operating system's secure store (Windows Credential Manager, macOS Keychain, Linux Secret Service)
through `keyring`, not written into the file.

If no secure store is available (or `keyring` isn't installed), it falls back to the previous behaviour: the
secret is written into servers.json, which is made private to your user (0600 on Mac / Linux; inside your own
AppData on Windows). Either way the sign-in is never part of the profile file, playlists or logs.
"""
import json
import os

from core.servers import SOURCES

try:
    import keyring as _keyring
except Exception:
    _keyring = None

# The label the secrets appear under in the OS secure store.
_SERVICE = "Sevbify music servers"
# The fields that are actual credentials (kept out of the file when a secure store is available).
_SECRET_FIELDS = ("token", "password")


def path(data_dir):
    return os.path.join(data_dir, "servers.json")


def _secure_store():
    """Return the keyring module only if a real (non-null) secure backend is usable, else None.

    keyring picks a "fail"/null backend when no real one is present (e.g. a headless Linux box with no
    Secret Service). In that case we must NOT rely on it, so we fall back to the file.
    """
    if _keyring is None:
        return None
    try:
        from keyring.backends import fail as _fail
        if isinstance(_keyring.get_keyring(), _fail.Keyring):
            return None
    except Exception:
        return None
    return _keyring


def _entry(server_id, field):
    return f"{server_id}:{field}"


def load(data_dir):
    try:
        with open(path(data_dir), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    kr = _secure_store()
    out = []
    for s in data:
        if not (isinstance(s, dict) and s.get("type") in SOURCES and s.get("id") and s.get("url")):
            continue
        if kr is not None:
            for field in _SECRET_FIELDS:
                if not s.get(field):                      # secret lives in the store, not the file
                    try:
                        value = kr.get_password(_SERVICE, _entry(s["id"], field))
                    except Exception:
                        value = None
                    if value:
                        s[field] = value
        out.append(s)
    return out


def save(data_dir, servers):
    os.makedirs(data_dir, exist_ok=True)
    kr = _secure_store()
    to_write = []
    for s in servers:
        s = dict(s)                                       # don't mutate the caller's objects
        if kr is not None:
            for field in _SECRET_FIELDS:
                secret = s.get(field)
                if not secret:
                    continue
                try:
                    kr.set_password(_SERVICE, _entry(s["id"], field), secret)
                    # Only drop the secret from the file once we've confirmed it reads back from the
                    # store — so a silently-failing backend can never lose your sign-in.
                    if kr.get_password(_SERVICE, _entry(s["id"], field)) == secret:
                        s[field] = ""
                except Exception:
                    pass                                  # leave the secret in the (private) file
        to_write.append(s)
    p = path(data_dir)
    tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(to_write, f)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
