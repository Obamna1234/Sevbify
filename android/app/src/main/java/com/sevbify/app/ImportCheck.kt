package com.sevbify.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.sevbify.app.ui.Nav
import kotlinx.coroutines.launch
import org.json.JSONArray

/** After a playlist file is imported: every song is looked up once (shared core: core/import_check.py). Found
 *  songs get their cover, album and length; ones that can't be found as written come back with the closest song,
 *  and Sevbify asks "Did you mean …?" so a typo doesn't stop them streaming or downloading. */
object ImportCheck {
    data class Problem(val index: Int, val written: String, val suggestion: String)

    var checking by mutableStateOf("")               // the playlist being checked ("" = none)
    var done by mutableIntStateOf(0)
    var total by mutableIntStateOf(0)
    var review by mutableStateOf<Pair<Playlist, List<Problem>>?>(null)

    fun asText(t: Track) = if (t.artist.isNotEmpty()) "${t.artist} - ${t.title}" else t.title

    fun start(pl: Playlist) {
        if (!Library.settings.online) return
        val todo = pl.tracks.indices.filter { !pl.tracks[it].isLocal && Library.localFor(pl.tracks[it]) == null }
        if (todo.isEmpty()) return
        checking = pl.name; done = 0; total = todo.size
        SevbifyApp.instance.scope.launch {
            val problems = mutableListOf<Problem>()
            try {
                for (chunk in todo.chunked(8)) {
                    val sent = chunk.map { pl.tracks[it] }
                    val arr = Bridge.arr("check_import", JSONArray(sent.map { it.toJson() }).toString())
                    for (k in chunk.indices) {
                        val i = chunk[k]
                        val r = arr.getJSONObject(k)
                        if (i >= pl.tracks.size || pl.tracks[i] != sent[k]) continue      // edited meanwhile
                        if (r.optString("status") == "ok") {
                            val found = Track.fromJson(r.getJSONObject("track"))
                            val t = pl.tracks[i]
                            pl.tracks[i] = t.copy(album = t.album.ifEmpty { found.album },
                                                  coverUrl = t.coverUrl.ifEmpty { found.coverUrl },
                                                  durationMs = if (t.durationMs > 0) t.durationMs else found.durationMs,
                                                  previewUrl = t.previewUrl.ifEmpty { found.previewUrl })
                        } else {
                            problems.add(Problem(i, asText(sent[k]), r.optString("suggestion")))
                        }
                    }
                    done += chunk.size
                    Library.changed()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Nav.say("⚠ Couldn't check the songs: ${e.message}")
                checking = ""
                return@launch
            }
            checking = ""
            if (problems.isEmpty()) Nav.say("All ${todo.size} songs in “${pl.name}” were found")
            else review = pl to problems
        }
    }

    /** The ticked songs, renamed as typed ("Artist - Title"). */
    fun apply(pl: Playlist, fixes: Map<Int, String>) {
        for ((i, text) in fixes) {
            if (i !in pl.tracks.indices) continue
            val cut = text.indexOf(" - ")
            val (artist, title) = if (cut > 0) text.substring(0, cut).trim() to text.substring(cut + 3).trim() else "" to text.trim()
            if (title.isNotEmpty()) pl.tracks[i] = Track(title = title, artist = artist)
        }
        Library.changed()
        review = null
        if (fixes.isNotEmpty()) Nav.say("Fixed ${fixes.size} song${if (fixes.size == 1) "" else "s"}")
    }
}
