"""Scanning music folders into Song objects. No Qt imports."""
import os

from .models import Song, SUPPORTED_EXTENSIONS

# A folder holding this file (and everything inside it) is never scanned for songs. Sevbify puts it in its
# podcast and audiobook download folders, so episodes and chapters don't show up as music.
NO_SCAN_MARKER = ".sevbify-noscan"


def mark_no_scan(folder):
    """Create `folder` and mark it as not music (see NO_SCAN_MARKER)."""
    os.makedirs(folder, exist_ok=True)
    marker = os.path.join(folder, NO_SCAN_MARKER)
    if not os.path.exists(marker):
        with open(marker, "w", encoding="utf-8") as f:
            f.write("Podcasts and audiobooks downloaded by Sevbify: not shown in Your Songs.\n")
    return folder


def scan_folders(folders, recursive=True, should_stop=lambda: False):
    """Return a sorted, de-duplicated list of Songs found in the given folders.

    Missing folders are skipped (reported in the returned 'problems' list).
    should_stop: callable checked between files so a scan can be cancelled.
    """
    songs = {}
    problems = []
    for folder in folders:
        if not os.path.isdir(folder):
            problems.append(f"Folder not found: {folder}")
            continue
        if recursive:
            walker = os.walk(folder)
        else:
            walker = [(folder, [], os.listdir(folder))]
        for root, dirs, files in walker:
            if NO_SCAN_MARKER in files:
                dirs[:] = []
                continue
            dirs.sort()
            for name in sorted(files):
                if should_stop():
                    return _sorted(songs), problems
                if not name.lower().endswith(SUPPORTED_EXTENSIONS):
                    continue
                path = os.path.join(root, name)
                try:
                    song = Song(path)
                except Exception as e:  # never let one bad file stop the scan
                    problems.append(f"Skipped {path}: {e}")
                    continue
                songs.setdefault(song.key, song)
    return _sorted(songs), problems


def _sorted(songs_by_key):
    # Same order as before (by file name), then by full path for ties.
    return sorted(songs_by_key.values(),
                  key=lambda s: (os.path.basename(s.file_path).casefold(), s.key))
