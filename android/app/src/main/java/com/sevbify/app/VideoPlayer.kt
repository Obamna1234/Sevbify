package com.sevbify.app

import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.MediaItem
import androidx.media3.common.Player as MediaPlayer
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.exoplayer.source.ProgressiveMediaSource

/**
 * Watching a video podcast (a YouTube episode). Separate from the music player: music pauses while a video
 * plays, and "Listen as audio only" hands the episode back to it at the same point. YouTube's HD comes as
 * separate picture and sound streams, which are joined here (MergingMediaSource). Picture-in-picture is the
 * mini player: the video keeps playing in a small window over other apps.
 */
@androidx.annotation.OptIn(markerClass = [UnstableApi::class])
object VideoPlayer {
    var track by mutableStateOf<Track?>(null)
    var playing by mutableStateOf(false)
    var loading by mutableStateOf(false)
    var error by mutableStateOf("")
    var height by mutableStateOf(0)                // the quality YouTube gave (720 = 720p)
    var inPip by mutableStateOf(false)             // shown in the floating mini player
    var player: ExoPlayer? = null
        private set

    fun get(context: Context): ExoPlayer = player ?: ExoPlayer.Builder(context.applicationContext).build().also { p ->
        p.addListener(object : MediaPlayer.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                playing = isPlaying
                if (isPlaying) Player.pause()          // never music and a video at the same time
            }
            override fun onPlayerError(e: androidx.media3.common.PlaybackException) {
                error = "Couldn't play the video (${e.errorCodeName})"
            }
            override fun onPlaybackStateChanged(state: Int) {
                if (state == MediaPlayer.STATE_ENDED) {
                    android.os.Handler(android.os.Looper.getMainLooper()).post {   // not inside the player's own callback
                        val t = track
                        stop()
                        t?.let { Library.finished.add(it.itemKey); Library.resume.remove(it.itemKey); Library.save() }
                        Player.next()                   // on to the next episode, like the audio player
                    }
                }
            }
        })
        player = p
    }

    /** Find the links for this quality and start (at `startMs`, or where you stopped). */
    suspend fun load(context: Context, t: Track, quality: String, startMs: Long? = null) {
        track = t
        loading = true
        error = ""
        val p0 = get(context)
        p0.pause()
        try {
            val o = Bridge.obj("youtube_video", t.pageUrl, quality)
            val headers = o.optJSONObject("headers")?.let { h -> h.keys().asSequence().associateWith { h.getString(it) } } ?: emptyMap()
            val http = DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(true).setDefaultRequestProperties(headers)
            val factory = ProgressiveMediaSource.Factory(http)
            val video = factory.createMediaSource(MediaItem.fromUri(Uri.parse(o.getString("video"))))
            val audioUrl = o.optString("audio")
            val source = if (audioUrl.isNotEmpty())
                MergingMediaSource(video, factory.createMediaSource(MediaItem.fromUri(Uri.parse(audioUrl))))
            else video
            height = o.optInt("height")
            val p = get(context)
            p.setMediaSource(source)
            p.prepare()
            val at = startMs ?: Library.resume[t.itemKey]?.takeIf { it > 5000 } ?: 0L
            if (at > 0) p.seekTo(at)
            p.play()
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
            error = "Couldn't load the video: ${e.message}"
        } finally {
            loading = false
        }
    }

    fun position(): Long = player?.currentPosition ?: 0L

    /** Remember where you are (like podcasts), unless in a private session. */
    fun savePosition() {
        val t = track ?: return
        val p = player ?: return
        if (!Library.privateSession && p.currentPosition > 5000) { Library.resume[t.itemKey] = p.currentPosition; Library.save() }
    }

    fun pause() { player?.pause() }

    fun stop() {
        savePosition()
        player?.run { stop(); release() }
        player = null
        playing = false
        track = null
        inPip = false
    }
}
