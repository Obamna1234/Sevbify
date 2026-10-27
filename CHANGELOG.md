# Changelog

## v5.0 (in progress) — Queue, shuffle & repeat

- **Queue panel** (right side, toggle with the ≡ button in the player bar): *Now playing*, *Next in queue* (songs you added),
  *Next from: <source>* (Your Songs, Your Library, a playlist, search results). Click any row to jump to it; right-click to remove; *Clear*.
- **Recently played** tab (last 50 songs, remembered between launches).
- **Add to queue** in every song's right-click menu.
- **Shuffle** (Ctrl+S) and **Repeat** off / all / one (Ctrl+R), remembered between launches. With repeat off, playback now
  stops at the end of the queue (like Spotify); Next still wraps around.
- Home grid now fits the window width (fewer columns when the side panel is open); long names are shortened with "…".
- Dark scrollbars everywhere.
- New modules: `core/play_queue.py` (queue logic, no UI), `ui/queue_panel.py`, `ui/icons.py` (drawn icons).
- **Settings** (⚙ in the sidebar): *Online features* on/off switch, optional Last.fm API key and Jamendo client ID,
  *Clear online cache*. Online status shown in the sidebar (Online / Offline / Online features off).
- Online layer (`core/online/`): network client with disk cache (works offline with last-known info, shows nothing
  online when switched off), Deezer / Last.fm / Wikipedia providers, song matching against your library.
- The GitHub build now runs a live check of the online services (`tools/online_check.py`), reported as notes.
- **Now playing view** (right side, toggle with the ▣ button; shown by default for new users): big artwork with a slow
  zoom-and-glow animation, song and artist, and **About the artist** (photo, Last.fm listeners, Deezer fans, bio, tags,
  links) when online. Says clearly when you're offline or online features are off.
- **Looping videos (canvas):** put a short video next to a song with the same name (e.g. `Song.mp4`), in a `canvas`
  folder next to your music, or `%APPDATA%\Sevbify\canvas\<Artist>.mp4` for all of an artist's songs. Plays silently
  behind the song; falls back to the animated artwork if it can't be played.
- Fix: very short songs could be mistaken for broken files and skipped.

## v4.9.3 — 27 Oct 2026 — Renamed to Sevbify; macOS & Linux builds

