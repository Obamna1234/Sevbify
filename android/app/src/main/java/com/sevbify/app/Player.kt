package com.sevbify.app

import android.content.ComponentName
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.compose.runtime.getValue
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
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File

/**
 * Sevbify's queue and playback, like the Windows app's: a context (playlist, album, radio, search...),
 * "Add to queue" songs that play next, shuffle and repeat, songs you don't have streaming in full (found by
 * the shared core) and podcasts / audiobooks continuing where you stopped.
 */
object Player {
    var current by mutableStateOf<Track?>(null)
    var isPlaying by mutableStateOf(false)
    var position by mutableLongStateOf(0L)
    var duration by mutableLongStateOf(0L)
    var status by mutableStateOf("")            // "Finding the full song…", "30-second preview", errors
    var sourceName by mutableStateOf("")
    var shuffle by mutableStateOf(Library.settings.shuffle)
    var repeat by mutableStateOf(Library.settings.repeat)   // off / all / one
    var noticeFor by mutableStateOf<Track?>(null)           // the one-time streaming notice is waiting
    val context = mutableStateListOf<Track>()               // the songs being played from, in play order
    val userQueue = mutableStateListOf<Track>()             // "Add to queue"
    var index by mutableStateOf(0)

    private var controller: MediaController? = null
    private var original: List<Track> = emptyList()
    private var loadJob: Job? = null
    private var ticker: Job? = null
    private var handledEnd = false
    private var lastResumeSave = 0L
    private var failuresInARow = 0
    private var plainHttpFor = ""               // episode whose https:// version failed              // stops skipping when nothing in the queue can play

