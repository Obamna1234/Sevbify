"""Find a short looping video ("canvas") to show behind a song's artwork.

Spotify's Canvas videos are not available to other apps, so Sevbify uses
videos you provide. For a song file  D:\\Music\\Mega Drive - NARC.mp3  it looks for,
in order (first match wins; .mp4, .webm, .mov, .m4v):

  1. D:\\Music\\Mega Drive - NARC.mp4             same name, next to the song
  2. D:\\Music\\canvas\\Mega Drive - NARC.mp4      a "canvas" folder next to the song
  3. <Sevbify data folder>\\canvas\\Mega Drive - NARC.mp4
  4. ...\\canvas\\Mega Drive.mp4                    one video for every song by that artist
"""
import os
import re

VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v")


def _safe(name):
    return re.sub(r'[\\/:"*?<>|]', "_", name or "").strip()


def canvas_folders(song_path, data_dir=None):
    folder = os.path.dirname(song_path or "")
    out = [folder, os.path.join(folder, "canvas")] if folder else []
    if data_dir:
        out.append(os.path.join(data_dir, "canvas"))
    return out


def find_canvas(song, data_dir=None):
    path = getattr(song, "file_path", "") or ""
    base = os.path.splitext(os.path.basename(path))[0] if path else ""
    names = [n for n in (base, _safe(f"{song.artist} - {song.title}")) if n]
    folders = canvas_folders(path if not getattr(song, "is_remote", False) else "", data_dir)
    for i, folder in enumerate(folders):
        if not os.path.isdir(folder):
            continue
        for name in names:
            for ext in VIDEO_EXTS:
                p = os.path.join(folder, name + ext)
                if os.path.isfile(p):
                    return p
    # Artist-wide video, only in canvas folders (not loose next to songs).
    if song.artist and song.artist != "Unknown Artist":
        for folder in [f for f in folders if os.path.basename(f) == "canvas"]:
            for ext in VIDEO_EXTS:
                p = os.path.join(folder, _safe(song.artist) + ext)
                if os.path.isfile(p):
                    return p
    return None


def set_canvas(song, video_path, data_dir):
    """Use a video as this song's Canvas: copied to <data folder>/canvas/<Artist - Title>.<ext>."""
    import shutil
    ext = os.path.splitext(video_path)[1].lower()
    if ext not in VIDEO_EXTS:
        raise ValueError("Choose an .mp4, .webm, .mov or .m4v video.")
    folder = os.path.join(data_dir, "canvas")
    os.makedirs(folder, exist_ok=True)
    name = _safe(f"{song.artist} - {song.title}")
    for e in VIDEO_EXTS:                                 # one Canvas per song
        old = os.path.join(folder, name + e)
        if os.path.isfile(old):
            os.remove(old)
    target = os.path.join(folder, name + ext)
    shutil.copy2(video_path, target)
    return target


def remove_canvas(song, data_dir):
    """Remove a Canvas added with set_canvas (videos you keep next to your music are never deleted)."""
    folder = os.path.join(data_dir, "canvas")
    removed = False
    for e in VIDEO_EXTS:
        p = os.path.join(folder, _safe(f"{song.artist} - {song.title}") + e)
        if os.path.isfile(p):
            os.remove(p)
            removed = True
    return removed
