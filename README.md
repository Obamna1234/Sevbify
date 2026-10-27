# Sevbify — Local Music Player

Sevbify is an ad-free desktop music player for your own music files, with a familiar dark,
streaming-app-style interface. Built with Python, PyQt6 and VLC.
Windows is the first target platform. It can also download songs you don't have yet, using the
download engine from its sister app SEVBY (see *Downloading songs* below).

Sevbify is built with AI help (Anthropic's Claude writes and tests most of the code; the owner
decides what it does and tests it on Windows).

**Current version:** v4.9.3 — library, search, saved playlists, volume. See `CHANGELOG.md`.

## Requirements

| What | Version | Notes |
|---|---|---|
| Operating system | Windows 10/11 (64-bit), macOS, or Linux | Windows first; macOS and Linux builds are set up and will be switched on later |
| Python | 3.10 – 3.13, **64-bit** | https://www.python.org/downloads/ — tick "Add python.exe to PATH" |
| VLC media player | 3.0.x, **64-bit** | https://www.videolan.org/vlc/ — must match Python's 64-bit; the app uses VLC's engine (libVLC) for playback |
| Python packages | see `requirements.txt` | PyQt6, python-vlc, mutagen, Pillow, certifi, yt-dlp, pytest |
| ffmpeg | nothing to install | Needed for downloading songs. Comes with the `imageio-ffmpeg` package (copied once into `%APPDATA%\Sevbify\ffmpeg` when running from source); the ready-made app has it built in. |

## Quick start (recommended)

