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
    folder = os.path.dirname(song_path)
    out = [folder, os.path.join(folder, "canvas")]
    if data_dir:
        out.append(os.path.join(data_dir, "canvas"))
    return out


def find_canvas(song, data_dir=None):
    base = os.path.splitext(os.path.basename(song.file_path))[0]
    names = [base, _safe(f"{song.artist} - {song.title}")]
    folders = canvas_folders(song.file_path, data_dir)
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
        for folder in folders[1:]:
            for ext in VIDEO_EXTS:
                p = os.path.join(folder, _safe(song.artist) + ext)
                if os.path.isfile(p):
                    return p
    return None
