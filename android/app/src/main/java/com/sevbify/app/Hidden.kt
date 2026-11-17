package com.sevbify.app

import androidx.compose.runtime.mutableStateListOf
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

/** Hide song / Don't play this artist, like the PC (core/hidden.py): skipped when music plays by itself (playlists,
 *  albums, radio, mixes, autoplay); a song you pick or queue yourself still plays. Kept on this phone, in the same
 *  shape as the PC's (so profiles carry them across). Settings → Hidden songs and artists lists them with a switch
 *  each. */
object Hidden {
    data class Entry(val kind: String, val key: String, val artist: String, val title: String, var on: Boolean)

    val entries = mutableStateListOf<Entry>()
    private const val MAX = 2000

    private fun norm(s: String): String =
        Regex("\\w+").findAll(Normalizer.normalize(s, Normalizer.Form.NFKC).lowercase()).joinToString(" ") { it.value }

    fun songKey(artist: String, title: String) = norm(artist) + "|" + norm(title)
    fun artistKey(artist: String) = norm(artist)

    fun isHidden(t: Track): Boolean {
        if (t.isItem) return false
        val artists = entries.filter { it.on && it.kind == "artist" }.map { it.key }.toSet()
        if (artists.isNotEmpty()) {
            if (artistKey(t.artist) in artists) return true
            val parts = t.artist.split(Regex(",|&| feat\\.? | ft\\.? | with | x ", RegexOption.IGNORE_CASE))
            if (parts.any { artistKey(it).isNotEmpty() && artistKey(it) in artists }) return true
        }
        val k = songKey(t.artist, t.title)
        return entries.any { it.on && it.kind == "song" && it.key == k }
    }

    fun songHidden(t: Track) = entries.any { it.on && it.kind == "song" && it.key == songKey(t.artist, t.title) }
    fun artistHidden(artist: String) = entries.any { it.on && it.kind == "artist" && it.key == artistKey(artist) }

    fun set(kind: String, artist: String, title: String, on: Boolean) {
        val key = if (kind == "song") songKey(artist, title) else artistKey(artist)
        if (key.trim('|').isEmpty()) return
        val i = entries.indexOfFirst { it.kind == kind && it.key == key }
        if (i >= 0) entries[i] = entries[i].copy(on = on)
        else if (on) {
            entries.add(Entry(kind, key, artist.take(200), title.take(300), true))
            while (entries.size > MAX) entries.removeAt(0)
        }
        Library.changed()
    }

    fun remove(e: Entry) { entries.removeAll { it.kind == e.kind && it.key == e.key }; Library.changed() }

    fun toJson(): JSONObject = JSONObject().apply {
        put("hidden_songs", JSONArray(entries.filter { it.kind == "song" }.map {
            JSONObject().put("key", it.key).put("artist", it.artist).put("title", it.title).put("on", it.on) }))
        put("hidden_artists", JSONArray(entries.filter { it.kind == "artist" }.map {
            JSONObject().put("key", it.key).put("artist", it.artist).put("on", it.on) }))
    }

    fun load(o: JSONObject?) {
        entries.clear()
        if (o == null) return
        for ((field, kind) in listOf("hidden_artists" to "artist", "hidden_songs" to "song")) {
            val a = o.optJSONArray(field) ?: continue
            for (i in 0 until minOf(a.length(), MAX)) {
                val e = a.optJSONObject(i) ?: continue
                val artist = e.optString("artist").take(200)
                val title = e.optString("title").take(300)
                val key = if (kind == "song") songKey(artist, title) else artistKey(artist)
                if (key.trim('|').isEmpty() || entries.any { it.kind == kind && it.key == key }) continue
                entries.add(Entry(kind, key, artist, title, e.optBoolean("on", true)))
            }
        }
    }
}
