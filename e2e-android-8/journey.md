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
