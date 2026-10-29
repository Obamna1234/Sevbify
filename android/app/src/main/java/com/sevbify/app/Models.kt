package com.sevbify.app

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * A song. Either a file on the phone (localUri set) or a song you don't have yet (an online track that streams
 * in full while online and can be downloaded) - the same idea as the Windows app's "⬇" songs.
 */
data class Track(
    val title: String,
    val artist: String,
    val album: String = "",
    val durationMs: Long = 0,
    val coverUrl: String = "",
    val previewUrl: String = "",
    val streamUrl: String = "",
    val downloadUrl: String = "",
    val source: String = "",
    val sourceId: String = "",
    val pageUrl: String = "",
    val genre: String = "",
    val explicit: Boolean = false,
    val key: String = "",
    val localUri: String = "",
    val localArt: String = "",
) {
    val isLocal get() = localUri.isNotEmpty()
    /** Podcast episodes, audiobook chapters and YouTube episodes (they remember where you stopped). */
    val isItem get() = source == "podcast" || source == "audiobook" || source == "youtube"
    val itemKey get() = if (isItem) "$source:$sourceId" else ""
    val matchKey get() = key.ifEmpty { matchKeyOf(artist, title) }
    val art get() = localArt.ifEmpty { coverUrl }

    fun toJson(): JSONObject = JSONObject().apply {
        put("title", title); put("artist", artist); put("album", album); put("duration_ms", durationMs)
        put("cover_url", coverUrl); put("preview_url", previewUrl); put("stream_url", streamUrl)
        put("download_url", downloadUrl); put("source", source); put("source_id", sourceId)
        put("page_url", pageUrl); put("genre", genre); put("explicit", explicit); put("key", key)
        if (localUri.isNotEmpty()) put("local_uri", localUri)
        if (localArt.isNotEmpty()) put("local_art", localArt)
    }

    companion object {
        fun fromJson(o: JSONObject) = Track(
            title = o.optString("title"), artist = o.optString("artist"), album = o.optString("album"),
            durationMs = o.optLong("duration_ms"), coverUrl = o.optString("cover_url"),
            previewUrl = o.optString("preview_url"), streamUrl = o.optString("stream_url"),
            downloadUrl = o.optString("download_url"), source = o.optString("source"),
            sourceId = o.optString("source_id"), pageUrl = o.optString("page_url"), genre = o.optString("genre"),
            explicit = o.optBoolean("explicit"), key = o.optString("key"),
            localUri = o.optString("local_uri"), localArt = o.optString("local_art"),
        )

        /** Same idea as core/online/models.match_key: first artist + title, lower-case, without versions. */
        fun matchKeyOf(artist: String, title: String): String {
            fun norm(t: String) = t.lowercase()
                .replace(Regex("""\s*[\(\[](feat|ft|with|remaster|live|radio edit|official)[^)\]]*[\)\]]"""), "")
                .replace(Regex("""\s+-\s+(remaster|live|radio edit).*$"""), "")
                .replace("&", " and ").replace(Regex("""[^\p{L}\p{N}\s]"""), " ")
                .replace(Regex("""^the\s+"""), "").replace(Regex("""\s+"""), " ").trim()
            val first = artist.split(Regex("""\s*(,|;| x | feat\.? | ft\.? |&)\s*"""), 2).first()
            return "${norm(first)}|${norm(title)}"
        }
    }
}

fun JSONArray.tracks(): List<Track> = (0 until length()).map { Track.fromJson(getJSONObject(it)) }
fun List<Track>.toJsonArray(): JSONArray = JSONArray().also { a -> forEach { a.put(it.toJson()) } }

data class Playlist(
    val id: String = UUID.randomUUID().toString(),
    var name: String,
    val tracks: MutableList<Track> = mutableListOf(),
    var folder: String = "",
    var coverUrl: String = "",
    var created: Long = System.currentTimeMillis(),
    var lastPlayed: Long = 0,
    var pinned: Boolean = false,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("id", id); put("name", name); put("tracks", tracks.toJsonArray()); put("folder", folder)
        put("cover_url", coverUrl); put("created", created); put("last_played", lastPlayed); put("pinned", pinned)
    }

    companion object {
        fun fromJson(o: JSONObject) = Playlist(
            id = o.optString("id").ifEmpty { UUID.randomUUID().toString() }, name = o.optString("name"),
            tracks = (o.optJSONArray("tracks") ?: JSONArray()).tracks().toMutableList(),
            folder = o.optString("folder"), coverUrl = o.optString("cover_url"), created = o.optLong("created"),
            lastPlayed = o.optLong("last_played"), pinned = o.optBoolean("pinned"),
        )
    }
}

/** A podcast, YouTube channel (video podcast) or audiobook, as the shared core describes it. */
data class Show(val json: JSONObject) {
    val key get() = json.optString("key")
    val title get() = json.optString("title")
    val author get() = json.optString("author")
    val image get() = json.optString("image_url").ifEmpty { json.optString("cover_url") }
    val description get() = json.optString("description")
    val isYoutube get() = json.optString("kind") == "youtube"
    val isBook get() = json.has("identifier")
}

data class Episode(val track: Track, val published: Double, val date: String, val description: String)
