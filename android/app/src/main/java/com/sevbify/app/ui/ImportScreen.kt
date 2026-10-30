package com.sevbify.app.ui

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
            Text("Import a playlist", style = MaterialTheme.typography.headlineMedium)
        }
        Muted("Paste a public Spotify, Apple Music, Deezer or Jamendo playlist or album link (or Share it from Spotify to Sevbify). Same " +
              "order and cover; songs already on your phone play from your files, the rest stream while online and wait " +
              "under To download. Your Spotify account is never signed in to.")
        OutlinedTextField(link, { link = it }, singleLine = true, placeholder = { Text("https://open.spotify.com/playlist/…") },
                          modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        if ("jamendo.com" in link.lowercase()) {
            var jid by remember { mutableStateOf(Library.settings.jamendoId) }
            Muted("Jamendo needs a free client ID (make one at devportal.jamendo.com). It's kept on this phone only.")
            OutlinedTextField(jid, { jid = it.trim(); Library.settings.jamendoId = jid; Library.changed() }, singleLine = true,
                              placeholder = { Text("Jamendo client ID") },
                              modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        }
        Muted("More than 100 songs? Without signing in, Spotify only shares 100 songs per link. In Spotify on a computer, " +
              "click a song in the playlist, press Ctrl+A then Ctrl+C, and paste the links here.")
        OutlinedTextField(songs, { songs = it }, placeholder = { Text("https://open.spotify.com/track/…") },
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
    }
}
