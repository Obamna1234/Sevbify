package com.sevbify.app

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore

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
}