    fun connect(context: Context) {
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token).buildAsync()
        future.addListener({
            controller = future.get()
            controller?.addListener(object : MediaPlayer.Listener {
                override fun onIsPlayingChanged(playing: Boolean) {
                    isPlaying = playing
                    if (playing) failuresInARow = 0
                }
                override fun onPlaybackStateChanged(state: Int) {
                    if (state == MediaPlayer.STATE_READY) {
                        duration = controller?.duration?.takeIf { it > 0 } ?: duration
                        applyResume()
                    }
                    if (state == MediaPlayer.STATE_ENDED && !handledEnd) {
                        handledEnd = true
                        current?.let { if (it.isItem) { Library.finished.add(it.itemKey); Library.resume.remove(it.itemKey) } }
                        advance(auto = true)
                    }
                }
                override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                    val t = current
                    if (t != null && t.isItem && plainHttpFor != t.itemKey &&
                        t.streamUrl.ifEmpty { t.downloadUrl }.startsWith("http://")) {
                        plainHttpFor = t.itemKey          // the https version didn't work: try the original link
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
                    position = c.currentPosition.coerceAtLeast(0)
                    if (c.isPlaying) skipSponsor(position)?.let { c.seekTo(it); position = it }
                    if (c.duration > 0) duration = c.duration
                    val t = current
                    if (t != null && t.isItem && c.isPlaying && !Library.privateSession &&
                        System.currentTimeMillis() - lastResumeSave > 5000) {
                        Library.resume[t.itemKey] = position
                        lastResumeSave = System.currentTimeMillis()
                        Library.save()
                    }
                }
                delay(500)
            }
        }
    }

    // --- choosing what plays ---------------------------------------------------------------------------------
    fun play(track: Track, queue: List<Track> = listOf(track), source: String = "") {
        failuresInARow = 0
        original = queue
        sourceName = source
        // Podcast episodes and audiobook chapters always play in order (like Spotify), even with shuffle on.
        val order = if (shuffle && !queue.all { it.isItem }) listOf(track) + queue.filter { it !== track }.shuffled() else queue
        context.clear(); context.addAll(order)
        index = order.indexOfFirst { it === track }.coerceAtLeast(0)
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
        if (current == null && context.isNotEmpty()) { start(); return }
        if (c.isPlaying) c.pause() else c.play()
    }

    // --- SponsorBlock: skip the ad reads in YouTube episodes (Settings; only a 4-character hash is sent) --------
    private var sponsor: Pair<String, List<LongArray>> = "" to emptyList()
    private var skipped = mutableSetOf<Long>()

    private fun loadSponsor(t: Track) {
        sponsor = t.itemKey to emptyList(); skipped.clear()
        if (t.source != "youtube" || t.pageUrl.isEmpty() || !Library.settings.skipSponsors || !Library.settings.online) return
        SevbifyApp.instance.scope.launch {
            try {
                val a = Bridge.arr("sponsor_segments", t.pageUrl)
                val segs = (0 until a.length()).map { i -> a.getJSONArray(i).let { s -> longArrayOf(s.getLong(0), s.getLong(1)) } }
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

    fun seekTo(ms: Long) { if (videoMode) VideoPlayer.player?.seekTo(ms) else controller?.seekTo(ms) }

    fun pause() { controller?.pause() }

    // --- video podcasts: the same episode as a video (Now playing's Audio / Video switch) -------------------
    /** The episode playing now is being watched (the video player has it). */
    val videoMode: Boolean get() = current?.let { VideoPlayer.track?.itemKey == it.itemKey } == true && VideoPlayer.player != null

    fun canWatch(t: Track?) = t != null && t.source == "youtube" && t.pageUrl.isNotEmpty()

    /** Switch from listening to watching, at the same point. */
    fun switchToVideo(context: Context) {
        val t = current ?: return
        if (!canWatch(t)) return
        val at = position
        controller?.pause()
        SevbifyApp.instance.scope.launch { VideoPlayer.load(context, t, Library.settings.videoQuality, at.takeIf { it > 0 }) }
    }

    /** Switch from watching back to listening, at the same point. */
    fun switchToAudio() {
        val t = current ?: return
        val at = VideoPlayer.position()
        VideoPlayer.stop()
        if (at > 0) Library.resume[t.itemKey] = at
        val c = controller ?: return
        if (c.mediaItemCount > 0 && c.currentMediaItem?.mediaId == t.matchKey) { c.seekTo(at); c.play() } else start()
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
            // Every song failed (offline with nothing downloaded, or no internet with Repeat on): stop instead
            // of skipping round and round forever.
            if (failuresInARow >= maxOf(1, context.size + userQueue.size)) {
                controller?.pause()
                status = if (Library.settings.online) "Nothing in this list could be played" else
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
            controller?.pause()
        }
    }

    fun startRadio(seed: Track, autoplay: Boolean = false) {
        status = "Starting ${seed.title} Radio…"
        SevbifyApp.instance.scope.launch {
            try {
                val songs = Bridge.tracks("radio", seed.artist, seed.title, 50)
                    .filter { Library.settings.explicitOk || !it.explicit }
                if (songs.isEmpty()) { status = "No radio for this song"; return@launch }
                val list = if (autoplay) songs else listOf(seed) + songs
                play(list.first(), list, "${seed.title} Radio")
                status = ""
                if (!autoplay) {
                    // Open the radio's own page, so it's obvious what's playing (like Spotify's "… Radio").
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
    private fun start() {
        val t = context.getOrNull(index) ?: return
        if (VideoPlayer.track != null && VideoPlayer.track?.itemKey != t.itemKey) VideoPlayer.stop()
        current = t
        handledEnd = false
        position = 0; duration = t.durationMs
        loadSponsor(t)
        Library.played(t)
        loadJob?.cancel()
        loadJob = SevbifyApp.instance.scope.launch {
            try {
                val (uri, headers, note) = locate(t) ?: return@launch
                status = note
                PlaybackService.headers.clear()             // only the playing song's link needs them
                headers?.let { PlaybackService.headers[uri] = it }
                val meta = MediaMetadata.Builder().setTitle(t.title).setArtist(t.artist).setAlbumTitle(t.album)
                    .setArtworkUri(t.art.takeIf { it.isNotEmpty() }?.let { Uri.parse(it) }).setExtras(Bundle()).build()
                val item = MediaItem.Builder().setUri(uri).setMediaId(t.matchKey).setMediaMetadata(meta).build()
                controller?.run {
                    setMediaItem(item); prepare()
                    if (!videoMode) play()          // being watched: the sound comes with the video
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
                status = "⚠ ${t.title}: ${e.message}"
            }
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
            val link = t.streamUrl.ifEmpty { t.downloadUrl }
            // Ask for the secure (https) version of old http:// episode links first; plain http only if that fails.
            val url = if (link.startsWith("http://") && plainHttpFor != t.itemKey) "https://" + link.removePrefix("http://") else link
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
        // Always the full song. A 30-second clip only plays from the song menu's Preview, never in its place.
        if (!Library.settings.onlineNoticeAccepted) { noticeFor = t; return null }
        status = "Finding the full song…"
        try {
            val r = Bridge.obj("resolve", t.artist, t.title, t.durationMs)
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
