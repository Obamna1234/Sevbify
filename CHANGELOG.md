# Changelog

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
