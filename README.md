# Custom Spotify Replica — Local Music Player

A Spotify-inspired desktop music player for local files, built with Python, PyQt6 and VLC.
Windows is the first target platform.

**Current version:** v4.9 — library, search, saved playlists, volume. See `CHANGELOG.md`.

## Requirements

| What | Version | Notes |
|---|---|---|
| Windows | 10 or 11, 64-bit | |
| Python | 3.10 – 3.13, **64-bit** | https://www.python.org/downloads/ — tick "Add python.exe to PATH" |
| VLC media player | 3.0.x, **64-bit** | https://www.videolan.org/vlc/ — must match Python's 64-bit; the app uses VLC's engine (libVLC) for playback |
| Python packages | see `requirements.txt` | PyQt6, python-vlc, mutagen, Pillow, pytest |

## Quick start (recommended)

**One-time setup**
1. Install **64-bit Python 3.12** (https://www.python.org/downloads/, tick *Add python.exe to PATH*)
   and **64-bit VLC** (https://www.videolan.org/vlc/).
2. In GitHub Desktop: **File → Clone repository → Spotify-Replica**.
3. Optional: copy your music into the clone's `audio` folder (it stays on your PC and is never
   uploaded), or skip this and use **Your Library → Add folder…** in the app.
   With no `audio` folder, the app uses your Windows *Music* folder.

**Every time there's an update**
1. GitHub Desktop → **Fetch origin** → **Pull origin**.
2. Double-click **`Run Spotify Replica.bat`**.

The first run sets up a private Python environment (about a minute). After that it starts
straight away, and re-installs packages automatically only when an update needs it.
`Run Tests.bat` runs the automated tests.

**Ready-made .exe (no Python needed):** every push is built and tested on a real Windows machine
by GitHub Actions. Open the repo's **Actions** tab → latest *Windows build & tests* run →
download **Spotify-Replica-Windows** → unzip → run `Spotify Replica.exe` (VLC must be installed).

## Manual setup (Windows, PowerShell)

Open PowerShell **in the project folder** (in File Explorer: Shift + right-click the folder → "Open in Terminal"), then:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run this once and then try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Running the app

```powershell
.\.venv\Scripts\Activate.ps1      # if not already active
python app.py
```

You can also launch it from any folder, e.g. `python "C:\path\to\spotify-replica\app.py"` —
music and artwork are found relative to the project folder.

## Using the app

| Where | What you can do |
|---|---|
| **Home** | Click a cover to play. Right-click for *Add to playlist*. |
| **Search** | Type to filter by song, artist or album. Double-click a result to play (next/previous stay within the results). |
| **Your Library** | Every song as a list. Click a column header to sort. **Add folder…** adds a music folder (sub-folders included); **✕** removes it (files are never deleted); **Rescan** picks up new files. |
| **Playlists** | Click a playlist to open it; click its green ▶ to play it. **Create Playlist** to make one (songs optional). |
| **A playlist** | Play, Rename, Delete. Right-click a song to move it up/down, remove it, or add it to another playlist. |
| **Player bar** | Play/pause, previous (restarts the song if > 3 s in), next, seek, volume and mute. |

**Keyboard:** Space = play/pause · Ctrl+→ / Ctrl+← = next / previous · Ctrl+↑ / Ctrl+↓ = volume · Ctrl+F = search · Ctrl+L = library

## Adding music

Either put `.mp3`, `.wav`, `.flac`, `.ogg` or `.m4a` files in the bundled `audio` folder and
press **Rescan**, or use **Your Library → Add folder…** to add any folder on your PC.
Artwork comes from (in order): an image in `assets` with the same name as the audio file,
art embedded in the file's tags, or a placeholder.

## Where your playlists and settings are saved

`%APPDATA%\Custom Spotify Replica\library.json` (paste that into File Explorer's address bar).
Playlists, volume and music folders are saved automatically. Songs inside the project folder are
saved with relative paths, so moving the project folder doesn't break playlists. If a song's
file goes missing, it stays in the playlist greyed out as "(file missing)" instead of being
removed. If the save file is ever damaged, the app keeps a copy (`library.corrupt-<date>.json`)
and starts fresh rather than crashing. Delete `library.json` to reset to first-run state.

## Running the automated tests

```powershell
python -m pytest tests -v
```

The tests generate short WAV tones and play them through VLC's silent dummy output in a
hidden window, so they make no sound and don't touch your music. They need VLC installed.

## Project layout

| Path | Purpose |
|---|---|
| `Run Spotify Replica.bat` | One-click launcher (sets up Python packages automatically) |
| `Run Tests.bat` | Runs the automated tests |
| `.github/workflows/windows-build.yml` | Automatic Windows tests + `.exe` build on every push |
| `app.py` | Entry point. Shows a clear message if VLC is missing. `--smoke-test` starts, loads the library and exits (used by the automatic build). |
| `core/` | Data and logic with no UI code: `paths.py`, `models.py` (Song, Playlist), `library.py` (folder scanning), `storage.py` (save file) |
| `ui/main_window.py` | Main window: pages, player bar, playback, playlist actions |
| `ui/track_table.py` | Song list used by Search, Your Library and playlist pages |
| `ui/sidebar.py` | Navigation sidebar |
| `ui/Playlist_View.py`, `ui/Home_View.py`, `ui/player_bar.py`, `test_home.py` | **Legacy / unused** by the running app (the last three use PyQt5). Kept until a decision is made. |
| `tests/` | Automated playback regression tests |
| `audio/` | Your music (optional; kept on your PC only, not uploaded to GitHub) |
| `assets/` | Artwork images + `album_covers/placeholder.png` |
| `album_covers/` | Generated cache (extracted art, playlist collages) — safe to delete; not uploaded |
| `Folder_Structure_Scanner_v4.py` | Utility: writes a folder listing to your Desktop |

## Known limitations (v4.9)

- No shuffle, repeat or visible "up next" queue yet.
- The three sample playlists (Favorites, Chill Hits, Workout Mix) are created once on first run with the same 4 songs; delete or edit them freely.
- The library is re-read from the files on every launch (fine for hundreds of songs; a cache will be needed for very large libraries).
- Album and artist pages don't exist yet.
- Online "Go to Radio" is not started.
