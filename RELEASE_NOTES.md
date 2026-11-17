## What's new in beta.48

> **Windows and Linux: please download this update by hand once** (from this page). Beta.47's updater can't install
> it by itself; from beta.48 on, updates install automatically again. macOS, Android and iPhone update as usual.

Everything below is on Windows, macOS, Linux, Android and iPhone unless it says otherwise.

**Listening**
- **Canvas:** when a song has an official music video, a silent 8-second loop of it plays behind Now Playing (and
  wide in full screen on the computer). Kept with downloaded songs so it works offline; storage limit in Settings.
- **Expanded Now Playing** on the computer, like Spotify's: tilting cover, Canvas, artist picture, lyrics, About the
  artist, Credits and Next in queue, with the full ••• menu.
- **Full-screen lyrics** on phones (now on iPhone too), following the song; tap a line to jump there.
- **Smart Shuffle**, **daylist** and **mood mixes**, **Discover Weekly**, **Release Radar** and **Daily Mixes** on
  every device, worked out on your device from what you play.
- **Recommended songs** under your playlists, and a **What's new** bell for new episodes and new releases.
- **Sleep timer** everywhere, including "end of this episode"; **playback speed** for podcasts and audiobooks.
- **Crossfade / gapless** on phones, **equaliser** with presets on phones, **volume levelling** (now really works on
  the computer) and **mono audio**.
- **Hide song / Don't play this artist**, with a list in Settings to bring them back.
- **Your Wrapped:** your listening stats, worked out on your device.

**Your library**
- **Liked Songs** on phones (⊕ in the mini player), **Your Episodes** (save episodes for later), **mark as played**.
- **Pin playlists**, **Downloaded** filter, **playlist folders**, **custom cover pictures and descriptions**.
- **Smart downloads** (off until you turn it on): songs you keep playing are downloaded for you; Wi-Fi only on phones.
- **Whole Spotify playlists** (optional, Settings): reads all of a public playlist, not just the first 100 songs.
  No Spotify account is used.
- **Podcasts on iPhone:** top shows, search, show pages, follow, continue where you stopped.
- **SoundCloud** results in phone search, like the computer.

**Together, without any server**
- **Share a playlist** as a link or a small file you send however you like; your friend can add it or merge it
  into theirs (collaborative playlists). **Blend:** swap "taste" links to make a playlist for both of you. Nothing
  is uploaded anywhere: the link is the playlist.
- **Remote control and Jam:** a paired phone shows what the computer is playing, controls it, and adds songs to its
  queue (your own Wi-Fi only, encrypted; switch it off in Settings).

**Everything else**
- **Windows installer** (Sevbify-Windows-Setup.exe) with an uninstaller, and a **macOS disk image**.
- **Going back:** if an update won't start, the computer goes back to the version before by itself (and Settings
  has "Go back to the previous version").
- **Feature tour** on first start (Help → Feature tour any time), an **Android home-screen widget**, Like and ±15 s
  on the iPhone lock screen.
- **Debug log** you can save as a text file (links shortened, no email addresses; nothing is sent), and a plain note
  when YouTube or another source stops working for a while (an update usually fixes it).
- Pair your phone with your computer, Support the artist, instant zoom, smooth scrolling, Help → FAQ, and many
  smaller fixes.

Tested automatically on Windows, macOS, Ubuntu, an Android emulator and an iPhone simulator.

## Install

**Windows**
1. Under **Assets** below, download **Sevbify-Windows-Setup.exe** and open it. If Windows says "Windows protected
   your PC", click **More info** → **Run anyway** (the app isn't signed yet). No admin password is needed.
2. To remove it later: Settings → Apps → Sevbify → Uninstall (it asks whether to keep your playlists and settings).
   Prefer no installer? **Sevbify-Windows.zip** still works: extract it and double-click **Sevbify.exe**.

**macOS** (Apple Silicon)
1. Download **Sevbify-macOS.dmg**, open it and drag **Sevbify** onto **Applications** (or use
   **Sevbify-macOS.zip**). To remove it, drag it from Applications to the Bin.
2. The first time, right-click Sevbify → **Open** → **Open** (or System Settings → Privacy & Security → Open Anyway).

**Linux** (64-bit, Ubuntu 22.04 or newer, or similar)
1. Install VLC: `sudo apt install vlc` (Fedora: `sudo dnf install vlc`, Arch: `sudo pacman -S vlc`).
2. Download **Sevbify-Linux.tar.gz**, extract it, and run `./Sevbify` in the `Sevbify` folder. `./install.sh` adds
   it to your app menu.

**Android**
1. On your phone, download **Sevbify-Android.apk** from Assets and open it. Allow your browser to install apps if
   asked, then tap **Install** (if Play Protect warns about an unknown app, tap **Install anyway**).
2. Open Sevbify and allow **Music and audio** and **Notifications**.

**iPhone / iPad** (iOS 16 or newer, free with SideStore or AltStore)
1. Install SideStore (sidestore.io) or AltStore (altstore.io).
2. On your iPhone, download **Sevbify-iOS.ipa** from Assets in Safari, then in SideStore / AltStore: **My Apps → +**
   and choose it. Turn on Developer Mode if iOS asks.
3. For updates: Sevbify's Settings → Sevbify updates → **Add Sevbify to SideStore**.
4. With a free Apple ID, SideStore / AltStore refreshes the app every 7 days.

After installing, Sevbify offers new versions itself. Your playlists, settings and music are kept.

The first time you pair a phone, your computer may ask whether Sevbify may use the network (Windows firewall,
macOS), and your iPhone asks about devices on your local network: choose **Allow**.

## Please use it responsibly

Only download music you have the right to download, for example songs you've bought, that the artist offers for
free, or that are openly licensed. Sevbify isn't affiliated with any music service it works with.
