package com.sevbify.app

import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import android.provider.MediaStore
import android.provider.OpenableColumns

/**
 * Songs already on the phone, from Android's music index. Only the folders you choose in Settings are used
 * (by default the Music folder, which is also where Sevbify saves downloads). Nothing else on the phone is read.
 */
object LocalMusic {
    fun scan(context: Context): List<Track> {
        val folders = Library.settings.musicFolders.map { it.trim('/').lowercase() + "/" }
        val out = ArrayList<Track>()
        val collection = if (Build.VERSION.SDK_INT >= 29) MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
                         else MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        val pathColumn = if (Build.VERSION.SDK_INT >= 29) MediaStore.Audio.Media.RELATIVE_PATH else MediaStore.Audio.Media.DATA
        val projection = arrayOf(MediaStore.Audio.Media._ID, MediaStore.Audio.Media.TITLE, MediaStore.Audio.Media.ARTIST,
                                 MediaStore.Audio.Media.ALBUM, MediaStore.Audio.Media.DURATION,
                                 MediaStore.Audio.Media.ALBUM_ID, pathColumn)
        try {
            context.contentResolver.query(collection, projection, "${MediaStore.Audio.Media.IS_MUSIC} != 0", null,
                                          "${MediaStore.Audio.Media.TITLE} COLLATE NOCASE")?.use { c ->
                val id = c.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
                val title = c.getColumnIndexOrThrow(MediaStore.Audio.Media.TITLE)
                val artist = c.getColumnIndexOrThrow(MediaStore.Audio.Media.ARTIST)
                val album = c.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM)
                val dur = c.getColumnIndexOrThrow(MediaStore.Audio.Media.DURATION)
                val albumId = c.getColumnIndexOrThrow(MediaStore.Audio.Media.ALBUM_ID)
                val path = c.getColumnIndexOrThrow(pathColumn)
                while (c.moveToNext()) {
                    val rel = (c.getString(path) ?: "").let {
                        if (Build.VERSION.SDK_INT >= 29) it else it.substringAfter("/0/", it)
                    }.lowercase()
                    if (folders.isNotEmpty() && folders.none { rel.startsWith(it) }) continue
                    val uri = ContentUris.withAppendedId(collection, c.getLong(id))
                    val art = ContentUris.withAppendedId(Uri.parse("content://media/external/audio/albumart"), c.getLong(albumId))
                    val a = c.getString(artist)?.takeUnless { it == "<unknown>" } ?: "Unknown Artist"
                    val t = c.getString(title) ?: "Unknown"
                    out.add(Track(title = t, artist = a, album = c.getString(album) ?: "", durationMs = c.getLong(dur),
                                  localUri = uri.toString(), localArt = art.toString(), source = "local",
                                  key = Track.matchKeyOf(a, t)))
                }
            }
        } catch (e: SecurityException) {
            // No permission yet: Your Songs stays empty until you allow it.
        }
        return out
    }

    /**
     * The media-index folder path for a folder the user picked in the file explorer (Settings ▸ Music folders ▸
     * Browse), e.g. a picked "Music/Sevbify" → "Music/Sevbify". Returns null if the pick isn't on this phone's
     * internal storage (an SD card or a cloud app → those go under "Folders from other apps" instead), or is the
     * whole-storage root (too broad). What's returned matches how scan() reads folders by name.
     */
    fun relativePathFromTree(uri: Uri): String? {
        val docId = try { DocumentsContract.getTreeDocumentId(uri) } catch (e: Exception) { return null }
        val parts = docId.split(":", limit = 2)
        if (parts.size != 2) return null
        if (!parts[0].equals("primary", ignoreCase = true)) return null   // only internal storage is indexed by path
        val path = parts[1].trim('/')
        return path.ifEmpty { null }
    }

    /**
     * A one-off playable song from a file you picked yourself in the phone's file explorer (Library ▸ + ▸
     * "Play a file…"). Reads the file's own tags for the title and artist, falling back to the file's name.
     * The file is played straight from its content:// link and is NOT added to Your Songs; nothing else on
     * the phone is read. Read access is kept (best-effort) so it can replay from Recently played later.
     */
    fun trackFromUri(context: Context, uri: Uri): Track {
        try {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (e: SecurityException) {
            // Only a temporary grant (common for Downloads/attachments): it still plays for now.
        }

        var displayName = ""
        try {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) displayName = c.getString(0) ?: ""
            }
        } catch (e: Exception) { /* some providers don't answer: fall back to tags/"Audio file" */ }

        var title = ""; var artist = ""; var album = ""; var durationMs = 0L
        val mmr = MediaMetadataRetriever()
        try {
            mmr.setDataSource(context, uri)
            title = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE).orEmpty()
            artist = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST).orEmpty()
            album = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM).orEmpty()
            durationMs = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
        } catch (e: Exception) {
            // Not tagged, or not decodable here: the player will still try the file, and the name is used below.
        } finally {
            try { mmr.release() } catch (e: Exception) {}
        }

        if (title.isBlank()) title = displayName.substringBeforeLast('.').ifBlank { "Audio file" }
        if (artist.isBlank()) artist = "Unknown Artist"
        return Track(title = title, artist = artist, album = album, durationMs = durationMs,
                     localUri = uri.toString(), source = "local", key = Track.matchKeyOf(artist, title))
    }
}
