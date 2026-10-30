"""Where your music servers' sign-ins are kept: servers.json in Sevbify's data folder, readable only by you
(on Mac / Linux the file is made private to your user; on Windows it's inside your own AppData). It's never part of
the profile file, playlists or logs."""
import json
import os

from core.servers import SOURCES


def path(data_dir):
    return os.path.join(data_dir, "servers.json")


def load(data_dir):
    try:
        with open(path(data_dir), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [s for s in data if isinstance(s, dict) and s.get("type") in SOURCES and s.get("id") and s.get("url")]


def save(data_dir, servers):
    os.makedirs(data_dir, exist_ok=True)
    p = path(data_dir)
    tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(servers, f)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
