package com.sevbify.app.ui

import com.sevbify.app.tr
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.sevbify.app.Library
import kotlinx.coroutines.launch

/** Spotify only shares 100 songs of a playlist without signing in. Chosic's free exporter (in the browser) gets
 *  all of them as a .csv; Sevbify copies the link for you, then adds the downloaded file to the same playlist. */
@Composable
fun ChosicDialog(playlistId: String, link: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var opened by remember { mutableStateOf(false) }
    val pl = Library.playlists.firstOrNull { it.id == playlistId } ?: run { Nav.chosicFor = null; return }
    val picker = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            try {
                val (_, tracks) = readPlaylistFile(context, uri)
                if (tracks.size <= pl.tracks.size) { Nav.say("That file has no more songs than “${pl.name}”"); return@launch }
                pl.tracks.clear(); pl.tracks.addAll(tracks)
                Library.changed()
                Nav.chosicFor = null
                Nav.say("“${pl.name}” now has all ${tracks.size} songs")
                com.sevbify.app.ImportCheck.start(pl)
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Nav.say("⚠ Couldn't read that file: ${e.message}")
            }
        }
    }
    AlertDialog(
        onDismissRequest = { Nav.chosicFor = null },
        title = { Text(if (opened) "Add the file from Chosic" else "Spotify only shared ${pl.tracks.size} songs") },
        text = {
            Text(if (opened) "In Chosic, paste the link (it's copied), press Export and download the CSV. Then come back " +
                             "and pick the downloaded file: it's added to “${pl.name}”."
                 else "Get all of “${pl.name}” with Chosic's free Spotify Playlist Exporter. It opens in your browser " +
                      "with the link copied; Sevbify then adds the file it downloads to this playlist.")
        },
        confirmButton = {
            TextButton(onClick = {
                if (!opened) {
                    val cm = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                    cm.setPrimaryClip(android.content.ClipData.newPlainText("Spotify playlist", link))
                    try {
                        context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW,
                            android.net.Uri.parse("https://www.chosic.com/spotify-playlist-exporter/"))
                            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
                    } catch (_: Exception) {}
                    opened = true
                } else picker.launch(arrayOf("*/*"))
            }) { Text(if (opened) tr("Choose a file") else "Open Chosic", color = C.Green) }
        },
        dismissButton = {
            TextButton(onClick = { Nav.chosicFor = null }) {
                Text(if (opened) tr("Cancel") else "Keep the first ${pl.tracks.size}", color = C.Text)
            }
        },
        containerColor = C.Elevated,
    )
}
