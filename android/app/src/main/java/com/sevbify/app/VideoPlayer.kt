package com.sevbify.app

import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player as MediaPlayer
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.ProgressiveMediaSource
import androidx.media3.exoplayer.source.SingleSampleMediaSource

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
    var fullscreen by mutableStateOf(false)        // the landscape full-screen view
    var zoomFill by mutableStateOf(false)          // pinched out: fill the screen (crops the edges) instead of fitting
    var speed by mutableStateOf(1f)                // playback speed
    /** A caption track YouTube has for the video. */
    class Caption(val lang: String, val name: String, val url: String)
    var captions by mutableStateOf<List<Caption>>(emptyList())
    var captionLang by mutableStateOf("")          // the track in use ("" = none available)
    var captionsOn by mutableStateOf(false)
    private var lastInfo: org.json.JSONObject? = null
    private var lastHeaders: Map<String, String> = emptyMap()
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
                val http = (e.cause as? androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException)?.responseCode
                Player.diagLog("video ERROR ${e.errorCodeName}${if (http != null) " (HTTP $http)" else ""}")
                if (e.errorCode in 2001..2004) track?.let { Player.probeNetwork(Uri.parse(lastInfo?.optString("video").orEmpty()).host.orEmpty()) }
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
        zoomFill = false
        captions = emptyList(); captionLang = ""
        captionsOn = Library.settings.videoCaptions
        val p0 = get(context)
        p0.pause()
        try {
            val o = Bridge.obj("youtube_video", t.pageUrl, quality)
            val headers = o.optJSONObject("headers")?.let { h -> h.keys().asSequence().associateWith { h.getString(it) } } ?: emptyMap()
            lastInfo = o; lastHeaders = headers
            captions = (o.optJSONArray("captions") ?: org.json.JSONArray()).let { a ->
                (0 until a.length()).map { i -> a.getJSONObject(i).let { c -> Caption(c.getString("lang"), c.optString("name", c.getString("lang")), c.getString("url")) } }
            }
            captionLang = pickCaption(captions)
            height = o.optInt("height")
            val p = get(context)
            p.setMediaSource(buildSource(captionLang))
            applyCaptionSetting(p)
            p.setPlaybackSpeed(speed)
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

    /** The picture, the sound and (when there is one) the captions as one source. A caption that can't be
     *  loaded just doesn't show; it never stops the video. */
    private fun buildSource(lang: String): MediaSource {
        val o = lastInfo ?: throw IllegalStateException("no video loaded")
        val http = DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(true).setDefaultRequestProperties(lastHeaders)
        val factory = ProgressiveMediaSource.Factory(http)
        val video = factory.createMediaSource(MediaItem.fromUri(Uri.parse(o.getString("video"))))
        val parts = ArrayList<MediaSource>()
        parts.add(video)
        val audioUrl = o.optString("audio")
        if (audioUrl.isNotEmpty()) parts.add(factory.createMediaSource(MediaItem.fromUri(Uri.parse(audioUrl))))
        captions.firstOrNull { it.lang == lang }?.let { c ->
            val sub = MediaItem.SubtitleConfiguration.Builder(Uri.parse(c.url)).setMimeType(MimeTypes.TEXT_VTT)
                .setLanguage(c.lang.substringBefore("-orig")).setSelectionFlags(C.SELECTION_FLAG_DEFAULT).build()
            parts.add(SingleSampleMediaSource.Factory(http).setTreatLoadErrorsAsEndOfStream(true)
                          .createMediaSource(sub, C.TIME_UNSET))
        }
        return if (parts.size == 1) video else MergingMediaSource(*parts.toTypedArray())
    }

    /** Your phone's language first, then English, then whatever there is. */
    private fun pickCaption(list: List<Caption>): String {
        if (list.isEmpty()) return ""
        val mine = java.util.Locale.getDefault().language
        return (list.firstOrNull { it.lang.substringBefore("-") == mine } ?: list.firstOrNull { it.lang.substringBefore("-") == "en" }
            ?: list.first()).lang
    }

    private fun applyCaptionSetting(p: ExoPlayer) {
        p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !(captionsOn && captionLang.isNotEmpty())).build()
    }

    fun setCaptions(on: Boolean) {
        captionsOn = on
        Library.settings.videoCaptions = on; Library.changed()
        player?.let { applyCaptionSetting(it) }
    }

    /** Another caption language: the source is rebuilt, and the video carries on from the same moment. */
    fun chooseCaption(lang: String) {
        val p = player ?: return
        captionLang = lang
        captionsOn = true
        Library.settings.videoCaptions = true; Library.changed()
        try {
            val at = p.currentPosition; val was = p.playWhenReady
            p.setMediaSource(buildSource(lang), at)
            applyCaptionSetting(p)
            p.prepare(); p.playWhenReady = was
        } catch (e: Exception) { error = "Couldn't switch the captions" }
    }

    fun changeSpeed(s: Float) { speed = s; player?.setPlaybackSpeed(s) }

    fun seekBy(ms: Long) {
        val p = player ?: return
        val dur = p.duration.takeIf { it > 0 } ?: Long.MAX_VALUE
        p.seekTo((p.currentPosition + ms).coerceIn(0L, dur))
    }

    fun position(): Long = player?.currentPosition ?: 0L
    fun duration(): Long = player?.duration?.takeIf { it > 0 } ?: 0L

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
        fullscreen = false
        lastInfo = null
    }
}
