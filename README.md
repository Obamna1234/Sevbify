# End-to-end reports

Build run 44404241034, checked 2026-11-18 22:19 UTC

## e2e-android-8
### Sevbify end-to-end (Android emulator)

| Step | Result | Details |
|---|---|---|
| App opens | ✅ pass | on screen: Settings, All, Music, Podcasts, Audiobooks, ♪, Your Songs, Popular right now, Dracula (with JENNIE), Tame Impala, Choosin' Texas, Ella Langley, Boston, STELLA LEFTY, Welcome to Sevbify. Search for a song, make a playlist with Create (+), or import one from Spotify under Your Library. Songs on your phone show up in Your Songs., Home, Home, Search, Search, Your Library, Your Library, Crea |
| Stream a song (Bandcamp) | ✅ pass | playing “Candlepower, Chris Zabriskie, Divider”, position moved 6004 ms in 6 s |
| Stream a song (YouTube) | ✅ pass | playing “Monkeys Spinning Monkeys, Kevin MacLeod, Monkeys Spinning Monkeys”, position moved 6070 ms in 6 s |
| Pause and resume | ✅ pass | paused: state=2, held=True; resumed: playing “Monkeys Spinning Monkeys, Kevin MacLeod, Monkeys Spinning Monkeys”, position moved 3062 ms in 4 s |
| Preview a song (30 s) | ✅ pass | card shown, your song paused (state 2) and carried on after Close (state 3) |
| Saved in (like Spotify's ✓) | ✅ pass | ⊕ saved it to Liked Songs; ✓ opened Saved in with Liked Songs ticked; Done closed it |
| Sort by energy (a sorted copy) | ✅ pass | made “My Playlist #2 · Energetic to calm”; “My Playlist #2” is still in Your Library |
| Canvas / Cover switch | 🚫 blocked here | this song has no Canvas loop (no music video found within a minute) |
| Play a podcast episode | ✅ pass | The Daily: playing “How Stable Is the A.I. Industry? We’re About to Find Out., The Daily, The Daily”, position moved 5775 ms in 6 s |
| Open Settings | ✅ pass | Settings → Playback shown |
| Pair with a computer and receive a song | ✅ pass | paired as “Android SDK built for x86_64” over the network, received “CI tone.wav” in Music/Sevbify (no self-test line) |
| No crashes | ✅ pass | 0 crash(es) / not-responding in the log |

## e2e-android
### Sevbify end-to-end (Android emulator)

| Step | Result | Details |
|---|---|---|
| Update from the last release keeps your library | ⏭ skipped | this build is debug-signed (not main), so it can't update the released app; checked on main builds |
| App opens | ✅ pass | on screen: Settings, All, Music, Podcasts, Audiobooks, ♪, Your Songs, Popular right now, Dracula (with JENNIE), Tame Impala, Choosin' Texas, Ella Langley, Boston, STELLA LEFTY, Welcome to Sevbify. Search for a song, make a playlist with Create (+), or import one from Spotify under Your Library. Songs on your phone show up in Your Songs., Home, Home, Search, Search, Your Library, Your Library, Crea |
| Stream a song (Bandcamp) | ✅ pass | playing “Candlepower, Chris Zabriskie, Divider”, position moved 6002 ms in 6 s |
| Stream a song (YouTube) | ✅ pass | playing “Monkeys Spinning Monkeys, Kevin MacLeod, Monkeys Spinning Monkeys”, position moved 6060 ms in 6 s |
| Pause and resume | ✅ pass | paused: state=2, held=True; resumed: playing “Monkeys Spinning Monkeys, Kevin MacLeod, Monkeys Spinning Monkeys”, position moved 6100 ms in 4 s |
| Preview a song (30 s) | ✅ pass | card shown, your song paused (state 2) and carried on after Close (state 3) |
| Saved in (like Spotify's ✓) | ✅ pass | ⊕ saved it to Liked Songs; ✓ opened Saved in with Liked Songs ticked; Done closed it |
| Sort by energy (a sorted copy) | ✅ pass | made “My Playlist #2 · Energetic to calm”; “My Playlist #2” is still in Your Library |
| Canvas / Cover switch | 🚫 blocked here | this song has no Canvas loop (no music video found within a minute) |
| Play a podcast episode | ✅ pass | The Daily: playing “How Stable Is the A.I. Industry? We’re About to Find Out., The Daily, The Daily”, position moved 5972 ms in 6 s |
| Open Settings | ✅ pass | Settings → Playback shown |
| Pair with a computer and receive a song | ✅ pass | paired as “sdk_gphone64_x86_64” over the network, received “CI tone.wav” in Music/Sevbify (no self-test line) |
| No crashes | ✅ pass | 0 crash(es) / not-responding in the log |

## e2e-ubuntu-22.04
### Linux (Ubuntu 22.04)

| Step | Result | Details |
|---|---|---|
| App opens | ✅ pass | window open, 0 songs in the library |
| Search the web | ✅ pass | 1 results, first: Chris Zabriskie - Candlepower |
| Stream a song (Bandcamp) | 🚫 blocked here | Bandcamp refused this computer (HTTP 200: Client Challenge JavaScript is disabled in your browser. Please enable JavaScript to proceed. A required part of this site couldn’t load. Th (Bandcamp); played from SoundCloud instead |
| Stream a song (YouTube) | 🚫 blocked here | YouTube refused this computer (ERROR: [youtube] LrM_Y39Gmhk: Sign in to confirm you’re not a bot. This helps protect our community. Use --cookies-from-browser or --cookies for the authenticat); played from SoundCloud instead |
| Pause, resume and seek | ✅ pass | pause held, resumed, seek to 1:00 worked |
| Make a playlist | ✅ pass | playlist “Journey playlist” with 1 song(s) |
| Download a song | ✅ pass | Chris Zabriskie - Candlepower.mp3 (5314 KB) in /home/runner/work/Sevbify/Sevbify/report/downloads |
| Find, follow and play a podcast | ✅ pass | NPR News Now: 4 episodes, followed: True, latest episode: position moved 5849 ms in 6 s |
| Podcast filter, search and sort | ✅ pass | 4 episodes; in progress: 1; '4pm' finds 1; oldest-first sort: True |
| Download a podcast episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR” saved as 2026-11-18 - 4pm ET, November 18  The latest headlines from NPR.opus (1523 KB), in the Podcasts folder: True |
| Your own music plays | ✅ pass | Chris Zabriskie - Candlepower: position moved 5097 ms in 5 s |
| Open Settings | ✅ pass | settings page shown |
| Zoom instantly | ✅ pass | zoomed live to 110% (pixel ratio 1.1) and back; window size kept |
| Activity log is written | ✅ pass | 43 lines, links shortened: True |
| No windows flashing up | ✅ pass | none |
| App opens again | ✅ pass | window open, 1 songs in the library |
| Everything is still there after a restart | ✅ pass | playlists ['Journey playlist', 'Journey mine'], podcasts ['NPR News Now'], 1 songs in the library |
| Play the downloaded song | ✅ pass | Chris Zabriskie - Candlepower: position moved 5849 ms in 6 s |
| Play the downloaded episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR”: position moved 5708 ms in 6 s; played from the downloaded file |
| A deleted song is remembered and can be downloaded again | ✅ pass | shown as “Candlepower   ⬇” (missing), remembered as Chris Zabriskie - Candlepower, Download again queued 1 |
| No windows flashing up | ✅ pass | none |

Linux 6.8.0-1070-azure (#78~22.04.1-Ubuntu SMP Thu Sep 24 18:46:45 UTC 2026)

## e2e-ubuntu-24.04
### Linux (Ubuntu 24.04)

| Step | Result | Details |
|---|---|---|
| App opens | ✅ pass | window open, 0 songs in the library |
| Search the web | ✅ pass | 1 results, first: Chris Zabriskie - Candlepower |
| Stream a song (Bandcamp) | 🚫 blocked here | Bandcamp refused this computer (HTTP 200: Client Challenge JavaScript is disabled in your browser. Please enable JavaScript to proceed. A required part of this site couldn’t load. Th (Bandcamp); played from SoundCloud instead |
| Stream a song (YouTube) | 🚫 blocked here | YouTube refused this computer (ERROR: [youtube] LrM_Y39Gmhk: Sign in to confirm you’re not a bot. This helps protect our community. Use --cookies-from-browser or --cookies for the authenticat); played from SoundCloud instead |
| Pause, resume and seek | ✅ pass | pause held, resumed, seek to 1:00 worked |
| Make a playlist | ✅ pass | playlist “Journey playlist” with 1 song(s) |
| Download a song | ✅ pass | Chris Zabriskie - Candlepower.mp3 (5314 KB) in /home/runner/work/Sevbify/Sevbify/report/downloads |
| Find, follow and play a podcast | ✅ pass | NPR News Now: 4 episodes, followed: True, latest episode: position moved 5849 ms in 6 s |
| Podcast filter, search and sort | ✅ pass | 4 episodes; in progress: 1; '5pm' finds 1; oldest-first sort: True |
| Download a podcast episode | ✅ pass | “5pm ET, November 18 / The latest headlines from NPR” saved as 2026-11-18 - 5pm ET, November 18  The latest headlines from NPR.opus (1442 KB), in the Podcasts folder: True |
| Your own music plays | ✅ pass | Chris Zabriskie - Candlepower: position moved 5097 ms in 5 s |
| Open Settings | ✅ pass | settings page shown |
| Zoom instantly | ✅ pass | zoomed live to 110% (pixel ratio 1.1) and back; window size kept |
| Activity log is written | ✅ pass | 43 lines, links shortened: True |
| No windows flashing up | ✅ pass | none |
| App opens again | ✅ pass | window open, 1 songs in the library |
| Everything is still there after a restart | ✅ pass | playlists ['Journey playlist', 'Journey mine'], podcasts ['NPR News Now'], 1 songs in the library |
| Play the downloaded song | ✅ pass | Chris Zabriskie - Candlepower: position moved 5849 ms in 6 s |
| Play the downloaded episode | ✅ pass | “5pm ET, November 18 / The latest headlines from NPR”: position moved 5828 ms in 6 s; played from the downloaded file |
| A deleted song is remembered and can be downloaded again | ✅ pass | shown as “Candlepower   ⬇” (missing), remembered as Chris Zabriskie - Candlepower, Download again queued 1 |
| No windows flashing up | ✅ pass | none |

Linux 7.0.0-1014-aws (#14~24.04.1-Ubuntu SMP PREEMPT Fri Sep 18 21:24:59 UTC 2026)

## e2e-windows-2022
### Windows 10 (Server 2022)

| Step | Result | Details |
|---|---|---|
| App opens | ✅ pass | window open, 0 songs in the library |
| Search the web | ✅ pass | 1 results, first: Chris Zabriskie - Candlepower |
| Stream a song (Bandcamp) | 🚫 blocked here | Bandcamp refused this computer (ERROR: [Bandcamp] candlepower: Got client challenge webpage response with chrome-152:windows-10; please report this issue on  https://github.com/yt-dlp/yt-dlp/i); played from SoundCloud instead |
| Stream a song (YouTube) | 🚫 blocked here | YouTube refused this computer (ERROR: [youtube] LrM_Y39Gmhk: Sign in to confirm you’re not a bot. This helps protect our community. Use --cookies-from-browser or --cookies for the authenticat); played from SoundCloud instead |
| Pause, resume and seek | ✅ pass | pause held, resumed, seek to 1:00 worked |
| Make a playlist | ✅ pass | playlist “Journey playlist” with 1 song(s) |
| Download a song | ✅ pass | Chris Zabriskie - Candlepower.mp3 (5314 KB) in D:\a\Sevbify\Sevbify\report\downloads |
| Find, follow and play a podcast | ✅ pass | NPR News Now: 4 episodes, followed: True, latest episode: position moved 5849 ms in 6 s |
| Podcast filter, search and sort | ✅ pass | 4 episodes; in progress: 1; '4pm' finds 1; oldest-first sort: True |
| Download a podcast episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR” saved as 2026-11-18 - 4pm ET, November 18  The latest headlines from NPR.opus (1615 KB), in the Podcasts folder: True |
| Your own music plays | ✅ pass | Chris Zabriskie - Candlepower: position moved 4949 ms in 5 s |
| Open Settings | ✅ pass | settings page shown |
| Zoom instantly | ✅ pass | zoomed live to 110% (pixel ratio 1.1) and back; window size kept |
| Activity log is written | ✅ pass | 48 lines, links shortened: True |
| No windows flashing up | ✅ pass | none |
| App opens again | ✅ pass | window open, 1 songs in the library |
| Everything is still there after a restart | ✅ pass | playlists ['Journey playlist', 'Journey mine'], podcasts ['NPR News Now'], 1 songs in the library |
| Play the downloaded song | ✅ pass | Chris Zabriskie - Candlepower: position moved 5850 ms in 6 s |
| Play the downloaded episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR”: position moved 5950 ms in 6 s; played from the downloaded file |
| A deleted song is remembered and can be downloaded again | ✅ pass | shown as “Candlepower   ⬇” (missing), remembered as Chris Zabriskie - Candlepower, Download again queued 1 |
| No windows flashing up | ✅ pass | none |

Windows 2022Server (10.0.20348)

## e2e-windows-2025
### Windows 11 (Server 2025)

| Step | Result | Details |
|---|---|---|
| App opens | ✅ pass | window open, 0 songs in the library |
| Search the web | ✅ pass | 1 results, first: Chris Zabriskie - Candlepower |
| Stream a song (Bandcamp) | 🚫 blocked here | Bandcamp refused this computer (ERROR: [Bandcamp] candlepower: Got client challenge webpage response with chrome-152:windows-10; please report this issue on  https://github.com/yt-dlp/yt-dlp/i); played from SoundCloud instead |
| Stream a song (YouTube) | 🚫 blocked here | YouTube refused this computer (ERROR: [youtube] LrM_Y39Gmhk: Sign in to confirm you’re not a bot. This helps protect our community. Use --cookies-from-browser or --cookies for the authenticat); played from SoundCloud instead |
| Pause, resume and seek | ✅ pass | pause held, resumed, seek to 1:00 worked |
| Make a playlist | ✅ pass | playlist “Journey playlist” with 1 song(s) |
| Download a song | ✅ pass | Chris Zabriskie - Candlepower.mp3 (5314 KB) in D:\a\Sevbify\Sevbify\report\downloads |
| Find, follow and play a podcast | ✅ pass | NPR News Now: 4 episodes, followed: True, latest episode: position moved 5849 ms in 6 s |
| Podcast filter, search and sort | ✅ pass | 4 episodes; in progress: 1; '4pm' finds 1; oldest-first sort: True |
| Download a podcast episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR” saved as 2026-11-18 - 4pm ET, November 18  The latest headlines from NPR.opus (1525 KB), in the Podcasts folder: True |
| Your own music plays | ✅ pass | Chris Zabriskie - Candlepower: position moved 4899 ms in 5 s |
| Open Settings | ✅ pass | settings page shown |
| Zoom instantly | ✅ pass | zoomed live to 110% (pixel ratio 1.1) and back; window size kept |
| Activity log is written | ✅ pass | 48 lines, links shortened: True |
| No windows flashing up | ✅ pass | none |
| App opens again | ✅ pass | window open, 1 songs in the library |
| Everything is still there after a restart | ✅ pass | playlists ['Journey playlist', 'Journey mine'], podcasts ['NPR News Now'], 1 songs in the library |
| Play the downloaded song | ✅ pass | Chris Zabriskie - Candlepower: position moved 5849 ms in 6 s |
| Play the downloaded episode | ✅ pass | “4pm ET, November 18 / The latest headlines from NPR”: position moved 5567 ms in 6 s; played from the downloaded file |
| A deleted song is remembered and can be downloaded again | ✅ pass | shown as “Candlepower   ⬇” (missing), remembered as Chris Zabriskie - Candlepower, Download again queued 1 |
| No windows flashing up | ✅ pass | none |

Windows 2025Server (10.0.26100)

