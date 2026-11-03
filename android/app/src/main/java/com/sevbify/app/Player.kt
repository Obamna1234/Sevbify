package com.sevbify.app

import android.content.ComponentName
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.compose.runtime.getValue
import coil.imageLoader
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player as MediaPlayer
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.MoreExecutors
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File

/**
 * Sevbify's queue and playback, like the Windows app's: a context (playlist, album, radio, search...),
 * "Add to queue" songs that play next, shuffle and repeat, songs you don't have streaming in full (found by
 * the shared core) and podcasts / audiobooks continuing where you stopped.
 */
object Player {
    var current by mutableStateOf<Track?>(null)
    var isPlaying by mutableStateOf(false)
    /** A song is being found / buffered after you picked it: shown as playing (like Spotify), not as paused. */
    var loading by mutableStateOf(false)
    val showPlaying: Boolean get() = isPlaying || loading
    var position by mutableLongStateOf(0L)
    var duration by mutableLongStateOf(0L)
    var status by mutableStateOf("")            // "Finding the full song…", "30-second preview", errors
    var diag by mutableStateOf("")              // recent playback events, for Settings ▸ About ▸ Playback status
    var sourceName by mutableStateOf("")

    /** A short rolling log of what the player did (states, errors, why it paused) so a stuck "loads but won't
     *  play" can be read in the app without a computer. Newest at the bottom; last 16 lines kept. */
    private fun diagLog(s: String) {
        val stamp = android.text.format.DateFormat.format("HH:mm:ss", System.currentTimeMillis())
        diag = (diag.split("\n").filter { it.isNotBlank() } + "$stamp  $s").takeLast(16).joinToString("\n")
    }

    private fun stateName(s: Int) = when (s) {
        MediaPlayer.STATE_IDLE -> "IDLE"; MediaPlayer.STATE_BUFFERING -> "BUFFERING"
        MediaPlayer.STATE_READY -> "READY"; MediaPlayer.STATE_ENDED -> "ENDED"; else -> "state$s"
    }

    private fun pwrReason(r: Int) = when (r) {
        MediaPlayer.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST -> "user"
        MediaPlayer.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_FOCUS_LOSS -> "AUDIO_FOCUS_LOSS"
        MediaPlayer.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_BECOMING_NOISY -> "becoming_noisy"
        MediaPlayer.PLAY_WHEN_READY_CHANGE_REASON_REMOTE -> "remote"
        MediaPlayer.PLAY_WHEN_READY_CHANGE_REASON_END_OF_MEDIA_ITEM -> "end_of_item"
        else -> "reason$r"
    }

    /** A one-line snapshot of the player right now, shown above the log. */
    fun diagSnapshot(): String {
        val c = controller
        return "connected=${c != null}  playing=${c?.isPlaying}  playWhenReady=${c?.playWhenReady}  " +
               "state=${c?.let { stateName(it.playbackState) }}  out=${com.sevbify.app.ui.AudioOutput.name}"
    }
    var shuffle by mutableStateOf(Library.settings.shuffle)
    var repeat by mutableStateOf(Library.settings.repeat)   // off / all / one
    var noticeFor by mutableStateOf<Track?>(null)           // the one-time streaming notice is waiting
    val context = mutableStateListOf<Track>()               // the songs being played from, in play order
    val userQueue = mutableStateListOf<Track>()             // "Add to queue"
    var index by mutableStateOf(0)

    private var controller: MediaController? = null
    // A play asked for before the player finished connecting (e.g. "Open with Sevbify" cold-starts the app):
    // held here and started as soon as connect() is ready, so the first song is never dropped.
    private var pendingPlay: Triple<Track, List<Track>, String>? = null
    private var original: List<Track> = emptyList()
    private var loadJob: Job? = null
    private var ticker: Job? = null
    private var handledEnd = false
    private var lastResumeSave = 0L
    private var failuresInARow = 0
    private var plainHost = ""                  // host whose https failed, waiting to see if plain http plays
    private fun hostOf(link: String): String = try { Uri.parse(link).host.orEmpty().lowercase() } catch (e: Exception) { "" }
    private var plainHttpFor = ""               // episode whose https:// version failed              // stops skipping when nothing in the queue can play

