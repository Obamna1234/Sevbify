package com.sevbify.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.DocumentsContract

/**
 * Folders you pick in Android's own file picker: an SD card, or a cloud app that offers folders there
 * (Nextcloud, OneDrive, Dropbox, Proton Drive...). Sevbify only gets read access to the folders you pick; your
 * sign-in stays inside that app, and the songs come straight from it (cloud songs need the internet unless that app
 * keeps them offline). Names come from the files ("Artist - Title", or Artist / Album / Title folders), so nothing
 * has to be downloaded just to list them.
 */
object CloudFolders {
    private val AUDIO = setOf("mp3", "m4a", "aac", "flac", "ogg", "opus", "wav", "wma", "alac", "aiff", "aif")
    private const val MAX_FILES = 10_000

    fun add(context: Context, tree: Uri): Boolean {
        return try {
            context.contentResolver.takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            val s = Library.settings
            if (tree.toString() !in s.cloudFolders) s.cloudFolders.add(tree.toString())
            Library.changed()
            true
        } catch (_: SecurityException) { false }
    }

    fun remove(context: Context, tree: String) {
        try {
            context.contentResolver.releasePersistableUriPermission(Uri.parse(tree), Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: Exception) {}
        Library.settings.cloudFolders.remove(tree)
        Library.changed()
    }

    fun name(context: Context, tree: String): String = try {
        val uri = Uri.parse(tree)
        val doc = DocumentsContract.buildDocumentUriUsingTree(uri, DocumentsContract.getTreeDocumentId(uri))
        context.contentResolver.query(doc, arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) it.getString(0) else null
        } ?: tree
    } catch (_: Exception) { "Folder (no longer available)" }

    fun scan(context: Context): List<Track> {
        val out = ArrayList<Track>()
        for (tree in Library.settings.cloudFolders.toList()) {
            try {
                val uri = Uri.parse(tree)
                walk(context, uri, DocumentsContract.getTreeDocumentId(uri), emptyList(), out, 0)
            } catch (_: Exception) { /* the app or card is gone for now: try again next time */ }
        }
        return out
    }

    private fun walk(context: Context, tree: Uri, docId: String, parents: List<String>, out: MutableList<Track>, depth: Int) {
        if (depth > 8 || out.size >= MAX_FILES) return
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, docId)
        val cols = arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                           DocumentsContract.Document.COLUMN_MIME_TYPE)
        val dirs = ArrayList<Pair<String, String>>()
        context.contentResolver.query(children, cols, null, null, null)?.use { c ->
            while (c.moveToNext() && out.size < MAX_FILES) {
                val id = c.getString(0) ?: continue
                val name = c.getString(1) ?: continue
                val mime = c.getString(2) ?: ""
                if (mime == DocumentsContract.Document.MIME_TYPE_DIR) { dirs.add(id to name); continue }
                val ext = name.substringAfterLast('.', "").lowercase()
                if (ext !in AUDIO && !mime.startsWith("audio/")) continue
                val (artist, title) = guess(name.substringBeforeLast('.'), parents)
                val file = DocumentsContract.buildDocumentUriUsingTree(tree, id)
                out.add(Track(title = title, artist = artist, album = if (parents.size >= 2) parents.last() else "",
                              localUri = file.toString(), source = "local", key = Track.matchKeyOf(artist, title)))
            }
        }
        for ((id, name) in dirs) walk(context, tree, id, parents + name, out, depth + 1)
    }

    /** "01 - Artist - Title", "Artist - Title", or Artist/Album/"03 Title". */
    private fun guess(base: String, parents: List<String>): Pair<String, String> {
        val clean = base.replace(Regex("""^\s*\d{1,3}\s*[-._)]?\s*"""), "").trim()
        val cut = clean.indexOf(" - ")
        if (cut > 0) return clean.substring(0, cut).trim() to clean.substring(cut + 3).trim()
        val artist = when {
            parents.size >= 2 -> parents[parents.size - 2]
            parents.size == 1 -> parents[0]
            else -> "Unknown Artist"
        }
        return artist to clean.ifEmpty { base }
    }
}
