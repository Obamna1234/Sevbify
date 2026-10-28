"""Scanning music folders into Song objects. No Qt imports."""
import os

from .models import Song, SUPPORTED_EXTENSIONS

# beta.6 put this hidden file in the podcast and audiobook download folders so they weren't scanned as music.
# Sevbify now keeps that list itself (skip=...), and removes its old marker files when it sees them.
OLD_NO_SCAN_MARKER = ".sevbify-noscan"


def remove_old_marker(folder):
    """Delete the marker file beta.6 left in `folder` (only our own one-line file)."""
    marker = os.path.join(folder, OLD_NO_SCAN_MARKER)
    try:
        if os.path.isfile(marker) and os.path.getsize(marker) < 200:
            os.remove(marker)
    except OSError:
        pass


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def scan_folders(folders, recursive=True, should_stop=lambda: False, skip=()):
    """Return a sorted, de-duplicated list of Songs found in the given folders.

    Missing folders are skipped (reported in the returned 'problems' list).
    should_stop: callable checked between files so a scan can be cancelled.
    skip: folders that are never scanned (Sevbify's podcast and audiobook downloads).
    """
    songs = {}
    problems = []
    skip = {_norm(f) for f in skip if f}
    for folder in folders:
        if not os.path.isdir(folder):
            problems.append(f"Folder not found: {folder}")
            continue
        if recursive:
            walker = os.walk(folder)
        else:
            walker = [(folder, [], os.listdir(folder))]
        for root, dirs, files in walker:
            if (skip and _norm(root) in skip) or OLD_NO_SCAN_MARKER in files:
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
