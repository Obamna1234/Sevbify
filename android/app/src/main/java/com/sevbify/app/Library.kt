package com.sevbify.app

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Settings, like the Windows app's (only the ones that make sense on a phone). */
data class Settings(
    var online: Boolean = true,
    var streamFull: Boolean = true,
    var source: String = "Bandcamp + YouTube",
    var autoplay: Boolean = true,
    var explicitOk: Boolean = true,
    var downloadOnWifiOnly: Boolean = false,
    var musicFolders: MutableList<String> = mutableListOf("Music"),
    var onlineNoticeAccepted: Boolean = false,
    var shuffle: Boolean = false,
    var repeat: String = "off",
    var lastfmKey: String = "",
    var libraryView: String = "list",
    var librarySort: String = "recents",
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("online", online); put("stream_full", streamFull); put("source", source); put("autoplay", autoplay)
        put("explicit_ok", explicitOk); put("wifi_only", downloadOnWifiOnly)
        put("music_folders", JSONArray(musicFolders)); put("notice", onlineNoticeAccepted)
        put("shuffle", shuffle); put("repeat", repeat); put("lastfm", lastfmKey)
        put("library_view", libraryView); put("library_sort", librarySort)
    }

    companion object {
        fun fromJson(o: JSONObject?): Settings {
            val s = Settings()
            if (o == null) return s
            s.online = o.optBoolean("online", true); s.streamFull = o.optBoolean("stream_full", true)
            s.source = o.optString("source", s.source); s.autoplay = o.optBoolean("autoplay", true)
            s.explicitOk = o.optBoolean("explicit_ok", true); s.downloadOnWifiOnly = o.optBoolean("wifi_only")
            o.optJSONArray("music_folders")?.let { a ->
                s.musicFolders = (0 until a.length()).map { a.getString(it) }.toMutableList()
            }
            s.onlineNoticeAccepted = o.optBoolean("notice"); s.shuffle = o.optBoolean("shuffle")
            s.repeat = o.optString("repeat", "off"); s.lastfmKey = o.optString("lastfm")
            s.libraryView = o.optString("library_view", "list"); s.librarySort = o.optString("library_sort", "recents")
            return s
        }
    }
}

/**
 * Everything Sevbify remembers on the phone: playlists, folders, followed shows, saved books, downloads,
 * where you stopped in episodes, recently played, settings. One JSON file in the app's private folder;
 * nothing leaves the phone.
 */
object Library {
    var coreVersion = ""
    var settings = Settings()
    val playlists = mutableStateListOf<Playlist>()
    val folders = mutableStateListOf<String>()
    val shows = mutableStateListOf<Show>()              // followed podcasts / YouTube channels / saved books
    val recent = mutableStateListOf<Track>()            // recently played (not in a private session)
    val offline = mutableMapOf<String, String>()        // song / episode key -> downloaded file
    val resume = mutableMapOf<String, Long>()           // episode / chapter key -> where you stopped (ms)
    val finished = mutableSetOf<String>()
    var localSongs by mutableStateOf<List<Track>>(emptyList())
    var privateSession by mutableStateOf(false)
    /** Bumped on every change, so screens that read it redraw. */
    var changes by mutableIntStateOf(0)
        private set

    private lateinit var file: File

    fun load(context: Context) {
        file = File(context.filesDir, "library.json")
        val o = try { JSONObject(file.readText()) } catch (e: Exception) { JSONObject() }
        settings = Settings.fromJson(o.optJSONObject("settings"))
        playlists.clear()
        o.optJSONArray("playlists")?.let { a -> for (i in 0 until a.length()) playlists.add(Playlist.fromJson(a.getJSONObject(i))) }
        folders.clear()
        o.optJSONArray("folders")?.let { a -> for (i in 0 until a.length()) folders.add(a.getString(i)) }
        shows.clear()
        o.optJSONArray("shows")?.let { a -> for (i in 0 until a.length()) shows.add(Show(a.getJSONObject(i))) }
        recent.clear()
        o.optJSONArray("recent")?.let { recent.addAll(it.tracks()) }
        offline.clear()
        o.optJSONObject("offline")?.let { m -> m.keys().forEach { k -> offline[k] = m.getString(k) } }
        resume.clear()
        o.optJSONObject("resume")?.let { m -> m.keys().forEach { k -> resume[k] = m.getLong(k) } }
        finished.clear()
        o.optJSONArray("finished")?.let { a -> for (i in 0 until a.length()) finished.add(a.getString(i)) }
        changed(save = false)
    }

