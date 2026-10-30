"""The iPhone app's door into Sevbify's shared Python code.

Swift (PyBridge.c) calls `call(name, args_json)`; everything goes in and out as JSON text. It reuses the Android
app's bridge (sevbify_bridge.py, copied in at build time), so the iPhone gets the same search, radio, full songs,
downloads, imports, podcasts and audiobooks as the other apps, plus a few iPhone-only helpers below.

The iPhone can't run other programs (no ffmpeg, no Deno), exactly like Android: downloads keep the original
audio, and streams ask for AAC/MP3 because the iPhone's player can't play WebM/Opus.
"""
import json
import os
import traceback

_started = {"done": False}


def _err(exc):
    return json.dumps({"ok": False, "error": str(exc) or type(exc).__name__,
                       "trace": traceback.format_exc()[-1500:]}, ensure_ascii=False)


def _prepare(data_dir):
    """Before any of core/ is imported: where Sevbify keeps its data, and iPhone-playable stream formats."""
    os.environ["SEVBIFY_DATA_DIR"] = data_dir
    os.environ.setdefault("HOME", os.path.dirname(data_dir))
    try:
        import certifi                       # web certificates for the online features (iOS has no system bundle)
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass
    from core import quality
    quality.STREAM_AUDIO_FORMAT = quality.IPHONE_STREAM_AUDIO_FORMAT
    _started["done"] = True


def call(name, args_json):
    try:
        args = json.loads(args_json or "[]")
        if not isinstance(args, list):
            args = [args]
        if name == "setup" and args:
            _prepare(args[0])
        if name in _LOCAL:
            return json.dumps({"ok": True, "value": _LOCAL[name](*args)}, ensure_ascii=False)
        import sevbify_bridge as bridge
        fn = getattr(bridge, name, None)
        if name.startswith("_") or not callable(fn):
            return json.dumps({"ok": False, "error": f"unknown function {name}"})
        return fn(*args)                     # the bridge already answers {"ok": ..., "value"/"error": ...}
    except Exception as exc:                 # never crash the app: errors go back to Swift as text
        return _err(exc)


# --- iPhone-only helpers ------------------------------------------------------------------------------------
AUDIO_EXT = (".mp3", ".m4a", ".aac", ".flac", ".wav", ".aiff", ".aif", ".alac", ".caf", ".mp4", ".ogg", ".opus")


def scan_folder(folder, art_dir="", limit=20000):
    """Songs in a folder you added (and its sub-folders), with their tags. Only that folder is read.
    With art_dir, each song's embedded cover is saved there once (as <hash>.jpg) and returned as "art"."""
    import hashlib
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            if f.lower().endswith(AUDIO_EXT) and not f.startswith("."):
                path = os.path.join(root, f)
                info = read_tags(path)
                if art_dir:
                    rel = os.path.relpath(path, folder)
                    name = hashlib.sha1(rel.encode("utf-8"), usedforsecurity=False).hexdigest()[:20] + ".jpg"
                    target = os.path.join(art_dir, name)
                    info["art"] = target if os.path.isfile(target) else cover_art(path, target)
                out.append(info)
                if len(out) >= limit:
                    return out
    return out


def read_tags(path):
    """Title / artist / album / length of one audio file (from its tags, or its file name)."""
    info = {"path": path, "title": os.path.splitext(os.path.basename(path))[0], "artist": "", "album": "",
            "duration_ms": 0}
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(path, easy=True)
        if audio is not None:
            if getattr(audio, "info", None) is not None and getattr(audio.info, "length", 0):
                info["duration_ms"] = int(audio.info.length * 1000)
            tags = audio.tags or {}

            def first(*keys):
                for k in keys:
                    v = tags.get(k) if hasattr(tags, "get") else None
                    if v:
                        return str(v[0] if isinstance(v, list) else v).strip()
                return ""
            info["title"] = first("title") or info["title"]
            info["artist"] = first("artist", "albumartist")
            info["album"] = first("album")
    except Exception:
        pass
    if not info["artist"] and " - " in info["title"]:
        info["artist"], info["title"] = [p.strip() for p in info["title"].split(" - ", 1)]
    info["artist"] = info["artist"] or "Unknown Artist"
    return info


def cover_art(path, out_path):
    """Save a song file's embedded cover picture to out_path; returns out_path, or "" when it has none."""
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(path)
        data = None
        if audio is not None and audio.tags is not None:
            tags = audio.tags
            for key in list(tags.keys()):
                if key.startswith("APIC"):
                    data = tags[key].data
                    break
            if data is None and "covr" in tags:
                data = bytes(tags["covr"][0])
            if data is None and hasattr(audio, "pictures") and audio.pictures:
                data = audio.pictures[0].data
        if data:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            return out_path
    except Exception:
        pass
    return ""


def python_info():
    import sys
    import platform
    info = {"python": sys.version.split()[0], "platform": sys.platform, "machine": platform.machine()}
    try:
        from core import downloader
        info["yt_dlp"] = downloader.engine().ytdlp_version()
    except Exception as exc:
        info["yt_dlp"] = f"not loaded: {exc}"
    return info


_LOCAL = {"scan_folder": scan_folder, "read_tags": read_tags, "cover_art": cover_art, "python_info": python_info}
