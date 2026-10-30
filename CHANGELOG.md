# Changelog

## v5.0 (in progress) — Spotify-style redesign, queue, radio, online search, downloads

**Deezer / Jamendo imports and simpler border colours (v5.0.0-beta.14):**
- Import a public Deezer playlist or album link (Deezer's free public API, no account; all songs, not just 100),
  or a Jamendo playlist or album link (needs the free Jamendo client ID; on Android a box for it appears when you
  paste a Jamendo link).
- Border colours: grey = made in Sevbify (your own songs or ones found online), blue = imported from a file,
  green = Spotify link, white = Apple Music link, purple = Deezer link, orange = Jamendo link.

**Playlist pictures, origin border, totals and smarter radio (v5.0.0-beta.13):**
- Playlists without a picture you chose get Spotify's: the covers of the first 4 *different* albums, in the
  playlist's order, as a 2x2 grid; with fewer than 4 different albums, the first song's cover. Songs you haven't
  downloaded count too (their cover is fetched), on Windows and Android. Rule shared in `core/playlist_cover.py`.
- Settings → "Show where playlists came from" (off by default): a coloured border around playlist pictures
  showing where each came from (colours changed in beta.14). Playlists made before this version count as made in
  Sevbify.
- Playlist length like Spotify: Windows "50 songs, about 2 hr 45 min"; Android "2h 45min".
- Song radio reacts to skips like Spotify: skipping a radio song in its first 30 seconds removes that artist's
  other upcoming songs from this radio (a few songs are always kept). In memory only: nothing is saved or sent.

**Lyrics, sharing, Connect and choosing downloads (v5.0.0-beta.12):**
- Lyrics, like Spotify: Android shows a "Lyrics preview" card under Now playing (scroll down) and full-screen
  lyrics; Windows has a Lyrics (microphone) button next to the queue. Time-synced lyrics highlight the line being
  sung and you can tap/click a line to jump there. From a .lrc/.txt file next to your song (offline), otherwise
  from LRCLIB (free, no account; only the song's name and length are sent). Settings → Lyrics switches it off.
- Share a song as a Spotify or YouTube link (Sevbify has no accounts): Android has a Spotify-style share sheet
  (song card, Spotify, YouTube, copy links, then your phone's share menu); Windows has ••• → Share → Copy
  Spotify / YouTube / song.link link. Exact links when they can be found, otherwise a search for the song.
- Connect, like Spotify: Android shows where the sound is going (this phone or your Bluetooth headphones, also
  on the mini player), Android's output picker and Bluetooth settings; Windows has a Connect button that lists
  your speakers/headphones (Bluetooth included) and switches Sevbify's output, plus Bluetooth & sound settings.
- A playlist's Download button asks first: Download all, or choose songs (ticked list, select all / none).
  Android: hold a song to start choosing several, then Download, Queue or Add to playlist.

**Go to album and episode order (v5.0.0-beta.11):**
- Go to album opens the whole album in its own order, like Spotify (songs you've downloaded play from your
  files, the rest stream); offline it shows the album's songs you have. Before, a song you didn't own went to a
  search (Windows) or the artist page (Android).
- Podcast episodes and audiobook chapters always play in order, back to back, even when Shuffle is on for music
  (like Spotify). Pick "Oldest first" on a show and press play on episode 1 to binge it from the start.

**Video podcasts, download quality and YouTube upkeep (v5.0.0-beta.10):**
- Video podcasts play inside Sevbify. Android: Now playing has an Audio / Video switch (cover art or the video,
  like Spotify), and leaving Now playing keeps the video in a small floating player you can move, resize and tap
  to open again (going to the home screen continues it picture-in-picture). Windows: "Mini player" on the video
  page opens a resizable window that stays on top while you use Sevbify.
- "Watch video" on a podcast's page finds the show's own YouTube channel (only a channel with the show's or
  host's name is accepted) and opens its episodes as videos.
- Podcast search puts the show you typed first (Apple's results came in their own order).
- Settings → Download quality: Best (the original audio, no conversion: the smallest full-quality file, .m4a),
  MP3 (Windows; now 160 kbps instead of a much bigger VBR file), or Data saver (about half the size).
  Audiobook quality: 64 or 128 kbps. Video podcast quality: Auto, 360p to 1080p.
- yt-dlp (what finds songs on YouTube) updates itself once a week when it's old, only from the official release
  and only if it matches its published checksum (Windows and, new, Android). The Windows app bundles Deno,
  which YouTube now needs for its audio, and yt-dlp-ejs.
- Failed or stopped downloads no longer leave half-finished files (.part, thumbnails) in your music folder.
- Android: opening an audiobook failed (fixed); the "S" bubble is now the Sevbify logo (it opens Settings;
  Sevbify has no accounts). Windows: the Desktop shortcut goes on the real Desktop when OneDrive moved it.
- CI: the build's GitHub token is read-only except for the Release step.

**Security and stability check (v5.0.0-beta.9), both apps:**
- Links from podcast feeds and imports can only be web addresses: a feed can no longer make "Open web page"
  launch a program or file on the PC, or make Sevbify read or copy local files. Feeds that try an XML
  "billion laughs" trick are refused, and oversized web answers are cut off.
- Android: Python starts in the background (no freeze on first start); the app no longer closes if the online
  core can't start; the download notification can't crash the app when downloads end straight away; switching
  offline stops downloads instead of waiting; nothing-can-play lists no longer skip round and round; safe file
  names for downloads (and correct extensions for podcast episodes); old http:// podcast episodes play (https
  is tried first); the library is saved off the main thread and a damaged library file is kept, not lost;
  your library is excluded from Google's cloud backup; failed downloads say why; Home → Audiobooks shows
  popular free audiobooks.
- Windows: PyQt6 pinned to the tested 6.11 (6.12 changed how Your Library reacts).

**Android app (v5.0.0-beta.8, first test version):**
- New Sevbify-Android.apk next to the Windows zip in every release (Android 13+). It lives in the same
  repository (`android/`) and runs the same `core/` code as Windows, so fixes to searching, matching,
  downloading, importing, podcasts and audiobooks reach both apps.
- Spotify-phone-style screens: Home, Search with Browse all, Your Library (filters, sort, list/grid), Create
  (playlist / folder), playlist and album pages, artist pages, the now-playing screen with queue, mini player,
  lock-screen and notification controls, podcasts and audiobooks, Settings and Import.
- Downloads keep the original audio (no conversion needed) and go to Music/Sevbify on the phone.

**Fixes from the beta.6 test, and more of Spotify (v5.0.0-beta.7):**
- Fixed the small "Sevbify" window that flashed up and took over the mouse, mostly while downloading: Home
  cards were shown before being put in the window (30+ flashes during a download run). Pages now never
  rebuild under a held mouse button or an open menu, and old pages are never turned into windows.
- Fixed the empty "Something went wrong" box (white text on white) and the Podcasts / Audiobooks Home chips.
- The Online button really switches Sevbify offline and back; Home and search no longer move sideways.
- Menus switch instantly (no submenu delay or fade).
- Crossfade overlaps the two songs with equal-power curves (no jump in volume); smooth volume slider.
- Dropping files from File Explorer works again (song lists had switched drops off).
- Downloads: Pause after this song, Resume, Stop all keeps songs as Stopped, Cancel / Try again per song; they
  wait out a lost internet connection or missing drive instead of failing.
- Downloaded podcasts and audiobooks are listed under Downloaded and play offline; no hidden
  `.sevbify-noscan` files any more (beta.6's are removed).
- Episodes sort by release date (newest / oldest); descriptions are cut at whole lines; faster artwork; a
  YouTube channel shows whether YouTube verified it.
- Import: covers looked up a few songs at a time; Spotify playlists over 100 songs come in complete by pasting
  the songs copied in Spotify.
- Song lists: Shift+click / Ctrl+click selection, whole-row hover and selection, Delete key, drag several songs;
  playlists show the artist under the title; Spotify time format (3:07).
- Playlist page like Spotify's: Preview, shuffle, download, •••, search in playlist, sort, + Add,
  Name & details. Spotify-style playlist menu (Move to folder with Find a folder, Add to other playlist,
  Share and export: .m3u8 export and copy the actual songs to a folder or phone).
- Spotify's white "Delete from Your Library?" card and dark "Edit details" box.
- Search like Spotify's: chips, Top result, Songs, artists, podcasts, audiobooks; clear and Browse buttons.
- Browse genres open a genre page (popular songs, playlists, new releases, albums, artists) from Deezer's daily
  charts; playlists and albums can be saved to Your Library.
- Miniplayer, Full screen (F11), zoom with Ctrl + / Ctrl − / Ctrl 0, Spotify's equaliser curve and zoom
  pictures, Reset appearance / Reset all settings.
- Song menu: Hide Canvas / Show Canvas, and Canvas video → choose your own loop.
- Private session badge; it ends when Sevbify closes or after 6 hours.
- Your Library chips are pills with ‹ › buttons.

**Spotify's library, settings, import, Browse, podcasts and audiobooks (v5.0.0-beta.6):**
- **Your Library** like Spotify: chips Playlists / Podcasts / Audiobooks / Albums / Artists / Downloaded / To download,
  filter, sort (Recents / Recently added / Alphabetical), Compact / List / Grid, folders (Create → Folder, Move to
  folder), collapse to covers and expand to the whole window; album and artist pages from your files.
- **Create → Playlist** makes "My Playlist #N" straight away (drag songs in); change a playlist's cover.
- **Settings page** in the middle like Spotify: online & privacy, music folders with on/off switches, download location
  and source, phone playlist files, playback (equaliser with presets, normalise volume, fade between songs, autoplay
  similar songs when a queue ends), now-playing view on play, song notifications, Canvas on/off, zoom, start with
  Windows, close to the tray, storage (download and cache sizes), proxy, hardware acceleration, private session
  (also in File menu), allow explicit songs.
- **Import a playlist** (Create → Import, or Settings): a public Spotify or Apple Music link (read from the public page,
  never signed in), or a CSV (Exportify), TXT (any encoding, including Chinese/Japanese/Korean files saved as
  "ANSI", and "Artist-Title" with any dash) or M3U file. Same order and cover; your own files are used when found.
- **Browse all** (empty search box, or the ▦ button): Podcasts, Audiobooks and music genres with what's popular now.
- **Home chips**: All / Music / Podcasts / Audiobooks, with Continue listening.
- **Podcasts**: search Apple's directory, Top podcasts, follow shows (in Your Library), episodes from each show's RSS
  feed, stream or download, continue where you left off, mark as played. **Video podcasts**: follow a YouTube channel
  by its link; Watch the video inside Sevbify or play the audio only.
- **Audiobooks**: free public-domain LibriVox books (Internet Archive): search, popular, newly added, chapters in
  order, download whole books, carry on at the first unfinished chapter.
- Podcast and audiobook downloads go to `Sevbify downloads\Podcasts` and `\Audiobooks` and never show up as songs.
- **About and updates** (Settings): check for a new Sevbify, update yt-dlp in one click; once-a-day check (can be off).

**Fixes and polish from the first Windows test (v5.0.0-beta.5):**
- Fixed: "wrapped C/C++ object of type LibraryRow has been deleted" when a click rebuilt a list (e.g. making a playlist
  from a song's menu). Lists now replace their rows only after the click has finished.
- Fixed: downloads went into "Sevbify downloads\Sevbify downloads". The red "Folder not found" note now shows once,
  with how to remove an old folder. Settings → Download location lets you choose the folder.
- Fixed: a black console window flashed while downloading (ffmpeg / yt-dlp now start without a window).
- Downloads are filed by main artist: `Sevbify downloads\Artist\Artist - Title.mp3` ("A feat. B" goes under A;
  bands like Simon & Garfunkel or AC/DC stay whole). Playlists are also saved as `.m3u8` files in
  `Sevbify downloads\Playlists` (same order, relative paths) so they work on a phone; a song is stored once.
- Privacy: YouTube downloads no longer use the Chrome sign-in unless allowed in Settings; Settings lists exactly
  which services are contacted.
- Song lists: grey selection like Spotify (no more white rows on Windows), dark panels everywhere, ▶ on hover next to
  the number (click to play), click empty space or press Esc to deselect.
- Click anywhere on the progress or volume bar to jump there.
- Drag and drop: reorder songs in a playlist, drop music files or folders from File Explorer into a playlist (also an
  empty one), drag songs onto a playlist on the left.
- **Show in folder** for songs on your computer.
- **Song radio** now has its own page (cover, "Song radio", "With … and more", Play, Save as playlist, Download). Songs are
  ordered by how close they are, artists are spread out, and songs you already have by those artists are mixed in.
- Song menu in Spotify's order: Add to playlist ▸ (with *Find a playlist*), Add to queue, Download / Show in folder,
  Sleep timer ▸, Play, Go to song radio, Go to artist, Go to album, Open in ▸.
- **••• menu** (top left): File / Edit / View / Playback / Help with Spotify's shortcuts (Ctrl+L search, Ctrl+F filter,
  Shift+←/→ seek, Ctrl+N, Ctrl+P, F1 About, Troubleshooting).
- **Sleep timer:** 5 min to 1 hour, or end of the song.
- Crisp drawn download icons instead of the emoji arrow.

**Full songs, To download, fresh start (v5.0.0-beta.4):**
- Songs you don't have yet now **stream in full** while online (Bandcamp first, then YouTube, matched by the song's
  real length with SEVBY's engine), instead of 30-second previews. They stay ⬇ "not downloaded" until downloaded;
  the player shows *Full song · YouTube · not downloaded*. Falls back to the preview if no full song is found.
  Settings → *Play full songs you don't have yet* switches it off. The one-time notice now covers streaming too.
- **Saved for later** is now called **To download** in the left panel and on its page.
- New users start with **no playlists** (the sample playlists are gone).
- Removed old unused files (`ui/sidebar.py`, `ui/Home_View.py`, `ui/Playlist_View.py`, `ui/player_bar.py`,
  `test_home.py`, `Folder_Structure_Scanner_v4.py`).
- New `core/streamer.py` with 9 tests (fake searches, no internet).

**Logo, icons and a smaller app (v5.0.0-beta.3):**
- New Sevbify logo (SEVBY family look: white play button with SEVBY's green download arrow and sound wave) as the
  icon of Sevbify.exe, its window, taskbar and shortcuts. macOS (.icns) and Linux (.png + .desktop) icons are ready
  for when those builds are switched on; `tools/make_logo.py` draws them all.
- **Settings → Add to Desktop and Start menu** (Windows app) makes shortcuts with the logo.
- VLC trimmed to what Sevbify uses (audio only): its own window, video, subtitles, visualisations, casting/streaming
  out, device discovery and remote control are left out (`tools/trim_vlc.py`). All audio formats, web streams,
  the equaliser and speed filters stay. VLC never opens a video window now.
- The start-up check on GitHub now plays WAV, MP3, FLAC, OGG, Opus, M4A and a web stream with the trimmed VLC, plays a
  looping canvas video with Qt's video player, and checks the icon, all inside the packaged app.

**All-in-one Windows app:** VLC's playback engine (libVLC + plugins) is now inside the ready-made app, so nothing
needs installing. The build hides the machine's own VLC before starting the packaged app, and `--smoke-test` plays a
WAV and an MP3 tone with the built-in engine. New releases are published automatically from the `VERSION` file
(first: v5.0.0-beta.1; this change: v5.0.0-beta.2).

**Downloading songs (SEVBY's engine, in the background):**
- Songs you don't have yet are greyed out with **⬇** in web search results, playlists and Saved for later, online
  or offline. Playlist headers say how many still need downloading to play offline.
- **Download** / **Retry download** in their right-click menu, **⬇ Download** on a playlist, **⬇ Download all** on
  the Saved for later (*To download*) page, which now also lists every ⬇ slot in your playlists.
- Downloads run one at a time in the background while music keeps playing: Bandcamp first, then YouTube, saved as
  tagged MP3s with cover art in `Sevbify downloads` inside your first music folder. Each song fills its exact place
  in every playlist it was added to. Rows show *Queued to download*, *Downloading…* or *Download failed*.
- **⬇ pill** in the top bar shows progress; click to stop or to retry failures. Closing the app stops cleanly.
- **Radio → Save as playlist** (queue panel). Songs you don't have stay as ⬇ slots in their place.
- Search: songs you already have are listed on top and not repeated under *More from the web*.
- Settings → **Downloads**: Bandcamp + YouTube / Bandcamp only / YouTube only (remembered).
- One-time notice before the first download: only download what you have the right to; not affiliated with
  YouTube, Bandcamp, Apple, Spotify, Deezer or Sevby LLC.
- New: `core/sevby_engine.py` (generated from SEVBY by `tools/make_engine.py`), `core/downloader.py`,
  `ui/download_manager.py`, `tools/download_check.py`, 21 tests in `tests/test_download.py` (fake downloader, no
  internet). The Windows build now bundles yt-dlp and ffmpeg, and `--smoke-test` checks both are inside the app.
- ffmpeg comes from the `imageio-ffmpeg` package, so downloads also work from `Run Sevbify.bat` without installing ffmpeg.
- Not yet tried: a real download from inside Sevbify on a home PC. On GitHub's cloud machine, Bandcamp search and
  YouTube matching work, but YouTube blocks the download itself there ("confirm you're not a bot"), as it often does for servers.

**New look (Spotify desktop layout, our own code):**
- Black window with three rounded panels: **Your Library** (left), the page (middle), Now playing / Queue (right).
- **Top bar:** back/forward history, round Home button, centred *What do you want to play?* search pill, online status, Settings.
- **Your Library panel:** Your Songs, Saved for later and all playlists with covers; filter chips, filter box, **+ Create**;
  click to open, double-click to play, right-click for Play / Rename / Delete; the playing list is green.
- **Home:** greeting, quick-play tiles, *Recently played*, *Your playlists* and *Your songs* card shelves (green play on hover).
- **Playlist / Your Songs / Saved for later pages:** big header with a colour gradient (taken from the cover), round green
  play button, clock column.
- **Player bar:** song on the left; shuffle / previous / round white play / next / repeat with the progress bar centred;
  now playing, queue and volume on the right. White sliders that turn green on hover.
- Bundled **Figtree** font (SIL Open Font License) — the closest free match to Spotify's typeface — and drawn icons.


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
- **Go to song radio** (right-click any song): 30–50 similar songs from Deezer (and Last.fm if you add a key),
  shown as *Next from: <song> Radio*. Songs you already own play in full from your files; others play as clearly
  labelled 30-second previews. Covers download in the background.
- **Search the web**: the Search page now shows *In your library* and *More from the web* (Deezer's catalogue). Songs
  you own are recognised and play in full; others are previews. Waits until you stop typing; explains when offline or
  switched off.
- **Open in ▸** Spotify / YouTube Music / YouTube / Apple Music / Bandcamp / Deezer in every song's menu.
- Cover art thumbnails in every song list.
- **Not-downloaded playlist slots:** add any Radio/Search song to a playlist; it keeps its exact position, shows ⬇ and
  "N not downloaded yet", plays as a preview when online, and is **filled automatically** with your own file (same
  position) as soon as a matching file appears in your music folders. Files still being written are waited for.
- **Music folders are watched:** new files show up by themselves (no Rescan needed).
- **⬇ Saved for later** page: right-click an online song → *Save for later*; lists are **sorted by genre** so different
  styles never mix. Per genre: Play, Add all to playlist…, Export… (.txt "Artist - Title" or .m3u). Songs leave the
  list once they're in your library.
- Fix (Windows): background online requests could outlive the app at exit and crash it; the app now waits for them.

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