**One-time setup**
1. Install **64-bit Python 3.12** (https://www.python.org/downloads/, tick *Add python.exe to PATH*)
   and **64-bit VLC** (https://www.videolan.org/vlc/).
2. In GitHub Desktop: **File → Clone repository → Sevbify**.
3. Optional: copy your music into the clone's `audio` folder (it stays on your PC and is never
   uploaded), or skip this and use **Your Library → Add folder…** in the app.
   With no `audio` folder, the app uses your Windows *Music* folder.

**Every time there's an update**
1. GitHub Desktop → **Fetch origin** → **Pull origin**.
2. Double-click **`Run Sevbify.bat`**.

The first run sets up a private Python environment (about a minute). After that it starts
straight away, and re-installs packages automatically only when an update needs it.
`Run Tests.bat` runs the automated tests.

**Ready-made app (no Python needed):** every push is built and tested on a real Windows machine by GitHub Actions
(macOS and Linux builds are set up but switched off until later). Open the repo's **Actions** tab → latest *Build & test* run →
download **Sevbify-Windows**, **Sevbify-macOS** or **Sevbify-Linux** → unzip → run it (VLC must be installed).
- **macOS:** the app isn't signed by Apple yet, so the first time, right-click `Sevbify.app` → **Open** → **Open**.
- **Linux:** extract with `tar xzf Sevbify-Linux.tar.gz`, then run `Sevbify/Sevbify`. Install VLC with your package manager (e.g. `sudo apt install vlc`).

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

You can also launch it from any folder, e.g. `python "C:\path\to\Sevbify\app.py"` —
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
| **Songs you don't have yet** | Greyed out with **⬇** everywhere (web search results, playlists, Saved for later). Right-click → **Download**. |
| **Radio** | In the queue panel, **Save as playlist** keeps a Radio as a playlist; songs you don't have stay in their place as ⬇ slots. |
| **Saved for later** (*To download*) | Every song waiting to be downloaded: all ⬇ slots in your playlists plus songs you saved, with **⬇ Download all**. |
| **⬇ pill in the top bar** | Shows download progress ("⬇ 2 of 5 · Song"). Click it to stop, or to retry songs that failed. |

**Keyboard:** Space = play/pause · Ctrl+→ / Ctrl+← = next / previous · Ctrl+↑ / Ctrl+↓ = volume · Ctrl+F = search · Ctrl+L = library

## Adding music

Either put `.mp3`, `.wav`, `.flac`, `.ogg` or `.m4a` files in the bundled `audio` folder and
press **Rescan**, or use **Your Library → Add folder…** to add any folder on your PC.
Artwork comes from (in order): an image in `assets` with the same name as the audio file,
art embedded in the file's tags, or a placeholder.

## Downloading songs

Songs you find with **Search** or **Radio** can be added to playlists before you have them. They sit in
their place greyed out with ⬇, and the playlist header says how many still need downloading to play
offline. While online they play as 30-second previews.

Right-click such a song → **Download**, use **⬇ Download** on a playlist, or **⬇ Download all** on the
*Saved for later* page. Sevbify then, in the background while your music keeps playing:

1. looks for the song on **Bandcamp** first, then **YouTube** (Settings → Downloads lets you pick
   *Bandcamp + YouTube*, *Bandcamp only* or *YouTube only*);
2. saves it as a tagged **MP3** with cover art in a **`Sevbify downloads`** folder inside your first
   music folder;
3. puts it in the exact place (#) of every playlist it was added to, even if more songs were added after it.

If a download fails, the row says *Download failed*; right-click → **Retry download**, or click the red
⬇ pill at the top. Closing Sevbify stops the current download; finished songs are kept.

The download engine (`core/sevby_engine.py`) is copied from the SEVBY app
(https://github.com/Obamna1234/sevby, MIT) with its window code removed; Sevbify doesn't need SEVBY
installed. To update it after SEVBY changes, run
`python tools/make_engine.py <path to sevby_app.py> core/sevby_engine.py`. Don't edit it by hand.

**Only download music you have the right to download**, for example songs you've bought or that the
artist offers for free. Downloading from YouTube goes against YouTube's terms of service; Sevbify shows
this notice once before the first download, and you decide. Sevbify never downloads from file-sharing
networks, torrents or "ripping groups": those mostly share music without the artists' permission.
Sevbify is not affiliated with YouTube, Bandcamp, Apple, Spotify, Deezer, or **Sevby LLC (sevby.com)**.

**What is tested:** the download queue, stopping, failures, retry, the one-time notice, slots filling
in their exact place, and Radio → playlist → Download all are covered by automated tests that use a
*fake* downloader (no internet). The real Bandcamp/YouTube download is checked on GitHub's Windows
machine on every push (reports only: cloud servers are often blocked by YouTube), but it **has not yet
been tried from inside Sevbify on a home PC**. The same engine works in SEVBY on Windows.

## Where your playlists and settings are saved

`%APPDATA%\Sevbify\library.json` (paste that into File Explorer's address bar). Playlists saved
under the app's earlier names (`%APPDATA%\Aurvo` or `%APPDATA%\Custom Spotify Replica`) are copied across automatically on first launch.
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
| `Run Sevbify.bat` | One-click launcher (sets up Python packages automatically) |
| `Run Tests.bat` | Runs the automated tests |
| `.github/workflows/build.yml` | Automatic tests + app builds for Windows, macOS and Linux on every push |
| `app.py` | Entry point. Shows a clear message if VLC is missing. `--smoke-test` starts, loads the library and exits (used by the automatic build). |
| `core/` | Data and logic with no UI code: `paths.py`, `models.py` (Song, Playlist), `library.py` (folder scanning), `storage.py` (save file), `downloader.py` (runs songs through the download engine) |
| `core/sevby_engine.py` | SEVBY's download engine, **generated** by `tools/make_engine.py`; never edit by hand |
| `ui/download_manager.py` | Background download queue (one song at a time, in its own thread) |
| `tools/download_check.py` | Live download check run on GitHub (one Creative Commons song) |
| `ui/main_window.py` | Main window: pages, player bar, playback, playlist actions |
| `ui/track_table.py` | Song list used by Search, Your Library and playlist pages |
| `ui/theme.py`, `ui/top_bar.py`, `ui/library_panel.py`, `ui/cards.py` | Spotify-style look: colours/fonts, top bar, Your Library panel, Home cards |
| `ui/sidebar.py` | Old navigation sidebar (replaced by the Your Library panel in v5.0; kept for reference) |
| `ui/Playlist_View.py`, `ui/Home_View.py`, `ui/player_bar.py`, `test_home.py` | **Legacy / unused** by the running app (the last three use PyQt5). Kept until a decision is made. |
| `tests/` | Automated playback regression tests |
| `audio/` | Your music (optional; kept on your PC only, not uploaded to GitHub) |
| `assets/` | Artwork images + `album_covers/placeholder.png` |
| `album_covers/` | Generated cache (extracted art, playlist collages) — safe to delete; not uploaded |
| `Folder_Structure_Scanner_v4.py` | Utility: writes a folder listing to your Desktop |

## Credits and licences

- Sevbify's own code: MIT.
- Download engine: from SEVBY (MIT). Uses **yt-dlp** (Unlicense) and **ffmpeg** (the ready-made app
  bundles an ffmpeg build from the `imageio-ffmpeg` package, which is GPL-licensed; see https://ffmpeg.org).
- Playback: VLC / libVLC (LGPL) via python-vlc. Font: Figtree (SIL Open Font License).

## Known limitations (v4.9)

- No shuffle, repeat or visible "up next" queue yet.
- The three sample playlists (Favorites, Chill Hits, Workout Mix) are created once on first run with the same 4 songs; delete or edit them freely.
- The library is re-read from the files on every launch (fine for hundreds of songs; a cache will be needed for very large libraries).
- Album and artist pages don't exist yet.
- Online "Go to Radio" is not started.