- The app is now called **Sevbify** (window title, `Sevbify.exe` / `Sevbify.app`, `Run Sevbify.bat`, GitHub repo `Obamna1234/Sevbify`).
- Saved data lives in `%APPDATA%\Sevbify\` (macOS: `~/Library/Application Support/Sevbify`, Linux: `~/.local/share/Sevbify`).
  Data from `Aurvo` or `Custom Spotify Replica` folders is copied across automatically on first launch; old folders are kept.
- GitHub Actions workflow (`build.yml`) can build, test and start-up-check Windows, macOS and Linux. Only Windows runs for now; macOS/Linux are switched off until the Windows app is finished (saves Actions minutes).

## v4.9.2 — 27 Oct 2026 — Renamed to Aurvo

- The app is now called **Aurvo** (window title, `Aurvo.exe`, `Run Aurvo.bat`, GitHub repo).
- Saved data moves to `%APPDATA%\Aurvo\`. Playlists/settings from `%APPDATA%\Custom Spotify Replica\` are copied across
  automatically on first launch (the old folder is kept as a backup).

## v4.9.1 — 27 Oct 2026 — GitHub workflow

- Private GitHub repo with automatic **Windows tests + .exe build** on every push (`.github/workflows/windows-build.yml`).
- `Run Aurvo.bat` (originally `Run Spotify Replica.bat`): one-click launcher (creates `.venv`, installs/updates packages only when needed).
- `Run Tests.bat`, `pytest.ini` (only `tests/` is collected, not the legacy `test_home.py`).
- Packaged-app support: bundled artwork inside the `.exe`, artwork cache in `%APPDATA%`, no crash when a windowed `.exe` has no console.
- Default music folder: `audio/` next to the app if present, otherwise your Windows *Music* folder.
- `app.py --smoke-test` for automated start-up checks.
- Music (`audio/`) and the generated `album_covers/` cache are no longer stored in git.

## v4.9 — 26 Oct 2026 — Local library & playlists

**New**
- **Saved playlists and settings**: playlists, volume/mute and music folders persist in
  `%APPDATA%\Custom Spotify Replica\library.json` (versioned JSON, atomic writes, damaged-file
  backup + recovery, project-relative paths, missing files kept and shown greyed out).
- **Your Library page**: sortable list of all songs; add/remove music folders (scanned recursively); rescan.
- **Search page**: live search across title, artist and album (all words must match, case-insensitive).
- **Playlist page**: big header with collage, song count and total time; Play, Rename, Delete;
  right-click to move up/down, remove, or add to another playlist.
- **Add to playlist** from any song (right-click on Home, Search, Library); duplicates skipped;
  playlists can now be created empty.
- **Volume slider and mute** in the player bar (saved).
- **Keyboard shortcuts**: Space, Ctrl+←/→, Ctrl+↑/↓, Ctrl+F, Ctrl+L.
- **Now-playing highlight** (green) in every song list; active page highlighted in the sidebar.

**Changed**
- Library scan runs in the background: the window opens in ~0.06 s instead of ~1.1 s.
- Clicking a playlist tile now opens it; the green ▶ on the tile plays it (Spotify behaviour).
- Sample playlists are created only on first run, then behave like any other playlist.
- Playlist names must be unique (case-insensitive).
- Song/Playlist/scanning code moved from `ui/main_window.py` into a new `core/` package (no UI
  code), as groundwork for a future mobile front end. `ui.main_window` still re-exports the old names.

**Fixed**
- F10: "Skipped …" error message was cleared the moment the next song started, so it was never seen (v4.8 bug).
- F11: Rounded buttons (including the existing Create Playlist) drew with square corners — Qt ignores a radius larger than half the button height.
- F12: Closing the window twice could crash in VLC; shutdown is now idempotent.
- F13: Any unexpected error inside a button/timer handler closed the whole app (PyQt6 default). Errors are now logged to `%APPDATA%\Custom Spotify Replica\error.log` and shown once; playback continues.
- Tests now use a temporary artwork cache, so running them never overwrites or deletes your real playlist covers.

**Tests:** 23 automated tests (`tests/test_playback.py`, `tests/test_library.py`), passing 3 runs in a row (Linux, headless).

## v4.8 — 26 Oct 2026 — Playback stabilisation

Baseline: `v4.7 spotify media player - Copy.zip` (compared against the older
`Spotify Media Player chatgpt.zip`, Dec 2025, which is a pygame-based predecessor
with no fixes v4.7 lacks).

Each issue below was reproduced on the unmodified v4.7 code first, then fixed and covered
by `tests/test_playback.py` (9 tests, passing on Linux/headless; Windows run pending).

| ID | Issue | Status | Fix |
|---|---|---|---|
| F1 | Songs never auto-advance at end of track (`Ended` check was nested inside a "playing or paused" check). **Reproduced.** | Fixed | `update_progress()` handles Ended/Error independently, advancing exactly once per track. |
| F2 | `play_song()` busy-waited with `time.sleep()` on the UI thread until VLC reported a duration, with no limit. Not reproduced as an indefinite hang, but unbounded. | Fixed | Removed. Duration shown from file metadata immediately; refined from VLC by the progress timer. 10 s open timeout. |
| F3 | Launching from another folder found 0 songs and created a stray `album_covers` folder there. **Reproduced.** | Fixed | All paths resolved from the project folder via `pathlib`. |
| F4 | Missing or corrupt files showed as "playing" (⏸) with no feedback. **Reproduced.** | Fixed | Red status message in player bar; unplayable track is skipped; stops (no infinite loop) if every track in the queue fails. |
| F5 | Untagged WAV files got duration 0, and WAV embedded artwork was never extracted (WAVE was imported but unused). **Reproduced.** | Fixed | `audio is not None` check; WAV handled with the ID3 branch. |
| F6 | Playing a playlist only played its first song, then continued through the whole library. | Fixed | Simple play queue: Home queues the library, a playlist queues itself. |
| F7 | Missing VLC crashed with a traceback. | Fixed | `app.py` shows a "VLC not found" dialog with install steps. |
| F8 | VLC kept running after closing the window. | Fixed | `closeEvent` stops and releases VLC. |
| F9 | Playlist collage silently ignored unreadable images (bare `except`). | Fixed | Images converted to RGB; errors logged instead of hidden. |
| — | Previous button | Changed | Restarts the current song if more than 3 s in (Spotify behaviour); otherwise goes back. |
| — | Create Playlist | Changed | Songs keep library order instead of click order; clearer validation message. |

Added: `README.md`, `requirements.txt`, `.gitignore`, `CHANGELOG.md`, `tests/`.

Not changed (awaiting decisions): legacy PyQt5 files, sample playlists, Search/Library placeholders.
