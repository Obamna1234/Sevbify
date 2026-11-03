## What's new in beta.38 (Android)

- **A proper video player for video podcasts.** Tap the video for controls: play/pause, back/forward 10 seconds, a seek bar with the time, captions, speed and full screen. They fade away after 3 seconds. Double-tap the left or right side to skip 10 seconds (double-tap the middle to switch fill/fit).
- **Pinch to fill.** Pinch out to fill the screen (the edges are cropped, like YouTube), pinch in to fit it again.
- **Full screen.** The full-screen button turns the phone to landscape with no bars and the screen kept on; back (or the arrow) returns.
- **Captions.** When YouTube has captions for an episode, the CC button turns them on and lets you pick a language (your phone's language first, then English). They're remembered. Not every video has captions, and YouTube doesn't always hand them out, so the button only appears when there are some.
- **Playback speed.** 0.75×, 1×, 1.25×, 1.5× and 2× from the video's top bar.
- **Cast.** The cast button opens your phone's own Cast / screen-mirroring screen so you can show the video on a TV (use full screen). Sevbify doesn't send the video to the TV itself, because YouTube's links only work on the phone.
- **A cleaner mini video player.** Just the picture, with a thin progress line. Drag it to move it, pinch to resize it. Tap it to show play/pause, an expand button (opens the full video) and a close button; double-tap opens the full video. The corner resize handle is gone.

### Earlier, in beta.37 (Android)

- **Ad-free podcasts (new setting, on by default).** A podcast's own feed has ads built into the audio, so Sevbify now plays the episode's YouTube version when there is one and skips its sponsor reads (Settings → Playback → Ad-free podcasts; the sponsor switch above it stays on by default). If an episode has no YouTube version, or the search takes longer than 12 seconds, it plays from the feed as before. The next episode is looked up ahead of time so Next is quick. Downloads are ad-free too, with the sponsor segments saved so they're skipped offline. An episode you already started from the feed keeps playing from the feed, so your place stays right.
- **Audio ↔ Video keeps your place.** The YouTube audio and the video are the same recording, so switching no longer lands at a different point because of ads, and the video is already known (no second search). If audio hasn't resumed within 5 seconds of switching back, it's loaded again from the same point.
- **"Watch video" on a show's page.** It searched YouTube without the phone-friendly settings the rest of the app uses, and only accepted a channel with exactly the show's name. It now uses those settings and, when no channel is named like the show, finds the channel of the video that matches one of the show's episodes.
- **Smoother app.** The release build is now shrunk and optimised (R8), which Compose and the player run noticeably faster with than the unoptimised build.
- **Podcast resume no longer jumps back.** After a buffering pause an episode no longer jumped back to the last saved spot (up to 5 seconds).
- **Mini video player: the expand arrows work.** Tap them to open the video full size; drag them to resize it.

### Earlier, in beta.36 (Android)

- **Picking a new song no longer shows the old song's progress or keeps playing the old song.** While the new song is being found, the player now shows it at 0:00 and the previous song stays paused. The progress bar also only switches to the song's real length once it's known, which was a cause of it jumping around while streaming.
- **Next song is found in advance.** While a streamed song plays, the next one is looked up in the background, so Next starts quickly instead of "Finding the full song…".
- **Search works like Spotify's.** The Search tab shows a search bar and Browse all; tap the bar (or tap the Search tab again) to open the search page with the keyboard and your Recent searches (each with an X, plus "Clear recent searches"). Back returns to Browse all.
- **Typing in Search is smoother.** Searching your own songs now happens in the background after you pause typing.
- **Song radio like Spotify.** "Go to song radio" just opens the radio page. It doesn't start playing and doesn't touch your queue; press Play there to listen. Radios also have more songs.
- **Menus and the Share sheet are no longer cut off.** Song menu, Share, Add to playlist and similar sheets now open fully and scroll if they're taller than the screen.
- **Podcast video stays on.** If you're watching an episode and go to the next one (Next, or when it finishes), it opens as video too (or plays audio if that episode has no video). Switching back to audio resumes more reliably.

### Earlier, in beta.35 (Android)

- **Smoother skipping.** The player no longer jumps around when you skip: the status line keeps its place, the background colour fades to the next cover's colour instead of flashing grey, covers fade in, and the covers of the next and previous songs are fetched ahead of time.
- **Song radio no longer restarts the song.** "Go to song radio" on the song that's playing carries on from where it is; only the queue after it changes. Asking for the same song twice in a moment (two screens at once) now plays it once.
- **Picking a new song stops the old sound straight away** instead of the old song/podcast carrying on while the new one is found.
- **Podcast Video button, step 2.** It now says why it couldn't find the video (e.g. "10 results, best match 40%"), the length check is more forgiving (ads make the podcast audio a different length), and the same note appears in Settings → About and updates → Playback status so it can be tuned.
- Note: ads you hear in a podcast (like Fin vs History) are part of the show's own audio file from the podcast's host, not something Sevbify adds. YouTube versions of episodes have their sponsor segments skipped automatically (Settings → Playback).

### Earlier, in beta.34 (Android)

- **No more flicker between Home and Search.** Coming back to Search shows your last search straight away instead of an empty page that searches again, and Home keeps its shelves (Trending podcasts, Top in Comedy, …) instead of clearing and reloading them every time you switch tabs.

### Earlier, in beta.33 (Android)

- **Download notification shows what's downloading.** The notification now reads "Downloading *Song title*" with the artist underneath and how many are still to go, a progress bar for the whole batch ("2 of 5"), and when you pull it open it lists the next songs in the queue. Tapping it opens Sevbify.
- **Automatic playback check.** Every build is now played on a test phone before it can be called good, so a build where songs don't play gets caught before you see it.

### Earlier, in beta.32 (Android)

- **Audio / Video switch for ordinary podcasts.** Open any podcast episode (like Fin vs History) and the **Audio | Video** switch is on the Now Playing screen. Tap **Video** and Sevbify finds that episode's video on YouTube and carries on from the same point (it only picks a video whose title and length match, otherwise it tells you it couldn't find one).