    fun save() {
        if (!::file.isInitialized) return
        val o = JSONObject().apply {
            put("version", 1)
            put("settings", settings.toJson())
            put("playlists", JSONArray().also { a -> playlists.forEach { a.put(it.toJson()) } })
            put("folders", JSONArray(folders.toList()))
            put("shows", JSONArray().also { a -> shows.forEach { a.put(it.json) } })
            put("recent", recent.take(50).toJsonArray())
            put("offline", JSONObject(offline as Map<*, *>))
            put("resume", JSONObject(resume as Map<*, *>))
            put("finished", JSONArray(finished.toList().takeLast(2000)))
        }
        val tmp = File(file.parentFile, "library.json.tmp")
        tmp.writeText(o.toString())
        tmp.renameTo(file)
    }

    fun changed(save: Boolean = true) {
        changes++
        if (save) save()
    }

    // --- playlists ----------------------------------------------------------------------------------------
    fun newPlaylist(name: String? = null, tracks: List<Track> = emptyList()): Playlist {
        var n = playlists.size + 1
        var base = name?.trim().takeUnless { it.isNullOrEmpty() } ?: "My Playlist #$n"
        while (playlists.any { it.name.equals(base, true) }) {
            n++
            base = if (name.isNullOrBlank()) "My Playlist #$n" else "${name.trim()} $n"
        }
        val pl = Playlist(name = base, tracks = tracks.toMutableList())
        playlists.add(0, pl)
        changed()
        return pl
    }

    fun delete(pl: Playlist) { playlists.remove(pl); changed() }
    fun rename(pl: Playlist, name: String) { if (name.isNotBlank()) { pl.name = name.trim(); changed() } }
    fun add(pl: Playlist, tracks: List<Track>) { pl.tracks.addAll(tracks); changed() }
    fun removeAt(pl: Playlist, rows: Collection<Int>) {
        rows.sortedDescending().forEach { if (it in pl.tracks.indices) pl.tracks.removeAt(it) }
        changed()
    }
    fun move(pl: Playlist, from: Int, to: Int) {
        if (from !in pl.tracks.indices || to !in pl.tracks.indices) return
        pl.tracks.add(to, pl.tracks.removeAt(from)); changed()
    }

    fun createFolder(name: String = "New Folder"): String {
        var n = 2
        var f = name
        while (folders.any { it.equals(f, true) }) f = "$name ${n++}"
        folders.add(f); changed(); return f
    }

    fun deleteFolder(name: String) {
        folders.remove(name)
        playlists.forEach { if (it.folder == name) it.folder = "" }
        changed()
    }

    // --- songs you have / don't have yet --------------------------------------------------------------------
    /** Your own file for a song, if you have it (on the phone or downloaded by Sevbify). */
    fun localFor(t: Track): Track? {
        if (t.isLocal) return t
        offline[t.matchKey]?.let { path ->
            if (path.startsWith("content:") || File(path).exists()) return t.copy(localUri = path)
        }
        return localSongs.firstOrNull { it.matchKey == t.matchKey }
    }

    fun isDownloaded(t: Track) = t.isLocal || localFor(t) != null

    /** Songs waiting to be downloaded: every ⬇ song in your playlists, once each. */
    fun toDownload(): List<Track> {
        val seen = HashSet<String>()
        return playlists.flatMap { it.tracks }.filter { !it.isLocal && !it.isItem && localFor(it) == null && seen.add(it.matchKey) }
    }

    fun played(t: Track) {
        if (privateSession) return
        recent.removeAll { it.matchKey == t.matchKey }
        recent.add(0, t)
        while (recent.size > 50) recent.removeAt(recent.size - 1)
        changed()
    }

    fun follows(key: String) = shows.any { it.key == key }
    fun follow(show: Show) { if (!follows(show.key)) { shows.add(0, show); changed() } }
    fun unfollow(key: String) { shows.removeAll { it.key == key }; changed() }
}
