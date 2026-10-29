package com.sevbify.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.Player
import kotlinx.coroutines.launch

/** Settings: the phone versions of the Windows app's (online & privacy, playback, downloads, music folders). */
@Composable
fun SettingsScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    val s = Library.settings
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var update by remember { mutableStateOf("") }
    LazyColumn {
        item {
            Row(Modifier.statusBarsPadding(), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Text("Settings", style = MaterialTheme.typography.headlineMedium)
            }
        }
        item { Heading("Online and privacy") }
        item {
            Toggle("Online", "Search, radio, streaming, podcasts and downloads. Off: Sevbify contacts nothing; your own " +
                   "and downloaded music still plays.", s.online) {
                s.online = it; Library.changed(); scope.launch { try { Bridge.call("set_online", it) } catch (_: Exception) {} }
            }
        }
        item {
            Toggle("Play full songs you don't have yet", "Stream in full from Bandcamp, then YouTube. Off: 30-second previews.",
                   s.streamFull) { s.streamFull = it; Library.changed() }
        }
        item { Toggle("Allow explicit content", "", s.explicitOk) { s.explicitOk = it; Library.changed() } }
        item {
            Toggle("Private session", "What you play isn't added to Recently played and podcast positions aren't saved, " +
                   "until you turn it off or close Sevbify.", Library.privateSession) { Library.privateSession = it }
        }
        item {
            Muted("No account, no ads, no tracking, nothing sold. Online, Sevbify only contacts what each feature needs: " +
                  "Deezer (search, radio, genres), Wikipedia (artist info), Apple (podcast directory), the podcasts' own " +
                  "feeds, the Internet Archive (audiobooks), Bandcamp and YouTube (full songs, downloads), Spotify or Apple " +
                  "Music only when you import a link, and GitHub for update checks.")
        }
        item { Heading("Playback") }
        item { Toggle("Autoplay", "When your music ends, keep playing similar songs.", s.autoplay) { s.autoplay = it; Library.changed() } }
        item { Heading("Downloads") }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text("Download and stream from", style = MaterialTheme.typography.bodyLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    listOf("Bandcamp + YouTube", "Bandcamp only", "YouTube only").forEach { o ->
                        Chip(o, s.source == o) {
                            s.source = o; Library.changed(); scope.launch { try { Bridge.call("set_source", o) } catch (_: Exception) {} }
                        }
                    }
                }
            }
        }
        item {
            Muted("Songs are saved in your phone's Music folder under Sevbify/<Artist>, so other apps and your PC see them. " +
                  "Podcast episodes and audiobook chapters stay inside Sevbify.")
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp)) { OutlinedButton(onClick = { Nav.go(Screen.Downloads) }) { Text("Downloads", color = C.Text) } }
        }
        item { Heading("Your music") }
        item {
            var folders by remember { mutableStateOf(s.musicFolders.joinToString(", ")) }
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text("Music folders", style = MaterialTheme.typography.bodyLarge)
                Text("Folders on the phone Sevbify plays music from (separate with commas). Only these are read.",
                     style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(folders, { folders = it }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
                OutlinedButton(onClick = {
                    s.musicFolders = folders.split(",").map { it.trim() }.filter { it.isNotEmpty() }.toMutableList()
                    Library.changed()
                    (context as? com.sevbify.app.MainActivity)?.rescan()
                    Nav.say("Music folders saved")
                }, modifier = Modifier.padding(top = 6.dp)) { Text("Save", color = C.Text) }
            }
        }
        item { Heading("About and updates") }
        item {
            Muted("Sevbify ${Library.coreVersion} for Android. Built with AI help. Not affiliated with Spotify, YouTube, " +
                  "Bandcamp, Apple, Deezer or Sevby LLC.")
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = {
                    scope.launch {
                        update = try { Bridge.obj("check_updates", Library.coreVersion).optString("message") }
                                 catch (e: Exception) { "Couldn't check: ${e.message}" }
                    }
                }) { Text("Check for updates", color = C.Text) }
                Spacer(Modifier.width(12.dp))
                Text(update, style = MaterialTheme.typography.bodySmall)
            }
        }
        item { Gap(32.dp) }
    }
}

@Composable
private fun Heading(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(start = 16.dp, top = 20.dp, bottom = 4.dp))
}

@Composable
private fun Toggle(name: String, desc: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { onChange(!value) }.padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(name, style = MaterialTheme.typography.bodyLarge)
            if (desc.isNotEmpty()) Text(desc, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.width(12.dp))
        Switch(value, onChange, colors = SwitchDefaults.colors(checkedThumbColor = C.Text, checkedTrackColor = C.Green))
    }
}
