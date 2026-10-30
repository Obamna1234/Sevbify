package com.sevbify.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
    // Your Sevbify profile: Export / Import through Android's own file picker (any folder, Drive, a USB stick...).
    val exporter = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        if (uri != null) scope.launch {
            try { val n = com.sevbify.app.Profile.exportTo(context, uri); Nav.say("Profile saved (${n / 1024 + 1} KB)") }
            catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e; Nav.say("⚠ Couldn't save: ${e.message}") }
        }
    }
    val importer = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            try { Nav.say(com.sevbify.app.Profile.importFrom(context, uri)) }
            catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e; Nav.say("⚠ ${e.message}") }
        }
    }
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
        item { Toggle("Allow explicit content", "", s.explicitOk) { s.explicitOk = it; Library.changed() } }
        item {
            Toggle("Private session", "What you play isn't added to Recently played and podcast positions aren't saved, " +
                   "until you turn it off or close Sevbify.", Library.privateSession) { Library.privateSession = it }
        }
        item {
            Muted("No account, no ads, no tracking, nothing sold. Online, Sevbify only contacts what each feature needs: " +
                  "Deezer (search, radio, genres), Wikipedia (artist info), DuckDuckGo (only a finished search whose results look wrong, for “Did you mean”), Apple (podcast directory), the podcasts' own " +
                  "feeds, the Internet Archive (audiobooks), Bandcamp and YouTube (full songs, downloads), Spotify or Apple " +
                  "Music only when you import a link, LRCLIB for lyrics, song.link when you share a song, SponsorBlock for YouTube episodes, and GitHub for updates.")
        }
        item { Heading("Playback") }
        item { Toggle("Autoplay", "When your music ends, keep playing similar songs.", s.autoplay) { s.autoplay = it; Library.changed() } }
        item {
            Toggle("Lyrics", "Show lyrics under Now playing: from a .lrc file next to your song, or from LRCLIB (a free lyrics " +
                   "database; only the song's name and length are sent).", s.lyrics) { s.lyrics = it; Library.changed() }
        }
        item {
            Toggle("Skip sponsor segments in YouTube episodes", "Jumps over ad reads, \"like and subscribe\" reminders " +
                   "and self-promotion that viewers marked on SponsorBlock. Private: the episode isn't named, only a " +
                   "4-character code shared by many videos is sent. YouTube's own ads never play in Sevbify.",
                   s.skipSponsors) { s.skipSponsors = it; Library.changed() }
        }
        item { Heading("Your Library") }
        item {
            Toggle("Show where playlists came from", "A coloured border around playlist pictures: grey = made in Sevbify, " +
                   "green = Spotify link, white = Apple Music link, purple = Deezer link, orange = Jamendo link, " +
                   "blue = imported from a file.",
                   s.showPlaylistOrigin) { s.showPlaylistOrigin = it; Library.changed() }
        }
        item { Heading("Your Sevbify profile") }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text("One small file with your playlists, folders, podcasts, audiobooks, where you stopped, recently " +
                     "played, recent searches and settings. Open it in Sevbify on any device: Android, iPhone, " +
                     "Windows, Mac or Linux. It stays where you save it; Sevbify never uploads it.",
                     style = MaterialTheme.typography.bodySmall)
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { exporter.launch(com.sevbify.app.Profile.FILE_NAME) }) { Text("Export", color = C.Text) }
                    OutlinedButton(onClick = { importer.launch(arrayOf("*/*")) }) { Text("Import", color = C.Text) }
                }
            }
        }
        item {
            Toggle("Keep a copy in Downloads", "Saves your profile to Download/Sevbify whenever you leave Sevbify, so " +
                   "it's still there if the app is uninstalled (then: Import, and pick it). Only on this phone.",
                   s.profileBackup) { s.profileBackup = it; Library.changed() }
        }
        item { Heading("Downloads") }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text("Download and stream from", style = MaterialTheme.typography.bodyLarge)
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("Bandcamp + YouTube", "Bandcamp only", "YouTube only").forEach { o ->
                        Chip(o, s.source == o) {
                            s.source = o; Library.changed(); scope.launch { try { Bridge.call("set_source", o) } catch (_: Exception) {} }
                        }
                    }
                }
            }
        }
        item {
            Choice("Download quality",
                   if (s.songQuality == "small") "Data saver: a lower-bitrate original, about half the size. Slightly less " +
                       "detail with good headphones."
                   else "Best: the original audio with nothing lost (.m4a). A song can't be better than its source " +
                       "(YouTube ~128-160 kbps, Bandcamp 128 kbps), so this is also the smallest full-quality file. " +
                       "Plays in Samsung Music, VLC and on your PC.",
                   listOf("best" to "Best quality", "small" to "Data saver"), s.songQuality) { s.songQuality = it; Library.changed() }
        }
        item {
            Choice("Audiobook quality", "LibriVox records every chapter at both; speech sounds the same at 64 kbps.",
                   listOf("standard" to "Standard (64 kbps)", "high" to "High (128 kbps)"), s.bookQuality) {
                s.bookQuality = it; Library.changed()
            }
        }
        item {
            Choice("Video podcast quality", "When watching. Higher uses more data; the best YouTube has up to your choice is used.",
                   listOf("auto" to "Auto", "360" to "360p", "480" to "480p", "720" to "720p", "1080" to "1080p"), s.videoQuality) {
                s.videoQuality = it; Library.changed()
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
        item {
            Toggle("Keep yt-dlp up to date", "yt-dlp is what finds and downloads songs on YouTube; YouTube changes often. " +
                   "Once a week, when online, the newest official release is fetched and checked against its published " +
                   "checksum. Used from the next start.", s.autoUpdateYtdlp) { s.autoUpdateYtdlp = it; Library.changed() }
        }
        item {
            var ytdlp by remember { mutableStateOf("") }
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = {
                    ytdlp = "Checking…"
                    scope.launch {
                        ytdlp = try { Bridge.obj("update_ytdlp").optString("message") } catch (e: Exception) { "Couldn't update: ${e.message}" }
                    }
                }) { Text("Update yt-dlp now", color = C.Text) }
                Spacer(Modifier.width(12.dp))
                Text(ytdlp, style = MaterialTheme.typography.bodySmall)
            }
        }
        item { Gap(32.dp) }
    }
}

@Composable
private fun Choice(name: String, desc: String, options: List<Pair<String, String>>, value: String, onPick: (String) -> Unit) {
    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text(name, style = MaterialTheme.typography.bodyLarge)
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { (key, label) -> Chip(label, value == key) { onPick(key) } }
        }
        if (desc.isNotEmpty()) Text(desc, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
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
