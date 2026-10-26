# Custom Spotify Replica — Local Music Player

A Spotify-inspired desktop music player for local files, built with Python, PyQt6 and VLC.
Windows is the first target platform.

**Current version:** v4.8 (stabilised v4.7 baseline). See `CHANGELOG.md`.

## Requirements

| What | Version | Notes |
|---|---|---|
| Windows | 10 or 11, 64-bit | |
| Python | 3.10 – 3.13, **64-bit** | https://www.python.org/downloads/ — tick "Add python.exe to PATH" |
| VLC media player | 3.0.x, **64-bit** | https://www.videolan.org/vlc/ — must match Python's 64-bit; the app uses VLC's engine (libVLC) for playback |
| Python packages | see `requirements.txt` | PyQt6, python-vlc, mutagen, Pillow, pytest |

## First-time setup (Windows, PowerShell)

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

## Adding music

Put `.mp3`, `.wav`, `.flac`, `.ogg` or `.m4a` files in the `audio` folder and restart the app.
Artwork comes from (in order): an image in `assets` with the same name as the audio file,
art embedded in the file's tags, or a placeholder.

## Running the automated tests

```powershell
python -m pytest tests -v
```

The tests generate short WAV tones and play them through VLC's silent dummy output in a
hidden window, so they make no sound and don't touch your music. They need VLC installed.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Entry point. Shows a clear message if VLC is missing. |
| `ui/main_window.py` | Main window, library scan, metadata/artwork, playlists, playback |
| `ui/sidebar.py` | Navigation sidebar |
| `ui/Playlist_View.py`, `ui/Home_View.py`, `ui/player_bar.py`, `test_home.py` | **Legacy / unused** by the running app (the last three use PyQt5). Kept until a decision is made. |
| `tests/` | Automated playback regression tests |
| `audio/` | Your music |
| `assets/` | Artwork images + `album_covers/placeholder.png` |
| `album_covers/` | Generated cache (extracted art, playlist collages) — safe to delete |
| `Folder_Structure_Scanner_v4.py` | Utility: writes a folder listing to your Desktop |

## Known limitations (v4.8)

- Search and Your Library pages are still "Coming Soon".
- Playlists are not saved between launches; the three sample playlists are demo content.
- No volume, shuffle or repeat controls yet.
- The library is scanned on startup on the UI thread (fine for small libraries; will move to a background scan when folder import is added).