### Earlier, in beta.31 (Android)

- **Songs play again (the real cause found).** The Android Auto support added a rule that threw away every song the app handed to its own player, so each one "ended" the instant it started and Sevbify skipped on to the next. That's why local songs, streamed songs and podcasts all failed together. Only songs picked on a car's screen are special-cased now; everything else plays normally.

## What's new in beta.30 (Android)

- Removed an extra security layer from the player (this turned out not to be the cause of songs not playing — see beta.31). Server sign-ins on Jellyfin/Nextcloud are unaffected for normal use; the redirect hardening will come back later.

### Earlier, in beta.29 (Android)

- **Playback status readout (to track down songs that won't play).** Settings → About and updates → **Playback status** shows what the player last did, including *why* it stopped. If a song won't play, tap it, come back here, tap **Copy**, and send it over.
- **Less lag.** The app no longer re-saves your whole library on the UI thread every time a song changes, so navigation should feel smoother.

### Earlier, in beta.28 (Android)

- **Experiment: trying to get YouTube songs playing on the phone.** The phone has no JavaScript engine to solve YouTube's new playback challenge (the desktop app does), which is why mainstream songs were stuck on "Finding the full song…". This build asks YouTube for its audio a different way that may work without one. It may or may not fully fix it — if songs still won't play, use **Settings → Data-saving → "Bandcamp + YouTube"** so Bandcamp songs play, and use the desktop app for the rest.

### Earlier, in beta.27 (Android)

- **Choose Beta or Stable updates.** New switch in **Settings → About and updates → "Beta (test) updates"**. On = you get pre-release test builds as soon as they're out (leave it on for now, since everything is a beta). Off = only full official releases, so you'll never be offered a rough test build. It re-checks the moment you flip it.

### Earlier, in beta.26 (Android)

- **"Check for updates" is instant now** — tapping it fetches the latest straight from GitHub instead of after a delay.

### Earlier, in beta.25 (Android)

- **No more "spazzing" through songs.** When songs can't be played (e.g. the online song-finder is having trouble), the player now stops after a few tries with a clear message instead of racing through the whole list.
- **Pick your music folder by browsing.** Settings → Data-saving and offline → Music folders now has a **Browse…** button: choose the folder in your file explorer instead of typing its name.
- **Tidier Downloads screen.** Each download now shows its cover, song title and artist, with a progress bar on the one that's downloading.
- **Cleaner update bar.** Removed the odd green dot on the right of the update progress bar.

### Earlier, in beta.24 (Android)

- **Settings update instantly** — media quality and toggles change the moment you tap them.
- **30-second previews are one simple setting** in Settings → Playback (off by default = full songs).
- **Open with / Share → Sevbify** — hand a song to Sevbify from your file manager.

(Windows, macOS and Linux are unchanged in these builds.)

---

## Install (Windows)

Everything is included (player engine, downloader, ffmpeg); nothing else to install.

1. Under **Assets** below, download **Sevbify-Windows.zip**.
2. Right-click the zip → **Extract All…** → **Extract**.
3. Open the extracted `Sevbify` folder and double-click **Sevbify.exe**.
   If Windows says "Windows protected your PC", click **More info** → **Run anyway** (the app isn't signed yet).
4. Optional: in Sevbify, **Settings** (⚙ top right) → **Add to Desktop and Start menu**.

Your playlists and settings are kept between versions (`%APPDATA%\Sevbify`). From beta.21 on, Sevbify offers new
versions itself: **Download**, then it restarts into the new one.

## Install (Android, new and experimental) — Android 13 or newer

1. On your phone, open this release and, under **Assets**, tap **Sevbify-Android.apk**.
2. Open the downloaded file. If Android asks, allow your browser to **install unknown apps**, then tap **Install**.
   Play Protect may warn that the app is unknown — tap **Install anyway** (it's your own app, not from the Play Store).
3. Open Sevbify, allow **Music and audio** (so it can see your songs) and **Notifications** (for the player
   and download progress).

Updating: from beta.21 on, Sevbify offers new versions itself (Download → Install); your playlists stay. The Android app uses the same core as
the Windows app (search, radio, full-song finding, downloads, importing, podcasts, audiobooks), with a layout
based on Spotify's phone app: Home, Search, Your Library and Create along the bottom, a mini player above them,
and the full now-playing screen. It only reads music from the folders you choose in Settings.
Downloaded songs are saved to `Music/Sevbify/<Artist>` on the phone.

## Install (macOS, new and experimental) — Apple Silicon Macs (M1 or newer)

1. Under **Assets**, download **Sevbify-macOS.zip** and double-click it to unzip.
2. Drag **Sevbify** into **Applications**.
3. The first time, **right-click Sevbify → Open → Open** (the app isn't from the App Store or signed by Apple,
   so a plain double-click is blocked once). If macOS still refuses: **System Settings → Privacy & Security →
   Open Anyway**.

Everything is included (VLC's player engine, ffmpeg, the downloader). Playlists and settings are kept in
`~/Library/Application Support/Sevbify`. Older Intel Macs aren't supported by this download yet.

## Install (Linux, new and experimental) — 64-bit, Ubuntu 22.04 or newer (or similar)

1. Install VLC (Sevbify plays music with it): `sudo apt install vlc` (Fedora: `sudo dnf install vlc`, Arch:
   `sudo pacman -S vlc`).
2. Under **Assets**, download **Sevbify-Linux.tar.gz** and extract it (right-click → Extract, or
   `tar xzf Sevbify-Linux.tar.gz`).
3. Open the `Sevbify` folder and run `./Sevbify`. To add it to your app menu, run `./install.sh` once.
   If it doesn't start on a very minimal system, also install `libxcb-cursor0`.

Playlists and settings are kept in `~/.local/share/Sevbify`.

## Install (iPhone / iPad, new and experimental) — iOS 16 or newer, free with AltStore or SideStore

Apple doesn't let apps be installed straight from a website, so the iPhone app is **sideloaded**: a free helper app
signs it with your own Apple ID. Nothing is paid and Sevbify gets no access to your Apple ID.

1. Install **AltStore** (altstore.io, needs a Windows PC or Mac once) or **SideStore** (sidestore.io).
2. On your iPhone, open this release in Safari and tap
   **Sevbify-iOS.ipa** to download it.
3. In AltStore / SideStore: **My Apps → +** and choose the downloaded `Sevbify-iOS.ipa`.
4. iOS 16+: turn on **Settings → Privacy & Security → Developer Mode** when asked (the iPhone restarts once).
5. For updates: in SideStore / AltStore, **Sources → +** and add
   `https://raw.githubusercontent.com/Obamna1234/Sevbify/altstore/source.json` (or Sevbify's Settings → Sevbify
   updates → Add Sevbify to SideStore). New versions then show up under Updates.
6. With a free Apple ID the app must be refreshed every **7 days** (AltStore does it on the same Wi-Fi as your
   computer; SideStore on the phone), and only 3 sideloaded apps can be active at a time.

Your songs: download them in Sevbify, or put files in **Files → On My iPhone → Sevbify**, or add a folder in
Your Library. What's different from Android: no podcasts, audiobooks, lyrics or video yet, and iPhones can't run
helper programs, so YouTube may fail more often (Bandcamp is tried first).

## What's in this version

beta.23:
- **Your own music servers:** add a Jellyfin or Nextcloud server in Settings (computers and Android). Its songs
  become a playlist; stream them, or download them straight from your server.
  - Jellyfin keeps only a revocable sign-in token, not your password. For Nextcloud, use an app password.
  - The sign-in stays on your device and never leaves your server's address.
- **Folders from other apps (Android):** add a folder from an SD card or a cloud app that offers folders in
  Android's file picker (Nextcloud, OneDrive, Dropbox, …). Your sign-in stays in that app.
- **Save space:** on Windows / Mac / Linux, downloaded podcast episodes and audiobook chapters are kept as small Opus
  files (about a third of the size; speech sounds the same). The original is only replaced after the new file checks
  out, and your own music is never changed. Song downloads have a "Save space" quality too.
- **Android Auto:** your playlists, Recently played and Your Songs on the car's screen.
  - Android Auto only lists Play Store apps until you switch on "Unknown sources" in its developer settings, and no
    app can do that for you. Settings → Car shows how, and Sevbify reminds you if Android Auto hasn't found it.
  - Not yet tested in a real car.
- **iPhone:** Settings explains CarPlay. Music plays through it with controls on its Now Playing screen, but a
  sideloaded app can't have its own CarPlay icon.
- **Security review of the new features:**
  - The updater only replaces a folder that's clearly Sevbify's own, and only with GitHub's checksum.
  - Server sign-ins never follow a redirect to another site.
  - Other Android apps can't read your playlists or history.
  - Playlist files can't make Windows contact other computers.
  - Downloads never overwrite a song you already have.

beta.22:
- **Importing a playlist file:** you name the playlist first (the file's name is filled in). Then every song is
  checked online. Songs that can't be found as written are listed under **Check the spelling**, with the closest
  real song filled in. Fix them there, keep them, or edit the file and import it again.
- **Spotify links with more than 100 songs:** Sevbify quietly tries to get the rest. If Spotify says no, it offers
  **Open Chosic**: your link is copied and Chosic's free exporter opens in the browser; press Export there.
  - Windows / Mac / Linux: Sevbify picks the downloaded file up from Downloads by itself.
  - Phones: you choose the file when you come back.
  - Either way, the songs are added to the same playlist.
- **Typos in search** now show results for the right spelling straight away ("Showing results for …"), with
  "Search instead for …" to go back. Your own songs also match small typos.
- **Spotify-style motion on Android:**
  - The profile menu slides in from the left (tap the logo, or swipe from the edge).
  - Pages slide in and out.
  - Swipe left and right between the filters on Home and in Your Library.
  - Your Library has a Sort by sheet and a list/grid button.
  - Recent searches have an X each.
- **iPhone:** the profile menu slides in the same way.

beta.21:
- **Full songs only.** Songs from imports, playlists, search and radio always play in full. If the full song can't be
  found, it's skipped ("Full song not found"); there's no automatic 30-second clip any more. A clip only plays when
  you pick **Preview (30 s)** from a song's menu: it opens a small window with a seek bar.
- **Updates inside the app.** Each new version is offered once.
  - Windows / Mac / Linux: Download, then restart.
  - Android: Download, then Android's installer.
  - iPhone: through the SideStore / AltStore source.
  Files come only from Sevbify's GitHub releases and are checksum-checked.
- **20 languages:** English, Spanish, French, German, Portuguese, Italian, Russian, Chinese, Japanese, Korean,
  Arabic, Hindi, Turkish, Dutch, Polish, Indonesian, Vietnamese, Thai, Ukrainian and Swedish.
  - Android and iPhone follow the phone's language for Sevbify (Android 13+: Settings → Apps → Sevbify →
    Language). On computers it's in Settings → Language.
  - Menus, tabs, buttons and settings are translated; longer explanations stay in English for now.
  - Search works in every language either way.
- **Did you mean…?** When a finished search finds nothing like what you typed, Sevbify asks DuckDuckGo for the
  right spelling. Only that search is sent, nothing else. A suggestion is shown only if it finds music.
- **Search** ignores accents and case in every script. On the Podcasts tab it also finds shows that are only on
  YouTube. Unrelated podcasts no longer show up on the All tab.
- **Android Settings** are now Spotify-style: Data saver and Private session on top, then pages for Content and
  display, Privacy and profile, Playback, Data-saving and offline, Media quality, and About and updates.
- **Phones import playlist files** (.csv from Exportify / TuneMyMusic, .txt, .m3u): any number of songs, which
  gets around Spotify's 100-songs-per-link limit.
- **Fixed:**
  - A renamed playlist didn't update until you tapped elsewhere.
  - Album covers were missing for some imported songs: Apple and Spotify are now tried when Deezer has no match.

beta.20: final checks before testing. A profile file from someone else can't point songs at files on your
device or unpack into gigabytes, text from the internet (titles, lyrics, descriptions) is always shown as plain
text on Windows / Mac / Linux, and opening a genre while an artist page loads no longer mixes the two up. Checked on
the Android emulator (every new screen, 1,500 random taps, no crashes) and the iPhone simulator.

beta.19: **your Sevbify profile**: one small file (.sevbify) with your playlists, folders, podcasts,
audiobooks, where you stopped, recently played, recent searches and settings. Export it in Settings and open it in
Sevbify on any device: Windows, Mac, Linux, Android or iPhone. It stays where you save it; Sevbify never uploads
it. On Android it can also keep itself in Download/Sevbify, so it survives uninstalling the app. Search also
remembers your recent searches now (with Clear), on every version.

**Android: new signing key.** Sevbify's code is now public, so the app is signed with a new key kept only in
GitHub's secrets. Android won't install it over an older Sevbify: **uninstall the old one first** (your playlists in
the app are removed with it; songs you downloaded stay in Music/Sevbify).

beta.18: the same Spotify features on the other apps. Windows / macOS / Linux: "Go to artist" opens a full artist
page (popular songs with Play, Shuffle and Artist radio, your own songs by them, latest release, albums, singles &
EPs, compilations), Play and Shuffle on genre pages, and the Podcasts and Audiobooks pages gain trending plus a
shelf per category. iPhone: song radio opens its own page, genre pages have Play and Shuffle, and artist pages have
"See more" and their albums, singles and compilations.
beta.17 (from the first Android test): Spotify-style progress bar, white Now Playing buttons, song radio opens its
own "… Radio" page, folders are named before they're made (and can be renamed or deleted by holding them), Explore
for podcasts and audiobooks (trending plus a shelf per category), a Play button on genre pages, artist pages with
more songs ("See more") and their albums, singles and compilations, sponsor reads skipped in YouTube episodes
(SponsorBlock, private), and the "Audiobooks" tab no longer breaks onto two lines. Fixed: the first song could say
it was "cancelled".
beta.16: **Sevbify for iPhone and iPad** (sideloaded with AltStore or SideStore; see above). It runs the same
shared core as the other apps: search, full songs, downloads, playlists, imports, song radio, autoplay, lock-screen
controls and AirPlay. Mac and iPhone builds now run only for releases, to save GitHub's paid minutes.
beta.15: **Sevbify for macOS (Apple Silicon) and Linux**, alongside Windows and Android. Same app and features;
see the install steps above. Both are new: please report anything that looks or behaves differently.
beta.14: import playlists and albums from Deezer and Jamendo links too, and simpler border colours (Settings →
"Show where playlists came from"): grey = made in Sevbify, blue = from a file, green = Spotify, white = Apple
Music, purple = Deezer, orange = Jamendo.
beta.13: playlist pictures made Spotify's way (the first 4 different albums as a 2x2 grid, or the first song's
cover), an optional coloured border showing which playlists you made and which you imported (Settings, off by
default), playlist lengths written like Spotify ("about 2 hr 45 min" / "2h 45min"), and song radio that listens
to skips (skip an artist early and the radio plays less of them, for that radio only; nothing is saved).
beta.12: lyrics (synced, like Spotify), share songs as Spotify/YouTube links, Connect (speakers/Bluetooth), and
Download all or choose songs for playlists.
beta.11: Go to album opens the whole album in order; podcast episodes always play in order (never shuffled).
beta.10: video podcasts inside the app (Audio/Video switch, movable and resizable mini player), download quality
settings (Best original audio / MP3 / Data saver), podcast search that puts the show you typed first, and yt-dlp
keeping itself up to date (checksum-checked). Earlier, beta.9: a security and stability pass on both apps (see `CHANGELOG.md`): links from podcast feeds can only
be web addresses, Android starts faster and handles downloads, offline and errors more safely.

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
