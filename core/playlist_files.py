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


# --- Export / copy for phones and other players (File → Share in a playlist's menu) ---------------------------
def export_playlist(songs, path, absolute=False):
    """Write one playlist file at `path` (.m3u8). Paths are relative to the file's folder unless that's not
    possible (another drive) or absolute=True. Returns (songs written, songs not downloaded yet)."""
    folder = os.path.dirname(os.path.abspath(path))
    lines = ["#EXTM3U"]
    written = pending = 0
    for s in songs:
        if getattr(s, "is_remote", False) or not getattr(s, "exists", True):
            lines.append(f"# not downloaded yet: {s.artist} - {s.title}")
            pending += 1
            continue
        target = s.file_path
        if not absolute:
            try:
                target = os.path.relpath(s.file_path, folder)
            except ValueError:
                target = s.file_path
        seconds = int((getattr(s, "duration", 0) or 0) / 1000) or -1
        lines.append(f"#EXTINF:{seconds},{s.artist} - {s.title}")
        lines.append(target.replace("\\", "/") if not os.path.isabs(target) else target)
        written += 1
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return written, pending


def copy_playlist(songs, dest_folder, name, numbered=True, should_stop=lambda: False, progress=None):
    """Copy the playlist's music files into dest_folder/<name>/ in playlist order ("01 - Artist - Title.mp3"),
    plus <name>.m3u8 inside it, ready for a phone or USB stick. Files already there with the same size are not
    copied again. Returns {"copied", "skipped", "pending", "folder", "playlist"}."""
    import shutil
    out = os.path.join(dest_folder, safe_name(name))
    os.makedirs(out, exist_ok=True)
    files = [s for s in songs if not getattr(s, "is_remote", False) and getattr(s, "exists", True)]
    width = max(2, len(str(len(files))))
    lines = ["#EXTM3U"]
    copied = skipped = 0
    for i, s in enumerate(files, 1):
        if should_stop():
            break
        ext = os.path.splitext(s.file_path)[1]
        base = safe_name(f"{s.artist} - {s.title}") if s.artist and s.artist != "Unknown Artist" else \
            safe_name(os.path.splitext(os.path.basename(s.file_path))[0])
        fname = (f"{i:0{width}d} - " if numbered else "") + base + ext
        target = os.path.join(out, fname)
        try:
            if os.path.exists(target) and os.path.getsize(target) == os.path.getsize(s.file_path):
                skipped += 1
            else:
                shutil.copy2(s.file_path, target)
                copied += 1
        except OSError:
            continue
        seconds = int((getattr(s, "duration", 0) or 0) / 1000) or -1
        lines.append(f"#EXTINF:{seconds},{s.artist} - {s.title}")
        lines.append(fname)
        if progress is not None:
            progress(i, len(files))
    playlist = os.path.join(out, safe_name(name) + ".m3u8")
    with open(playlist, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return {"copied": copied, "skipped": skipped, "pending": len(songs) - len(files), "folder": out,
            "playlist": playlist}
