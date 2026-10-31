package com.sevbify.app

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject

/**
 * Your Sevbify profile: one small file (".sevbify") with your playlists, folders, followed shows, saved books, where
 * you stopped, recently played, recent searches and settings. The same file opens in Sevbify on Windows, macOS,
 * Linux and iPhone (format: core/profile.py). It's only ever where you save it; nothing is uploaded.
 *
 * Settings ▸ "Keep a copy in Downloads" also saves it to Download/Sevbify whenever you leave the app, so it's still
 * there if Sevbify is uninstalled: after installing again, Settings ▸ Import profile.
 */
object Profile {
    const val FILE_NAME = "Sevbify profile.sevbify"

    fun build(withHistory: Boolean = true): JSONObject {
        val s = Library.settings
        val music = Library.shows.filter { !it.isBook }.map { it.json }
        val books = Library.shows.filter { it.isBook }.map { it.json }
        return JSONObject().apply {
            put("from", "android")
            put("folders", JSONArray(Library.folders.toList()))
            put("playlists", JSONArray().also { a ->
                Library.playlists.forEach { p ->
                    a.put(JSONObject().apply {
                        put("name", p.name); put("folder", p.folder); put("pinned", p.pinned); put("origin", p.origin)
                        put("cover_url", p.coverUrl); put("created", p.created / 1000)
                        put("tracks", JSONArray().also { t -> p.tracks.forEach { t.put(it.toJson()) } })
                    })
                }
            })
            put("shows", JSONArray(music)); put("books", JSONArray(books))
            put("resume", JSONObject(Library.resume as Map<*, *>))
            if (withHistory) {
                put("recent", Library.recent.take(50).toJsonArray())
                put("searches", JSONArray(Library.searches.toList()))
            }
            put("settings", JSONObject().apply {
                put("online", s.online); put("stream_full", s.streamFull); put("explicit_ok", s.explicitOk)
                put("autoplay", s.autoplay); put("song_quality", s.songQuality)
                put("show_playlist_origin", s.showPlaylistOrigin); put("skip_sponsors", s.skipSponsors)
                put("lyrics", s.lyrics); put("shuffle", s.shuffle); put("repeat", s.repeat)
            })
        }
    }

    suspend fun bytes(withHistory: Boolean = true): ByteArray =
        Base64.decode(Bridge.call("profile_pack", build(withHistory).toString()) as String, Base64.DEFAULT)

    suspend fun exportTo(context: Context, uri: Uri): Int {
        val data = bytes()
        context.contentResolver.openOutputStream(uri, "wt")?.use { it.write(data) } ?: throw CoreError("couldn't write there")
        return data.size
    }

    /** Adds what's in a profile (never replaces your playlists; the same playlist twice is skipped). */
    suspend fun importFrom(context: Context, uri: Uri): String {
        // A profile is normally a few hundred KB: never read more than 20 MB of whatever file was picked.
        val raw = context.contentResolver.openInputStream(uri)?.use { input ->
            val out = java.io.ByteArrayOutputStream()
            val buf = ByteArray(64 * 1024)
            var total = 0
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                total += n
                if (total > 20 * 1024 * 1024) throw CoreError("That file is too big to be a Sevbify profile.")
                out.write(buf, 0, n)
            }
            out.toByteArray()
        } ?: throw CoreError("couldn't open the file")
        val d = Bridge.obj("profile_unpack", Base64.encodeToString(raw, Base64.NO_WRAP))
        d.optJSONArray("folders")?.let { a -> for (i in 0 until a.length()) a.getString(i).let { if (it !in Library.folders) Library.folders.add(it) } }
        var added = 0
        val pls = d.optJSONArray("playlists") ?: JSONArray()
        for (i in 0 until pls.length()) {
            val p = pls.getJSONObject(i)
            val tracks = p.optJSONArray("tracks")?.tracks() ?: emptyList()
            val name = p.optString("name")
            val keys = tracks.map { it.matchKey }
            if (Library.playlists.any { it.name.equals(name, true) && it.tracks.map { t -> t.matchKey } == keys }) continue
            val pl = Library.newPlaylist(uniqueName(name), tracks)
            pl.folder = p.optString("folder").takeIf { it in Library.folders } ?: ""
            pl.pinned = p.optBoolean("pinned"); pl.origin = p.optString("origin"); pl.coverUrl = p.optString("cover_url")
            added++
        }
        fun addShows(key: String) {
            val a = d.optJSONArray(key) ?: return
            for (i in 0 until a.length()) {
                val show = Show(a.getJSONObject(i))
                if (show.key.isNotEmpty() && Library.shows.none { it.key == show.key }) Library.shows.add(show)
            }
        }
        addShows("shows"); addShows("books")
        d.optJSONObject("resume")?.let { m -> m.keys().forEach { k -> if (k !in Library.resume) Library.resume[k] = m.getLong(k) } }
        d.optJSONArray("searches")?.let { a ->
            val merged = (Library.searches.toList() + (0 until a.length()).map { a.getString(it) }).distinctBy { it.lowercase() }.take(30)
            Library.searches.clear(); Library.searches.addAll(merged)
        }
        d.optJSONObject("settings")?.let { m ->
            val s = Library.settings
            if (m.has("online") && !m.getBoolean("online")) s.online = false   // a file may turn online off, never on
            if (m.has("stream_full")) s.streamFull = m.getBoolean("stream_full")
            if (m.has("explicit_ok")) s.explicitOk = m.getBoolean("explicit_ok")
            if (m.has("autoplay")) s.autoplay = m.getBoolean("autoplay")
            if (m.optString("song_quality") in listOf("best", "small")) s.songQuality = m.getString("song_quality")
            if (m.has("show_playlist_origin")) s.showPlaylistOrigin = m.getBoolean("show_playlist_origin")
            if (m.has("skip_sponsors")) s.skipSponsors = m.getBoolean("skip_sponsors")
            if (m.has("lyrics")) s.lyrics = m.getBoolean("lyrics")
        }
        Library.changed()
        return if (added == pls.length()) "Profile imported: $added playlists added"
               else "Profile imported: $added playlists added (the rest were already here)"
    }

    private fun uniqueName(wanted: String): String {
        val taken = Library.playlists.map { it.name.lowercase() }.toSet()
        if (wanted.lowercase() !in taken) return wanted
        var n = 1
        var name = "$wanted (imported)"
        while (name.lowercase() in taken) { n++; name = "$wanted (imported $n)" }
        return name
    }

    /** Settings ▸ Keep a copy in Downloads: Download/Sevbify/Sevbify profile.sevbify (Android 10+), updated whenever
     *  you leave the app. Survives uninstalling Sevbify; nothing is uploaded. */
    suspend fun backupToDownloads(context: Context) {
        if (!Library.settings.profileBackup || Build.VERSION.SDK_INT < 29) return
        // Downloads can be read by other apps with file access, so this copy leaves out what you played and searched.
        val data = bytes(withHistory = false)
        val resolver = context.contentResolver
        val saved = Library.settings.profileBackupUri.takeIf { it.isNotEmpty() }?.let { Uri.parse(it) }
        if (saved != null) {
            try {
                resolver.openOutputStream(saved, "wt")?.use { it.write(data); return }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e   // the file was deleted: make a new one
            }
        }
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, FILE_NAME)
            put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream")
            put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/Sevbify")
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return
        resolver.openOutputStream(uri, "wt")?.use { it.write(data) }
        Library.settings.profileBackupUri = uri.toString()
        Library.save()
    }
}