    fun connect(context: Context) {
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token).buildAsync()
        future.addListener({
            controller = future.get()
            pendingPlay?.let { (t, q, s) -> pendingPlay = null; play(t, q, s) }   // a play that was waiting to connect
            controller?.addListener(object : MediaPlayer.Listener {
                override fun onIsPlayingChanged(playing: Boolean) {
                    isPlaying = playing
                    if (playing && ownItemLoaded()) loading = false
                    // The plain-http version of an episode played after its https one failed: remember the host.
                    if (playing && plainHost.isNotEmpty()) {
                        Library.plainHttpHosts.add(plainHost); Library.save(); plainHost = ""
                    }
                    if (playing) { failuresInARow = 0; prefetchNext() }
                    diagLog("isPlaying=$playing")
                }
                override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                    diagLog("playWhenReady=$playWhenReady (${pwrReason(reason)})")
                }
                override fun onPlaybackStateChanged(state: Int) {
                    diagLog(stateName(state))
                    if (state == MediaPlayer.STATE_ENDED || (state == MediaPlayer.STATE_READY && ownItemLoaded())) loading = false
                    if (state == MediaPlayer.STATE_READY) {
                        duration = controller?.duration?.takeIf { it > 0 } ?: duration
                        // Once per start: going READY again after a buffering gap must not jump back to the last saved spot.
                        if (!resumeDone) { resumeDone = true; applyResume() }
                    }
                    if (state == MediaPlayer.STATE_ENDED && !handledEnd) {
                        handledEnd = true
                        current?.let { if (it.isItem) { Library.finished.add(it.itemKey); Library.resume.remove(it.itemKey) } }
                        advance(auto = true)
                    }
                }
                override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                    diagLog("ERROR ${error.errorCodeName}: ${error.message?.take(80)}")
                    loading = false
                    val t = current
                    if (t != null && t.isItem && plainHttpFor != t.itemKey &&
                        t.streamUrl.ifEmpty { t.downloadUrl }.startsWith("http://")) {
                        plainHttpFor = t.itemKey          // the https version didn't work: try the original link
                        plainHost = hostOf(t.streamUrl.ifEmpty { t.downloadUrl })
                        start(); return
                    }
                    status = "Couldn't play this song (${error.errorCodeName}); skipping"
                    advance(auto = false, failed = true)
                }
            })
        }, MoreExecutors.directExecutor())
        ticker?.cancel()
        ticker = SevbifyApp.instance.scope.launch {
            while (isActive) {
                if (videoMode) {
                    VideoPlayer.player?.let { v ->
                        position = v.currentPosition.coerceAtLeast(0)
                        if (v.duration > 0) duration = v.duration
                        isPlaying = v.isPlaying
                        if (v.isPlaying && System.currentTimeMillis() - lastResumeSave > 5000) {
                            VideoPlayer.savePosition(); lastResumeSave = System.currentTimeMillis()
                        }
                    }
                    skipSponsor(position)?.let { VideoPlayer.player?.seekTo(it) }
                    delay(500); continue
                }
                controller?.let { c ->
                    val t = current
                    // While the next song is being found, the previous one is still loaded in the player: its
                    // progress must not show under the new title (it looked like the bar jumping), and it must
                    // not carry on playing.
                    val mine = t == null || c.currentMediaItem?.mediaId == t.matchKey
                    if (!mine) {
                        position = 0
                        if (c.isPlaying && loadJob?.isActive == true) c.pause()
                    } else {
                        val p = c.currentPosition.coerceAtLeast(0)
                        // Just after you moved the bar, keep showing where you moved it to until the player has
                        // caught up (otherwise the bar jumps back for a moment, then forward).
                        position = if (System.currentTimeMillis() - lastSeekAt < 1200 && kotlin.math.abs(p - lastSeekTo) > 2000) lastSeekTo else p
                        if (c.isPlaying) skipSponsor(position)?.let { c.seekTo(it); position = it }
                        // The real length, once known (before that the length from the search result is used).
                        if (c.duration > 0 && c.playbackState == MediaPlayer.STATE_READY) duration = c.duration
                        if (t != null && t.isItem && c.isPlaying && !Library.privateSession &&
                            System.currentTimeMillis() - lastResumeSave > 5000) {
                            Library.resume[t.itemKey] = position
                            lastResumeSave = System.currentTimeMillis()
                            Library.save()
                        }
                    }
                }
                delay(250)
            }
        }
    }

    // --- choosing what plays ---------------------------------------------------------------------------------
    fun play(track: Track, queue: List<Track> = listOf(track), source: String = "", keepCurrent: Boolean = false) {
        if (controller == null) { pendingPlay = Triple(track, queue, source); return }  // not connected yet: start on connect
        failuresInARow = 0
        original = queue
        sourceName = source
        // Podcast episodes and audiobook chapters always play in order (like Spotify), even with shuffle on.
        val order = if (shuffle && !queue.all { it.isItem }) listOf(track) + queue.filter { it !== track }.shuffled() else queue
        context.clear(); context.addAll(order)
        index = order.indexOfFirst { it === track }.coerceAtLeast(0)
        // Song radio of the song that's playing right now: carry on from where it is (no restart, no reload),
        // only the queue after it changes.
        val c = controller
        if (keepCurrent && c != null && current?.matchKey == track.matchKey &&
            c.currentMediaItem?.mediaId == track.matchKey && c.playbackState != MediaPlayer.STATE_ENDED) {
            if (!c.isPlaying) c.play()
            return
        }
        start()
    }

    fun playAll(queue: List<Track>, source: String, shuffled: Boolean = false) {
        if (queue.isEmpty()) return
        if (shuffled && !shuffle) toggleShuffle()
        play(if (shuffled) queue.random() else queue.first(), queue, source)
    }

    fun addToQueue(t: Track) { userQueue.add(t) }

    fun playPause() {
        if (videoMode) { VideoPlayer.player?.let { if (it.isPlaying) it.pause() else it.play() }; return }
        val c = controller ?: return
        val cur = current
        if (cur == null && context.isNotEmpty()) { start(); return }
        // Pause pressed while the song is still being found: stop looking (the old song must not start again).
        if (loading) { loadJob?.cancel(); loading = false; status = ""; return }
        // Its sound isn't loaded (it was stopped while being found): find it again.
        if (cur != null && c.currentMediaItem?.mediaId != cur.matchKey) { start(); return }
        if (c.isPlaying) c.pause() else c.play()
    }

    /** The player holds the song you picked (not the one before it, which stays loaded while the new one is found). */
    private fun ownItemLoaded(): Boolean = controller?.currentMediaItem?.mediaId == current?.matchKey

    // --- SponsorBlock: skip the ad reads in YouTube episodes (Settings; only a 4-character hash is sent) --------
    private var sponsor: Pair<String, List<LongArray>> = "" to emptyList()
    private var skipped = mutableSetOf<Long>()

    /** The YouTube page whose sponsor segments apply: the episode's own (a YouTube show), or the YouTube version a
     *  podcast episode is played/downloaded from (ad-free). "" if none. */
    private fun sponsorPageFor(t: Track): String =
        if (t.source == "youtube") t.pageUrl else Library.adFree[t.itemKey].orEmpty()

    private fun loadSponsor(t: Track) {
        sponsor = t.itemKey to emptyList(); skipped.clear()
        if (!Library.settings.skipSponsors) return
        val page = sponsorPageFor(t)
        if (page.isEmpty()) return
        Library.sponsorCache[t.itemKey]?.let { cached ->
            try {
                val a = org.json.JSONArray(cached)
                sponsor = t.itemKey to (0 until a.length()).map { i -> a.getJSONArray(i).let { s -> longArrayOf(s.getLong(0), s.getLong(1)) } }
                return                                   // known already (also works offline, for downloads)
            } catch (e: Exception) { /* unreadable: fetch again */ }
        }
        if (!Library.settings.online) return
        SevbifyApp.instance.scope.launch {
            try {
                val a = Bridge.arr("sponsor_segments", page)
                val segs = (0 until a.length()).map { i -> a.getJSONArray(i).let { s -> longArrayOf(s.getLong(0), s.getLong(1)) } }
                if (t.source != "youtube") { Library.sponsorCache[t.itemKey] = a.toString(); Library.save() }
                if (current?.itemKey == t.itemKey) sponsor = t.itemKey to segs
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
            }
        }
    }

    /** Where to jump to when the episode is inside a sponsor segment (each one is skipped once). */
    private fun skipSponsor(at: Long): Long? {
        val t = current ?: return null
        if (sponsor.first != t.itemKey) return null
        val seg = sponsor.second.firstOrNull { at >= it[0] && at < it[1] - 500 && it[0] !in skipped } ?: return null
        skipped.add(seg[0])
        status = "Skipped a sponsor segment"
        return seg[1]
    }

    private var lastSeekAt = 0L
    private var lastSeekTo = 0L

    fun seekTo(ms: Long) {
        lastSeekAt = System.currentTimeMillis(); lastSeekTo = ms
        position = ms                                   // the bar moves at once, not after the next refresh
        if (videoMode) VideoPlayer.player?.seekTo(ms) else controller?.seekTo(ms)
    }

    fun pause() { loadJob?.cancel(); loading = false; controller?.pause() }

    // --- video podcasts: the same episode as a video (Now playing's Audio / Video switch) -------------------
    /** The episode playing now is being watched (the video player has it). */
    val videoMode: Boolean get() = current?.let { VideoPlayer.track?.itemKey == it.itemKey } == true && VideoPlayer.player != null

    fun canWatch(t: Track?) = t != null && ((t.source == "youtube" && t.pageUrl.isNotEmpty()) || t.source == "podcast")

    /** Episode → its YouTube video, found once per episode (ordinary podcasts have no video of their own). */
    private val episodeVideo = HashMap<String, String>()
    private val noVideo = HashSet<String>()                       // looked for, none (this session)
    private val lookups = HashMap<String, Deferred<String>>()       // lookups in flight (they carry on if you stop waiting)
    private val adStreams = HashMap<String, org.json.JSONObject>()  // the next episode's audio link, found ahead of time

    private fun lookupPage(t: Track): Deferred<String> = lookups.getOrPut(t.itemKey) {
        SevbifyApp.instance.scope.async {
            try {
                val r = Bridge.obj("youtube_episode_for", t.artist, t.title, t.durationMs)
                diagLog("video lookup: ${r.optString("note")}")
                val url = r.optString("url")
                if (url.isEmpty()) {
                    lastVideoNote = r.optString("note"); noVideo.add(t.itemKey)
                    Library.adFreeMiss[t.artist] = (Library.adFreeMiss[t.artist] ?: 0) + 1; Library.save()
                } else {
                    episodeVideo[t.itemKey] = url
                    if (Library.adFreeMiss.remove(t.artist) != null) Library.save()
                }
                url
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                diagLog("video lookup failed: ${e.message?.take(80)}")
                lastVideoNote = e.message.orEmpty().take(80)
                lookups.remove(t.itemKey)                             // a network problem: allow trying again
                ""
            }
        }
    }

    /** The YouTube video of a podcast episode ("" if there is none, or it took longer than [waitMs]; the search
     *  carries on in the background, so asking again is quick). Found once per episode. */
    suspend fun episodePage(t: Track, waitMs: Long = 12_000): String {
        episodeVideo[t.itemKey]?.let { return it }
        Library.adFree[t.itemKey]?.let { episodeVideo[t.itemKey] = it; return it }
        if (t.itemKey in noVideo) return ""
        return withTimeoutOrNull(waitMs) { lookupPage(t).await() }.orEmpty()
    }

    /** Ad-free podcasts: allowed for this episode? (Not when it was already started from the feed: the two
     *  recordings differ by the ads, so your place would be wrong.) */
    fun adFreeAllowed(t: Track): Boolean {
        val s = Library.settings
        return t.source == "podcast" && s.adFreePodcasts && s.online && s.onlineNoticeAccepted &&
            !((Library.resume[t.itemKey] ?: 0L) > 30_000 && t.itemKey !in Library.adFree) &&
            (Library.adFreeMiss[t.artist] ?: 0) < 3          // this show has had no YouTube version 3 times: don't keep waiting
    }

    /** Watching rather than listening: kept for the next episode (Next, or when one finishes), like YouTube. */
    var preferVideo by mutableStateOf(false)
    var findingVideo by mutableStateOf(false)
    private var lastVideoNote = ""

    /** Switch from listening to watching, at the same point. */
    fun switchToVideo(context: Context, at: Long? = position, auto: Boolean = false) {
        val t = current ?: return
        if (!canWatch(t)) return
        if (!auto) preferVideo = true
        SevbifyApp.instance.scope.launch {
            var watch = t
            if (t.source != "youtube") {
                val page = episodeVideo[t.itemKey] ?: Library.adFree[t.itemKey] ?: run {
                    findingVideo = true
                    status = "Looking for this episode's video…"
                    try { episodePage(t, 30_000) } finally { findingVideo = false }
                }
                if (page.isEmpty()) {
                    status = "Couldn't find a video of this episode on YouTube" +
                        (if (lastVideoNote.isNotEmpty()) " ($lastVideoNote)" else "")
                    if (auto && current?.itemKey == t.itemKey) startAudio(t)        // no video for this one: just listen
                    else if (!auto) preferVideo = false
                    return@launch
                }
                status = ""
                episodeVideo[t.itemKey] = page
                watch = t.copy(pageUrl = page)
            }
            controller?.pause()
            VideoPlayer.load(context, watch, Library.settings.videoQuality, at?.takeIf { it > 0 })
            if (VideoPlayer.error.isNotEmpty() && auto && current?.itemKey == t.itemKey) startAudio(t)
        }
    }

    /** Switch from watching back to listening, at the same point. */
    fun switchToAudio() {
        preferVideo = false
        val t = current ?: return
        val at = VideoPlayer.position()
        VideoPlayer.stop()
        if (at > 0) Library.resume[t.itemKey] = at
        val c = controller ?: return
        if (c.mediaItemCount > 0 && c.currentMediaItem?.mediaId == t.matchKey) {
            // The listening player was only paused: carry on from where the video got to. (prepare() first: after
            // a long time paused its connection may have been dropped.)
            if (c.playbackState == MediaPlayer.STATE_IDLE) c.prepare()
            c.seekTo(at); c.play()
            // If the old connection is slow or dead (it was paused a while), load the episode afresh from here.
            SevbifyApp.instance.scope.launch {
                delay(5000)
                val c2 = controller
                if (!preferVideo && !videoMode && current?.itemKey == t.itemKey && c2 != null && c2.playWhenReady &&
                    !c2.isPlaying && c2.playbackState != MediaPlayer.STATE_ENDED) {
                    diagLog("audio didn't resume in 5 s: loading it again")
                    Library.resume[t.itemKey] = at
                    start()
                }
            }
        } else start()
    }

    fun next() {
        radioSkipFeedback()
        advance(auto = false)
    }

    /** Skipping a radio song in its first 30 s: less of that artist for the rest of this radio, like Spotify.
     *  Kept in memory only (nothing saved or sent). Same rule as PlayQueue.drop_upcoming_by_artist on Windows. */
    private fun radioSkipFeedback() {
        val t = current ?: return
        if (!sourceName.endsWith(" Radio") || userQueue.isNotEmpty() || t.isItem || index == 0) return
        if (position >= 30_000) return
        val artist = t.artist.trim().lowercase()
        if (artist.isEmpty()) return
        val rest = context.drop(index + 1)
        val kept = rest.filter { it.artist.trim().lowercase() != artist }
        if (kept.size == rest.size || kept.size < 5) return
        val removed = rest.filter { it.artist.trim().lowercase() == artist }.toSet()
        val head = context.take(index + 1)
        context.clear(); context.addAll(head + kept)
        original = original.filterNot { it in removed }
        status = "Got it: less ${t.artist} on this radio"
    }

    fun previous() {
        val c = controller ?: return
        if (c.currentPosition > 3000 || index == 0) { c.seekTo(0); return }
        index -= 1
        start()
    }

    fun jumpTo(position: Int) {
        if (position in context.indices) { index = position; start() }
    }

    fun toggleShuffle() {
        shuffle = !shuffle
        val cur = current
        if (shuffle && !context.all { it.isItem }) {
            val rest = context.drop(index + 1).shuffled()
            val head = context.take(index + 1)
            context.clear(); context.addAll(head + rest)
        } else if (original.isNotEmpty()) {
            context.clear(); context.addAll(original)
            index = original.indexOfFirst { it === cur }.coerceAtLeast(0)
        }
        Library.settings.shuffle = shuffle; Library.save()
    }

    fun cycleRepeat() {
        repeat = when (repeat) { "off" -> "all"; "all" -> "one"; else -> "off" }
        Library.settings.repeat = repeat; Library.save()
    }

    private fun advance(auto: Boolean, failed: Boolean = false) {
        if (failed) {
            failuresInARow++
            // Stop after a few failures in a row instead of racing through the whole queue (which looks like
            // the player "spazzing out"). A short run of failures means a bad connection or the song finder
            // is down, not one unplayable track, so skipping further won't help.
            if (failuresInARow >= maxOf(1, minOf(4, context.size + userQueue.size))) {
                controller?.pause(); loading = false
                status = if (Library.settings.online) "Couldn't play these right now — check your connection, or update yt-dlp in Settings" else
                    "You're offline and none of these songs are downloaded"
                return
            }
        } else failuresInARow = 0
        if (auto && repeat == "one" && !failed) { start(); return }
        if (userQueue.isNotEmpty()) {
            val t = userQueue.removeAt(0)
            context.add(index + 1, t)
            index += 1
            start(); return
        }
        if (index + 1 < context.size) { index += 1; start(); return }
        if (context.isNotEmpty() && (repeat == "all" || (!auto && !failed))) { index = 0; start(); return }
        val last = current
        if (auto && Library.settings.autoplay && Library.settings.online && last != null && !last.isItem) {
            startRadio(last, autoplay = true)                  // keep playing similar songs, like Spotify
        } else {
            controller?.pause(); loading = false
        }
    }

    fun startRadio(seed: Track, autoplay: Boolean = false) {
        if (autoplay) status = "Starting ${seed.title} Radio…"
        else com.sevbify.app.ui.Nav.say("Opening ${seed.title} Radio…")
        SevbifyApp.instance.scope.launch {
            try {
                val songs = Bridge.tracks("radio", seed.artist, seed.title, if (autoplay) 50 else 100)
                    .filter { Library.settings.explicitOk || !it.explicit }
                if (songs.isEmpty()) { status = "No radio for this song"; return@launch }
                val list = if (autoplay) songs else listOf(seed) + songs
                if (autoplay) {
                    play(list.first(), list, "${seed.title} Radio")
                    status = ""
                } else {
                    // Like Spotify: just open the radio's page. Nothing starts playing and your queue is left
                    // alone (press Play there to listen).
                    status = ""
                    com.sevbify.app.ui.Nav.nowPlayingOpen = false
                    com.sevbify.app.ui.Nav.go(com.sevbify.app.ui.Screen.Collection("Radio", "${seed.title} Radio", list, seed.art))
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
                status = "Radio needs the internet (${e.message})"
            }
        }
    }

    // --- getting a song to play --------------------------------------------------------------------------------
    private var resumeDone = false
    private var lastStartKey = ""
    private var lastStartAt = 0L

    private fun start() {
        val t = context.getOrNull(index) ?: return
        // The same song asked for twice within a moment (a double tap, or two screens both asking): once is enough.
        val now = System.currentTimeMillis()
        val c0 = controller
        if (t.matchKey == lastStartKey && now - lastStartAt < 1500 && c0 != null &&
            c0.currentMediaItem?.mediaId == t.matchKey && c0.playbackState != MediaPlayer.STATE_ENDED) return
        lastStartKey = t.matchKey; lastStartAt = now
        if (VideoPlayer.track != null && VideoPlayer.track?.itemKey != t.itemKey) VideoPlayer.stop()
        // Like Spotify: the old sound stops the moment you pick something else, not after the new song is found.
        if (c0 != null && c0.currentMediaItem?.mediaId != t.matchKey) c0.pause()
        current = t
        handledEnd = false
        resumeDone = false
        position = 0; duration = t.durationMs
        loadSponsor(t)
        preloadCovers()
        Library.played(t)
        loadJob?.cancel()
        warmJob?.cancel()                       // you chose something: stop looking up the others
        loading = false
        // Watching? Keep watching: the next episode opens as video too (listening if it has no video).
        if (preferVideo && canWatch(t) && Library.settings.online) {
            controller?.pause()
            switchToVideo(SevbifyApp.instance, at = null, auto = true)
            return
        }
        startAudio(t)
    }

    /** Find where to play this song/episode from and start it in the (audio) player. */
    private fun startAudio(t: Track) {
        loadJob?.cancel()
        loading = true
        loadJob = SevbifyApp.instance.scope.launch {
            try {
                val (uri, headers, note) = locate(t) ?: run { loading = false; return@launch }
                status = note
                PlaybackService.headers.clear()             // only the playing song's link needs them
                headers?.let { PlaybackService.headers[uri] = it }
                val meta = MediaMetadata.Builder().setTitle(t.title).setArtist(t.artist).setAlbumTitle(t.album)
                    .setArtworkUri(t.art.takeIf { it.isNotEmpty() }?.let { Uri.parse(it) }).setExtras(Bundle()).build()
                val item = MediaItem.Builder().setUri(uri).setMediaId(t.matchKey).setMediaMetadata(meta).build()
                diagLog("play '${t.title}' via ${uri.substringBefore(':')} (controller=${controller != null})")
                controller?.run {
                    setMediaItem(item); prepare()
                    if (!videoMode) { playWhenReady = true; play() }   // being watched: the sound comes with the video
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
                loading = false
                status = "⚠ ${t.title}: ${e.message}"
            }
        }
    }

    private var prefetchJob: Job? = null
    private var warmJob: Job? = null

    /** Can this song be looked up online ahead of time (a streamed song, not one you have or your own server's)? */
    private fun streamable(t: Track): Boolean {
        val s = Library.settings
        return !t.isItem && !t.isLocal && Library.localFor(t) == null && t.source != "jellyfin" && t.source != "webdav" &&
            s.online && s.streamFull && s.onlineNoticeAccepted
    }

    private suspend fun resolveQuietly(t: Track) {
        try { Bridge.obj("resolve", t.artist, t.title, t.durationMs) }
        catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e }
    }

    /** While a streamed song plays, find the next ones' streams in the background (the finder remembers them), so
     *  Next starts at once instead of "Finding the full song…" for several seconds. Three songs ahead for music
     *  (one after the other, so the phone isn't flooded); one episode ahead for podcasts. */
    private fun prefetchNext() {
        prefetchJob?.cancel()
        val ahead = (userQueue.toList() + context.drop(index + 1)).take(3)
        val nxt = ahead.firstOrNull() ?: return
        if (nxt.isItem) {
            // The next podcast episode: find its ad-free version and audio link now, so Next / the end of this one is quick.
            if (!adFreeAllowed(nxt)) return
            prefetchJob = SevbifyApp.instance.scope.launch {
                delay(4000)
                try {
                    val page = episodePage(nxt, 60_000)
                    if (page.isNotEmpty() && nxt.itemKey !in adStreams) adStreams[nxt.itemKey] = Bridge.obj("youtube_stream", page, false)
                } catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e }
            }
            return
        }
        val todo = ahead.filter { streamable(it) }
        if (todo.isEmpty()) return
        prefetchJob = SevbifyApp.instance.scope.launch {
            delay(4000)
            for (t in todo) { resolveQuietly(t); delay(500) }
        }
    }

    /** A page of songs is open (a genre, a playlist, search results): find the first few songs' streams while you
     *  look, so tapping one starts quickly. Stops as soon as you play something. Only for streamed songs, and only
     *  with the same settings that allow streaming at all. */
    fun warmUp(songs: List<Track>) {
        val todo = songs.filter { streamable(it) }.take(3)
        if (todo.isEmpty()) return
        warmJob?.cancel()
        warmJob = SevbifyApp.instance.scope.launch {
            delay(1200)
            for (t in todo) { resolveQuietly(t); delay(300) }
        }
    }

    /** Fetch the covers of the songs before/after this one now, so Next/Previous show them straight away. */
    private fun preloadCovers() {
        val app = SevbifyApp.instance
        listOf(index - 1, index + 1).mapNotNull { context.getOrNull(it)?.art?.takeIf { a -> a.isNotEmpty() } }.forEach { url ->
            try { app.imageLoader.enqueue(coil.request.ImageRequest.Builder(app).data(url).build()) } catch (_: Exception) {}
        }
    }

    /** (uri, headers, note) for a song: your file first, then the full stream (never the 30-second preview). */
    private suspend fun locate(t: Track): Triple<String, Map<String, String>?, String>? {
        if (t.isItem) {
            Library.offline[t.itemKey]?.let { if (File(it).exists()) return Triple(Uri.fromFile(File(it)).toString(), null, "Downloaded") }
            requireOnline(t) ?: return null
            if (t.source == "youtube") {
                status = "Finding the audio…"
                val s = Bridge.obj("youtube_stream", t.pageUrl, false)
                return Triple(s.getString("url"), headersOf(s), "Video podcast · audio")
            }
            if (adFreeAllowed(t)) {
                status = "Finding the ad-free version…"
                val page = episodePage(t, 8_000)
                if (page.isNotEmpty()) {
                    try {
                        val s = adStreams.remove(t.itemKey) ?: Bridge.obj("youtube_stream", page, false)
                        Library.adFree[t.itemKey] = page; Library.save()
                        loadSponsor(t)
                        return Triple(s.getString("url"), headersOf(s), "Podcast · ad-free (YouTube version)")
                    } catch (e: Exception) {
                        if (e is kotlinx.coroutines.CancellationException) throw e
                        diagLog("ad-free audio failed, using the feed: ${e.message?.take(80)}")
                    }
                }
            }
            val link = t.streamUrl.ifEmpty { t.downloadUrl }
            // Ask for the secure (https) version of old http:// episode links first; plain http only if that fails.
            // (A host that only worked over http before, and that we've already seen fail over https, goes straight to http.)
            val url = if (link.startsWith("http://") && plainHttpFor != t.itemKey && hostOf(link) !in Library.plainHttpHosts)
                "https://" + link.removePrefix("http://") else link
            return Triple(url, null, if (t.source == "audiobook") "Audiobook" else "Podcast")
        }
        Library.localFor(t)?.let { local ->
            val uri = if (local.localUri.startsWith("content:")) local.localUri else Uri.fromFile(File(local.localUri)).toString()
            return Triple(uri, null, "")
        }
        requireOnline(t) ?: return null
        if (t.source == "jellyfin" || t.source == "webdav") {
            status = "Connecting to your server…"
            val (url, headers) = MusicServers.playable(t) ?: throw CoreError("its server was removed in Settings")
            return Triple(url, headers, "From your server")
        }
        // Preview mode (Settings → Playback): play the 30-second preview instead of the full song.
        // Your own and downloaded songs already returned above, so this only affects songs you don't have.
        if (!Library.settings.streamFull) {
            status = "Playing 30-second preview…"
            val pv = t.previewUrl.ifEmpty {
                try { (Bridge.call("preview_url", t.artist, t.title) as? String).orEmpty() }
                catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e; "" }
            }
            if (pv.isNotEmpty()) return Triple(pv, null, "30-second preview")
            // no preview found → fall through to the full song
        }
        // Full song. (A 30-second clip plays in its place only when preview mode is on, handled just above.)
        if (!Library.settings.onlineNoticeAccepted) { noticeFor = t; return null }
        status = "Finding the full song…"
        try {
            val r = Bridge.obj("resolve", t.artist, t.title, t.durationMs)
            diagLog("found '${t.title}': ${r.optJSONObject("timings")?.toString() ?: "?"} (seconds)")
            return Triple(r.getString("url"), headersOf(r), "Full song · ${r.optString("source")} · not downloaded")
        } catch (e: CoreError) {
            throw CoreError("full song not found")
        }
    }

    private fun requireOnline(t: Track): Unit? {
        if (Library.settings.online) return Unit
        status = "You're offline: “${t.title}” isn't downloaded"
        advance(auto = false, failed = true)
        return null
    }

    fun acceptNotice(accepted: Boolean) {
        val t = noticeFor ?: return
        noticeFor = null
        if (accepted) {
            Library.settings.onlineNoticeAccepted = true; Library.save()
            if (current === t) start()
        } else {
            status = "Full songs need the notice accepted: “${t.title}” skipped"
            if (current === t) advance(auto = false, failed = true)
        }
    }

    private fun headersOf(o: org.json.JSONObject): Map<String, String>? = o.optJSONObject("headers")?.let { h ->
        h.keys().asSequence().associateWith { h.getString(it) }
    }

    private fun applyResume() {
        val t = current ?: return
        if (!t.isItem) return
        val ms = Library.resume[t.itemKey] ?: return
        val len = controller?.duration ?: 0
        if (ms > 5000 && (len <= 0 || ms < len - 15000)) {
            controller?.seekTo(ms)
            status = "Continuing from ${ms / 60000}:${"%02d".format((ms / 1000) % 60)}"
        }
    }

    fun upNext(): List<Track> = userQueue.toList() + context.drop(index + 1)
}
