package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.tracks
import kotlinx.coroutines.launch

/** Import a playlist: a Spotify / Apple Music link, plus (for over 100 songs) songs copied in Spotify. */
@Composable
fun ImportScreen(start: String) {
    val isSongs = start.contains("/track/")
    var link by remember { mutableStateOf(if (isSongs) "" else start) }
    var songs by remember { mutableStateOf(if (isSongs) start else "") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.statusBarsPadding().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
            Text(tr("Import a playlist"), style = MaterialTheme.typography.headlineMedium)
        }
        Muted(tr("Paste a public Spotify, Apple Music, Deezer or Jamendo playlist or album link (or Share it from Spotify to Sevbify). Same ") +
              "order and cover; songs already on your phone play from your files, the rest stream while online and wait " +
              "under To download. Your Spotify account is never signed in to.")
        OutlinedTextField(link, { link = it }, singleLine = true, placeholder = { Text(tr("https://open.spotify.com/playlist/…")) },
                          modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        if ("jamendo.com" in link.lowercase()) {
            var jid by remember { mutableStateOf(Library.settings.jamendoId) }
            Muted(tr("Jamendo needs a free client ID (make one at devportal.jamendo.com). It's kept on this phone only."))
            OutlinedTextField(jid, { jid = it.trim(); Library.settings.jamendoId = jid; Library.changed() }, singleLine = true,
                              placeholder = { Text(tr("Jamendo client ID")) },
                              modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        }
        Muted(tr("More than 100 songs? Without signing in, Spotify only shares 100 songs per link. In Spotify on a computer, ") +
              "click a song in the playlist, press Ctrl+A then Ctrl+C, and paste the links here.")
        OutlinedTextField(songs, { songs = it }, placeholder = { Text(tr("https://open.spotify.com/track/…")) },
                          modifier = Modifier.fillMaxWidth().height(120.dp).padding(horizontal = 16.dp))
        Button(onClick = {
            busy = true
            scope.launch {
                try {
                    val o = Bridge.obj("import_link", link, songs, Library.settings.jamendoId)
                    val tracks = o.getJSONArray("tracks").tracks()
                    val pl = Library.newPlaylist(o.optString("name", "Imported playlist"), tracks)
                    pl.coverUrl = o.optString("cover_url")
                    pl.origin = o.optString("origin", "spotify")
                    Library.changed()
                    Nav.back()
                    Nav.go(Screen.PlaylistPage(pl.id))
                    Nav.say("Imported “${pl.name}”: ${tracks.size} songs" +
                            if (o.optBoolean("truncated")) " (Spotify shares 100 per link: paste the copied songs for the rest)" else "")
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
                    Nav.say("⚠ Couldn't import: ${e.message}")
                } finally { busy = false }
            }
        }, enabled = !busy && (link.isNotBlank() || songs.isNotBlank()), modifier = Modifier.padding(16.dp),
           colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = C.Black)) {
            Text(if (busy) "Importing…" else "Import")
        }
        // Or a file: Exportify / TuneMyMusic / Soundiiz .csv, a .txt list ("Artist - Title" per line), .m3u / .m3u8.
        Text(tr("Or import a file"), style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(start = 16.dp, top = 8.dp))
        Muted("A .csv from Exportify, TuneMyMusic or Soundiiz (any number of songs), a .txt with one \"Artist - Title\" " +
              "per line, or an .m3u / .m3u8 playlist.")
        val context = androidx.compose.ui.platform.LocalContext.current
        val picker = androidx.activity.compose.rememberLauncherForActivityResult(
            androidx.activity.result.contract.ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) {
                busy = true
                scope.launch {
                    try {
                        val (fileName, tracks) = readPlaylistFile(context, uri)
                        // Name it (the file's name is filled in), then every song is checked for typos.
                        askName(fileName, tr("Playlist name"), tr("Import")) { name ->
                            val pl = Library.newPlaylist(name.ifBlank { fileName }, tracks)
                            pl.origin = "file"
                            Library.changed()
                            Nav.back()
                            Nav.go(Screen.PlaylistPage(pl.id))
                            Nav.say("Imported “${pl.name}”: ${pl.tracks.size} songs. Checking them…")
                            com.sevbify.app.ImportCheck.start(pl)
                        }
                    } catch (e: Exception) {
                        if (e is kotlinx.coroutines.CancellationException) throw e
                        Nav.say("⚠ Couldn't import: ${e.message}")
                    } finally { busy = false }
                }
            }
        }
        androidx.compose.material3.OutlinedButton(onClick = { picker.launch(arrayOf("*/*")) }, enabled = !busy,
                                                  modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Text(tr("Choose a file"), color = C.Text)
        }
    }
}

/** A playlist file picked in Android's file picker: copied to the app's cache under its own name (Python reads
 *  paths, and the file name becomes the playlist's name), read by the shared core, then removed.
 *  Returns (the file's name, its songs). */
suspend fun readPlaylistFile(context: android.content.Context, uri: android.net.Uri): Pair<String, List<com.sevbify.app.Track>> {
    var name = "Imported playlist.txt"
    context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
        if (c.moveToFirst()) c.getString(0)?.let { n -> name = n.replace(Regex("[\\\\/:*?\"<>|]"), "_").take(120) }
    }
    val ext = name.substringAfterLast('.', "").lowercase()
    if (ext !in listOf("txt", "csv", "m3u", "m3u8", "tsv"))
        throw com.sevbify.app.CoreError("choose a .txt, .csv or .m3u file")
    val dir = java.io.File(context.cacheDir, "import").apply { mkdirs() }
    val file = java.io.File(dir, name)
    try {
        context.contentResolver.openInputStream(uri)?.use { input ->
            file.outputStream().use { out ->
                val buf = ByteArray(64 * 1024); var total = 0L
                while (true) {
                    val n = input.read(buf); if (n < 0) break
                    total += n
                    if (total > 10L * 1024 * 1024) throw com.sevbify.app.CoreError("that file is too big for a playlist")
                    out.write(buf, 0, n)
                }
            }
        } ?: throw com.sevbify.app.CoreError("couldn't open the file")
        val o = Bridge.obj("import_file", file.path)
        val items = o.optJSONArray("items") ?: org.json.JSONArray()
        val tracks = (0 until items.length()).mapNotNull { i ->
            val it = items.getJSONObject(i)
            it.optJSONObject("track")?.let { t -> com.sevbify.app.Track.fromJson(t) }
        }
        if (tracks.isEmpty()) throw com.sevbify.app.CoreError("no songs found in that file")
        return o.optString("name").ifEmpty { name.substringBeforeLast('.') } to tracks
    } finally { file.delete() }
}
