package com.sevbify.app

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File

/**
 * Downloads, one at a time in the background (with a notification), like the Windows app: songs are found
 * by the shared core (Bandcamp first, then YouTube) and saved in your Music folder under Sevbify/<Artist>,
 * where other apps and your PC can see them. Podcast episodes and audiobook chapters stay inside Sevbify.
 * Pause / Resume, Stop all (stopped songs can be resumed), Cancel or Try again for one song.
 */
object Downloads {
    enum class State { QUEUED, DOWNLOADING, FAILED, STOPPED }

    val states = mutableStateMapOf<String, State>()
    val notes = mutableStateMapOf<String, String>()
    var paused by mutableStateOf(false)
    var doneCount by mutableStateOf(0)
    private val jobs = LinkedHashMap<String, Track>()
    private var worker: Job? = null

    fun stateOf(t: Track): State? = states[if (t.isItem) t.itemKey else t.matchKey]

    fun request(tracks: List<Track>): Int {
        var added = 0
        for (t in tracks) {
            if (!t.isItem && (t.isLocal || Library.localFor(t) != null)) continue
            val key = if (t.isItem) t.itemKey else t.matchKey
            if (states[key] == State.QUEUED || states[key] == State.DOWNLOADING) continue
            jobs[key] = t
            states[key] = State.QUEUED
            notes.remove(key)
            added++
        }
        if (added > 0) kick()
        return added
    }

    fun pause() { paused = true }
    fun resume() {
        paused = false
        states.filterValues { it == State.STOPPED }.keys.toList().forEach { states[it] = State.QUEUED }
        kick()
    }

    fun stopAll() {
        states.filterValues { it == State.QUEUED || it == State.DOWNLOADING }.keys.toList().forEach { states[it] = State.STOPPED }
        worker?.cancel()
        worker = null
        stopService()
    }

    fun cancel(key: String) {
        val wasActive = states[key] == State.DOWNLOADING
        states.remove(key); notes.remove(key); jobs.remove(key)
        if (wasActive) { worker?.cancel(); worker = null; kick() }
    }

    fun retry(key: String) { if (jobs.containsKey(key)) { states[key] = State.QUEUED; notes.remove(key); kick() } }

    fun waiting() = states.count { it.value == State.QUEUED || it.value == State.DOWNLOADING }

    private fun kick() {
        if (worker?.isActive == true) return
        val app = SevbifyApp.instance
        DownloadService.cancelStop()
        try {
            ContextCompat.startForegroundService(app, Intent(app, DownloadService::class.java))
        } catch (e: Exception) { /* Android refused (app in the background): downloads still run while open */ }
        worker = app.scope.launch {
            cleanIncoming(app)
            while (true) {
                if (paused) { delay(500); continue }
                val key = states.entries.firstOrNull { it.value == State.QUEUED }?.key ?: break
                val t = jobs[key] ?: run { states.remove(key); null } ?: continue
                states[key] = State.DOWNLOADING
                DownloadService.update(app)
                if (!Library.settings.online) {
                    // Sevbify was switched offline: keep the rest as Stopped (Resume picks them up), don't
                    // sit in the notifications waiting.
                    states.filterValues { it == State.QUEUED || it == State.DOWNLOADING }.keys.toList()
                        .forEach { states[it] = State.STOPPED; notes[it] = "Sevbify is offline" }
                    break
                }
                try {
                    if (t.isItem) downloadItem(app, t) else downloadSong(app, t)
                    states.remove(key); jobs.remove(key)
                    doneCount++
                    Library.changed()
                } catch (e: kotlinx.coroutines.CancellationException) {
                    throw e
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
                    val msg = e.message ?: "couldn't be downloaded"
                    if (Regex("timed out|unreachable|resolve|connection|offline", RegexOption.IGNORE_CASE).containsMatchIn(msg)) {
                        // Not the song's fault: wait for the internet and try again (like the Windows app).
                        states[key] = State.QUEUED; notes[key] = "waiting for the internet"
                        delay(60_000)
                    } else {
                        states[key] = State.FAILED; notes[key] = msg
                    }
                }
            }
            stopService()
        }
    }

    private fun stopService() = DownloadService.requestStop()

    /** Half-finished files from downloads that failed or were stopped (they're never visible, but take space). */
    private fun cleanIncoming(context: Context) {
        val work = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "incoming")
        val old = System.currentTimeMillis() - 60 * 60 * 1000
        work.walkBottomUp().forEach { f ->
            if (f != work && f.lastModified() < old) f.delete()     // folders only go when they're empty
        }
    }

    private suspend fun downloadSong(context: Context, t: Track) {
        val work = File(context.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "incoming").apply { mkdirs() }
        val res = Bridge.obj("download_song", t.artist, t.title, t.durationMs, work.absolutePath, Library.settings.songQuality)
        val file = File(res.getString("path"))
        val saved = publish(context, file, t)
        Library.offline[t.matchKey] = saved
        Library.save()
    }

    private suspend fun downloadItem(context: Context, t: Track) {
        val dir = File(context.getExternalFilesDir(null), if (t.source == "audiobook") "Audiobooks" else "Podcasts").apply { mkdirs() }
        val safe = safeName(t.album.ifEmpty { t.artist } + " - " + t.title, "Episode").take(120)
        val path = if (t.source == "youtube") {
            Bridge.call("download_youtube", t.pageUrl, File(dir, safe).absolutePath, Library.settings.songQuality) as String
        } else {
            // The extension of the file in the link ("…/episode.m4a?x=1" → m4a); mp3 when there isn't a clear one.
            val last = t.downloadUrl.ifEmpty { t.streamUrl }.substringBefore("?").substringBefore("#").substringAfterLast('/')
            val ext = last.substringAfterLast('.', "").lowercase().takeIf { it.matches(Regex("[a-z0-9]{2,4}")) } ?: "mp3"
            Bridge.call("download_url", t.downloadUrl.ifEmpty { t.streamUrl }, File(dir, "$safe.$ext").absolutePath) as String
        }
        Library.offline[t.itemKey] = path
        Library.save()
    }

    /** A name that is safe as a file or folder name: no path characters, control characters or "..". */
    fun safeName(name: String, fallback: String): String =
        name.replace(Regex("""[\\/:*?"<>|\u0000-\u001f]"""), "_").trim(' ', '.').ifEmpty { fallback }

    /** Move a finished song into Music/Sevbify/<Artist> (visible to other apps). Returns where it is now. */
    private fun publish(context: Context, file: File, t: Track): String {
        if (Build.VERSION.SDK_INT < 29) return file.absolutePath
        val artistFolder = safeName(t.artist.split(Regex("""\s+(feat\.?|ft\.?|featuring|x|vs\.?)\s+""", RegexOption.IGNORE_CASE))
            .first(), "Unknown Artist").take(80).trim(' ', '.').ifEmpty { "Unknown Artist" }
        val values = ContentValues().apply {
            put(MediaStore.Audio.Media.DISPLAY_NAME, file.name)
            put(MediaStore.Audio.Media.RELATIVE_PATH, "${Environment.DIRECTORY_MUSIC}/Sevbify/$artistFolder")
            put(MediaStore.Audio.Media.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values)
            ?: return file.absolutePath
        return try {
            resolver.openOutputStream(uri)?.use { out -> file.inputStream().use { it.copyTo(out) } }
            values.clear(); values.put(MediaStore.Audio.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            file.delete()
            uri.toString()
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
            resolver.delete(uri, null, null)
            file.absolutePath
        }
    }
}
