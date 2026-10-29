## Install (Windows)

Everything is included (player engine, downloader, ffmpeg); nothing else to install.

1. Under **Assets** below, download **Sevbify-Windows.zip**.
2. Right-click the zip → **Extract All…** → **Extract**.
3. Open the extracted `Sevbify` folder and double-click **Sevbify.exe**.
   If Windows says "Windows protected your PC", click **More info** → **Run anyway** (the app isn't signed yet).
4. Optional: in Sevbify, **Settings** (⚙ top right) → **Add to Desktop and Start menu**.

Your playlists and settings are kept between versions (`%APPDATA%\Sevbify`). To update, download the new zip,
extract it, and use the new `Sevbify.exe`; you can delete the old folder.

## Install (Android, new and experimental) — Android 13 or newer

1. On your phone, sign in to GitHub in the browser (the project is private, so downloads need you signed in).
2. Open this release and, under **Assets**, tap **Sevbify-Android.apk**.
3. Open the downloaded file. If Android asks, allow your browser to **install unknown apps**, then tap **Install**.
   Play Protect may warn that the app is unknown — tap **Install anyway** (it's your own app, not from the Play Store).
4. Open Sevbify, allow **Music and audio** (so it can see your songs) and **Notifications** (for the player
   and download progress).

Updating: install the new APK over the old one; your playlists stay. The Android app uses the same core as
the Windows app (search, radio, full-song finding, downloads, importing, podcasts, audiobooks), with a layout
based on Spotify's phone app: Home, Search, Your Library and Create along the bottom, a mini player above them,
and the full now-playing screen. It only reads music from the folders you choose in Settings.
Downloaded songs are saved to `Music/Sevbify/<Artist>` on the phone.

## What's in this version

See `CHANGELOG.md` inside the zip for the full list. Highlights:

- Spotify-style look: Your Library panel, Home shelves, queue and now-playing panels.
- Search, Go to song radio and artist info when online; your own music always works offline.
- **Songs you don't have yet stream in full** while online (found on Bandcamp, then YouTube) and stay marked ⬇
  until downloaded. They're listed under **To download** on the left.
- **Downloading** (SEVBY's engine, in the background): right-click a greyed ⬇ song → **Download**,
  **⬇ Download** on a playlist, or **⬇ Download all** on To download. Each song fills its own place in the playlist.
  Radio → **Save as playlist** in the queue panel.
- New users start with no playlists.
- **New in beta.7:** fixes from the beta.6 test (the flashing mini-window during downloads, the Podcasts
  error, the Online button, drag and drop from File Explorer, crossfade, volume), download Pause / Resume /
  Cancel / Try again, downloaded podcasts under Downloaded, Shift+click selection, Spotify-style playlist page,
  Preview, search and genre pages, Miniplayer, Full screen, zoom keys and Reset settings, playlist export and
  copy-to-phone, and full Spotify playlists over 100 songs.
- **New in beta.6:** Your Library like Spotify (podcasts, audiobooks, albums, artists, folders, sorting, grid,
  collapse/expand), a full Settings page (equaliser, normalise, fade, autoplay, zoom, start with Windows, tray,
  proxy, private session…), **Import a playlist** from a Spotify / Apple Music link or a file, **Browse**,
  **Podcasts** (including YouTube video podcasts), free **audiobooks**, and update checks for Sevbify and yt-dlp.
- **New in beta.5:** fixes from the first Windows test (crash when making a playlist, downloads folder inside itself,
  flashing console window, white selected rows). Downloads are filed per artist with phone-ready playlist files.
  Grey selection, ▶ on hover, click-to-seek, drag and drop, Show in folder, a proper Song radio page, Spotify's song
  menu, the ••• menu with Spotify's shortcuts, and a sleep timer.

**Pre-release / beta:** built and tested automatically on GitHub's Windows machine, but downloading a real song from
inside Sevbify hasn't been confirmed on a home PC yet. Please report anything that goes wrong.

Sevbify plays music with VLC's engine (libVLC by VideoLAN, LGPL/GPL, source at https://www.videolan.org), included
in the app. Only download music you have the right to download. Sevbify is not affiliated with YouTube, Bandcamp, Apple,
Spotify, Deezer or Sevby LLC (sevby.com). Built with AI help.
