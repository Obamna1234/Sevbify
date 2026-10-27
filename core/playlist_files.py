"""Playlist files (.m3u8) next to downloaded music, so the same playlists, in the same order, work on a phone
or in any music player after copying the folder. No UI code.

Each playlist becomes <download folder>/Playlists/<name>.m3u8 with paths relative to that file, so the folder
can be moved or copied as a whole. Songs stored once in Artist folders can be in many playlists. Songs not
downloaded yet are listed as comments. Only files Sevbify made (they carry MARKER) are ever replaced or removed.
"""
import os
import re

MARKER = "#SEVBIFY-PLAYLIST"
FOLDER = "Playlists"


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*]', "_", name or "").strip(" .")
    return name[:120] or "Playlist"


def playlist_text(songs, playlist_dir):
    lines = ["#EXTM3U", MARKER]
    for s in songs:
        if getattr(s, "is_remote", False):
            lines.append(f"# not downloaded yet: {s.artist} - {s.title}")
            continue
        path = s.file_path
        try:
            rel = os.path.relpath(path, playlist_dir)          # fails across Windows drives (C: vs D:)
        except ValueError:
            rel = path
        seconds = int((getattr(s, "duration", 0) or 0) / 1000) or -1
        lines.append(f"#EXTINF:{seconds},{s.artist} - {s.title}")
        lines.append(rel.replace("\\", "/"))
    return "\n".join(lines) + "\n"


def _made_by_us(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return MARKER in f.read(200)
    except OSError:
        return False


def write_playlist_files(download_folder, playlists):
    """Write one .m3u8 per playlist and remove ones Sevbify made for playlists that no longer exist.
    Returns the list of files written."""
    playlist_dir = os.path.join(download_folder, FOLDER)
    os.makedirs(playlist_dir, exist_ok=True)
    written, used = [], set()
    for pl in playlists:
        name = safe_name(pl.name)
        while name.casefold() in used:
            name += "_"
        used.add(name.casefold())
        path = os.path.join(playlist_dir, name + ".m3u8")
        if os.path.exists(path) and not _made_by_us(path):
            continue                                            # never overwrite the user's own file
        text = playlist_text(pl.songs, playlist_dir)
        try:
            with open(path, encoding="utf-8") as f:
                if f.read() == text:
                    written.append(path)
                    continue
        except OSError:
            pass
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(path)
    for f in os.listdir(playlist_dir):
        full = os.path.join(playlist_dir, f)
        if f.lower().endswith(".m3u8") and full not in written and _made_by_us(full):
            os.remove(full)
    return written
