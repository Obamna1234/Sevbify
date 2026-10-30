package com.sevbify.app

import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Your own Jellyfin / Nextcloud servers. Their sign-ins live only in Sevbify's private storage on this phone
 *  (servers.json; not in playlists, the profile file or backups) and go only to the server's own address. */
object MusicServers {
    val list = mutableStateListOf<JSONObject>()
    private var file: File? = null

    fun load(context: Context) {
        val f = File(context.filesDir, "servers.json"); file = f
        list.clear()
        try {
            val a = JSONArray(f.readText())
            for (i in 0 until a.length()) list.add(a.getJSONObject(i))
        } catch (_: Exception) {}
    }

    private fun save() {
        val f = file ?: return
        val tmp = File(f.path + ".tmp")
        tmp.writeText(JSONArray(list.toList()).toString())
        tmp.renameTo(f)
    }

    fun byId(id: String) = list.firstOrNull { it.optString("id") == id }

    /** Sign in, then the server's songs become a playlist named after it. */
    suspend fun add(kind: String, address: String, user: String, secret: String, folder: String): Playlist {
        val srv = Bridge.obj("server_add", kind, address, user, secret, folder)
        list.add(srv); save()
        return refresh(srv)
    }

    suspend fun refresh(srv: JSONObject): Playlist {
        val tracks = Bridge.tracks("server_songs", srv.toString())
        val origin = "server:" + srv.optString("id")
        val pl = Library.playlists.firstOrNull { it.origin == origin }
            ?: Library.newPlaylist(srv.optString("name", "My server"), emptyList()).also { it.origin = origin }
        pl.tracks.clear(); pl.tracks.addAll(tracks)
        Library.changed()
        return pl
    }

    fun remove(id: String) {
        list.removeAll { it.optString("id") == id }; save()
    }

    /** (url, headers) for one of a server's songs, or null when its server was removed. */
    suspend fun playable(t: Track): Pair<String, Map<String, String>>? {
        val srv = byId(t.pageUrl) ?: return null
        val o = Bridge.obj("server_playable", srv.toString(), t.toJson().toString())
        val h = o.optJSONObject("headers")
        return o.getString("url") to (h?.keys()?.asSequence()?.associateWith { h.getString(it) } ?: emptyMap())
    }
}
