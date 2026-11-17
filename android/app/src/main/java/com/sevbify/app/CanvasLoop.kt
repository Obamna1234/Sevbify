package com.sevbify.app

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.MediaItem
import androidx.media3.common.Player as MediaPlayer
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteBuffer
import java.security.MessageDigest

/** Canvas on Android, like the PC (core/canvas_loops.py): a silent 8-second loop from the song's official music
 *  video. The shared core finds the video and where the loop starts; the clip itself is cut here with Android's
 *  own video tools (no re-encoding, no ffmpeg), so only those seconds are fetched.
 *  - Clips for streamed songs live in a cache with a size limit (oldest played go first).
 *  - A downloaded song keeps its clip (in the app's files), so it loops offline too.
 *  - Off in Settings → Playback → Canvas: nothing is looked up. */
object CanvasLoop {
    var current by mutableStateOf<File?>(null)          // the clip for the song playing now (null: show the cover)
    private var player: ExoPlayer? = null
    private val busy = mutableSetOf<String>()
    private const val CLIP_US = 8_000_000L

    private fun norm(s: String) = Regex("[\\p{L}\\p{N}_]+").findAll(s.lowercase()).joinToString(" ") { it.value }
    fun key(artist: String, title: String): String =
        MessageDigest.getInstance("SHA-1").digest("${norm(artist)}|${norm(title)}".toByteArray())
            .joinToString("") { "%02x".format(it) }.take(24)

    private fun cacheDir(c: Context) = File(c.cacheDir, "canvas").apply { mkdirs() }
    private fun keptDir(c: Context) = File(c.filesDir, "canvas-kept").apply { mkdirs() }

    fun clipFile(c: Context, t: Track): File? {
        val k = key(t.artist, t.title)
        return listOf(File(keptDir(c), "$k.mp4"), File(cacheDir(c), "$k.mp4")).firstOrNull { it.isFile && it.length() > 10_000 }
            ?.also { it.setLastModified(System.currentTimeMillis()) }
    }

    /** The song changed: show its clip, or look one up in the background. */
    fun songChanged(t: Track?) {
        val c = SevbifyApp.instance
        current = null
        val s = Library.settings
        if (t == null || t.isItem || !s.canvasOn) { stop(); return }
        clipFile(c, t)?.let { show(it); return }
        stop()
        if (!s.online || t.artist.isBlank() || t.artist == "Unknown Artist") return
        val k = key(t.artist, t.title)
        if (!busy.add(k)) return
        SevbifyApp.instance.scope.launch {
            try {
                val src = Bridge.call("canvas_source", t.artist, t.title, t.durationMs) as? org.json.JSONObject ?: return@launch
                val out = File(cacheDir(c), "$k.mp4")
                val ok = withContext(Dispatchers.IO) { cut(src, out) }
                if (ok) {
                    trim(c, s.canvasCacheMb)
                    if (Library.offline.containsKey(t.matchKey)) keep(c, t)
                    if (Player.current?.let { key(it.artist, it.title) } == k) show(out)
                }
            } catch (e: Exception) {
                Log.w("Sevbify", "canvas: ${e.message}")
            } finally { busy.remove(k) }
        }
    }

    /** Copy the first ~8 s from `start` of the video-only stream into an MP4, without re-encoding. */
    private fun cut(src: org.json.JSONObject, out: File): Boolean {
        val url = src.optString("url")
        if (!url.startsWith("https://")) return false
        val headers = mutableMapOf<String, String>()
        src.optJSONObject("headers")?.let { h -> h.keys().forEach { headers[it] = h.optString(it) } }
        val startUs = (src.optDouble("start", 30.0) * 1_000_000).toLong()
        val ex = MediaExtractor()
        val part = File(out.path + ".part")
        var muxer: MediaMuxer? = null
        try {
            ex.setDataSource(url, headers)
            val track = (0 until ex.trackCount).firstOrNull {
                ex.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("video/") == true } ?: return false
            ex.selectTrack(track)
            val format = ex.getTrackFormat(track)
            muxer = MediaMuxer(part.path, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            val outTrack = muxer.addTrack(format)
            muxer.start()
            ex.seekTo(startUs, MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
            val buf = ByteBuffer.allocate(4 * 1024 * 1024)
            val info = MediaCodec.BufferInfo()
            var first = -1L
            var written = 0L
            var samples = 0
            while (true) {
                val size = ex.readSampleData(buf, 0)
                if (size < 0) break
                written += size; samples++
                // Never more than 8 MB or 2000 frames, even if the stream's timestamps don't move on.
                if (written > 8_000_000 || samples > 2000) { muxer.stop(); part.delete(); return false }
                val time = ex.sampleTime
                if (first < 0) first = time
                if (time - first > CLIP_US) break
                info.set(0, size, time - first, if ((ex.sampleFlags and MediaExtractor.SAMPLE_FLAG_SYNC) != 0)
                    MediaCodec.BUFFER_FLAG_KEY_FRAME else 0)
                muxer.writeSampleData(outTrack, buf, info)
                ex.advance()
            }
            muxer.stop()
            if (part.length() < 10_000 || part.length() > 8_000_000) { part.delete(); return false }
            return part.renameTo(out)
        } catch (e: Exception) {
            Log.w("Sevbify", "canvas cut: ${e.message}")
            part.delete()
            return false
        } finally {
            try { muxer?.release() } catch (_: Exception) {}
            ex.release()
        }
    }

    /** A downloaded song keeps its clip (loops offline). */
    fun keep(c: Context, t: Track) {
        if (!Library.settings.canvasKeepDownloads) return
        val k = key(t.artist, t.title)
        val from = File(cacheDir(c), "$k.mp4")
        val to = File(keptDir(c), "$k.mp4")
        if (from.isFile && !to.isFile) try { from.copyTo(to) } catch (_: Exception) {}
    }

    fun forget(c: Context, t: Track) { File(keptDir(c), "${key(t.artist, t.title)}.mp4").delete() }

    fun trim(c: Context, limitMb: Int) {
        val files = cacheDir(c).listFiles { f -> f.name.endsWith(".mp4") }?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (f in files) { if (total <= limitMb * 1_048_576L) break; total -= f.length(); f.delete() }
    }

    fun sizeMb(c: Context): Double = (cacheDir(c).listFiles()?.sumOf { it.length() } ?: 0L) / 1_048_576.0
    fun clear(c: Context) { cacheDir(c).listFiles()?.forEach { it.delete() } }

    // --- playback: a second, silent player that only draws the loop ------------------------------------------
    fun player(c: Context): ExoPlayer = player ?: ExoPlayer.Builder(c.applicationContext).build().also {
        it.volume = 0f
        it.repeatMode = MediaPlayer.REPEAT_MODE_ONE
        player = it
    }

    private fun show(f: File) {
        current = f
        val p = player(SevbifyApp.instance)
        p.setMediaItem(MediaItem.fromUri(android.net.Uri.fromFile(f)))
        p.prepare()
        p.playWhenReady = true
    }

    fun stop() { player?.let { it.stop(); it.clearMediaItems() } }
}
