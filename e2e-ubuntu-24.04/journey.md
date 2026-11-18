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
