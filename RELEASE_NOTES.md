## Install (Windows)

Everything is included (player engine, downloader, ffmpeg); nothing else to install.

1. Under **Assets** below, download **Sevbify-Windows.zip**.
2. Right-click the zip → **Extract All…** → **Extract**.
3. Open the extracted `Sevbify` folder and double-click **Sevbify.exe**.
   If Windows says "Windows protected your PC", click **More info** → **Run anyway** (the app isn't signed yet).
4. Optional: in Sevbify, **Settings** (⚙ top right) → **Add to Desktop and Start menu**.

Your playlists and settings are kept between versions (`%APPDATA%\Sevbify`). To update, download the new zip,
extract it, and use the new `Sevbify.exe`; you can delete the old folder.

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
- **New in beta.5:** fixes from the first Windows test (crash when making a playlist, downloads folder inside itself,
  flashing console window, white selected rows). Downloads are filed per artist with phone-ready playlist files.
  Grey selection, ▶ on hover, click-to-seek, drag and drop, Show in folder, a proper Song radio page, Spotify's song
  menu, the ••• menu with Spotify's shortcuts, and a sleep timer.

**Pre-release / beta:** built and tested automatically on GitHub's Windows machine, but downloading a real song from
inside Sevbify hasn't been confirmed on a home PC yet. Please report anything that goes wrong.

Sevbify plays music with VLC's engine (libVLC by VideoLAN, LGPL/GPL, source at https://www.videolan.org), included
in the app. Only download music you have the right to download. Sevbify is not affiliated with YouTube, Bandcamp, Apple,
Spotify, Deezer or Sevby LLC (sevby.com). Built with AI help.
