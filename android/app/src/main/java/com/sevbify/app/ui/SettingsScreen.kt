package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CloudDownload
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.PlayCircleOutline
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

/** Settings like Spotify's on Android: two quick switches on top, then one page per category instead of one
 *  long list. Only what Sevbify actually has is shown. */
@Composable
fun SettingsScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    val s = Library.settings
    LazyColumn {
        item {
            Row(Modifier.statusBarsPadding(), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Text(tr("Settings"), style = MaterialTheme.typography.headlineMedium)
            }
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                QuickTile(tr("Data saver"), "Smaller downloads, lower video quality", dataSaverOn(), Modifier.weight(1f)) { setDataSaver(it) }
                QuickTile(tr("Private session"), "Nothing added to Recently played", Library.privateSession, Modifier.weight(1f)) {
                    Library.privateSession = it; Library.changed(save = false)
                }
            }
        }
        val pages = listOf(
            Triple("content", Icons.Filled.Palette, "Content and display" to "Explicit content, playlist borders, language"),
            Triple("privacy", Icons.Filled.Lock, "Privacy and profile" to "Online, private session, your Sevbify profile"),
            Triple("playback", Icons.Filled.PlayCircleOutline, "Playback" to "Autoplay, lyrics, sponsor skipping"),
            Triple("offline", Icons.Filled.CloudDownload, "Data-saving and offline" to "Where songs come from, downloads, music folders"),
            Triple("quality", Icons.Filled.GraphicEq, "Media quality" to "Song, audiobook and video quality"),
            Triple("car", Icons.Filled.DirectionsCar, "Car" to "Android Auto, Bluetooth"),
            Triple("about", Icons.Filled.Info, "About and updates" to "Version, updates, yt-dlp"),
        )
        items(pages.size) { i ->
            val (key, icon, text) = pages[i]
            Row(Modifier.fillMaxWidth().clickable { Nav.go(Screen.SettingsPage(key)) }.padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = C.Text, modifier = Modifier.size(26.dp))
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    Text(tr(text.first), style = MaterialTheme.typography.bodyLarge)
                    Text(tr(text.second), style = MaterialTheme.typography.bodySmall, maxLines = 1)
                }
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = C.Sub)
            }
        }
        item { Gap(32.dp) }
    }
}

/** Data saver: the smaller download quality and 360p video. */
private fun dataSaverOn() = Library.settings.songQuality == "small"
private fun setDataSaver(on: Boolean) {
    val s = Library.settings
    s.songQuality = if (on) "small" else "best"
    s.videoQuality = if (on) "360" else "auto"
    if (on) s.bookQuality = "standard"
    Library.changed()
}

@Composable
private fun QuickTile(name: String, desc: String, on: Boolean, modifier: Modifier, onChange: (Boolean) -> Unit) {
    Column(modifier.clip(RoundedCornerShape(8.dp)).background(if (on) C.Green.copy(alpha = 0.18f) else C.Elevated)
               .clickable { onChange(!on) }.padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(name, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
            Switch(on, onChange, colors = SwitchDefaults.colors(checkedThumbColor = C.Text, checkedTrackColor = C.Green))
        }
        Text(tr(desc), style = MaterialTheme.typography.bodySmall, maxLines = 2)
    }
}

/** One Settings category. */
@Composable
fun SettingsPageScreen(key: String) {
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
    val title = mapOf("content" to "Content and display", "privacy" to "Privacy and profile", "playback" to "Playback",
                      "offline" to "Data-saving and offline", "quality" to "Media quality", "car" to "Car",
                      "about" to "About and updates")[key] ?: "Settings"
    LazyColumn {
        item {
            Row(Modifier.statusBarsPadding(), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Text(tr(title), style = MaterialTheme.typography.headlineSmall)
            }
        }
        when (key) {
        "content" -> {
        item { Toggle(tr("Allow explicit content"), "When off, songs marked explicit are left out of search and radios.", s.explicitOk) {
            s.explicitOk = it; Library.changed() } }
        item {
            Toggle(tr("Show where playlists came from"), "A coloured border around playlist pictures: grey = made in Sevbify, " +
                   "green = Spotify link, white = Apple Music link, purple = Deezer link, orange = Jamendo link, " +
                   "blue = imported from a file.",
                   s.showPlaylistOrigin) { s.showPlaylistOrigin = it; Library.changed() }
        }
        item {
            Column(Modifier.fillMaxWidth().clickable { openAppLanguage(context) }.padding(horizontal = 16.dp, vertical = 10.dp)) {
                Text(tr("Language"), style = MaterialTheme.typography.bodyLarge)
                Text(tr("Sevbify follows your phone's language. To use another one just for Sevbify, tap here (Android 13+: ") +
                     "Settings → Apps → Sevbify → Language). Search works in every language either way.",
                     style = MaterialTheme.typography.bodySmall)
            }
        }
        }
        "privacy" -> {
        item {
            Toggle(tr("Online"), "Search, radio, streaming, podcasts and downloads. Off: Sevbify contacts nothing; your own " +
                   "and downloaded music still plays.", s.online) {
                s.online = it; Library.changed(); scope.launch { try { Bridge.call("set_online", it) } catch (_: Exception) {} }
            }
        }
        item {
            Toggle(tr("Private session"), "What you play and search isn't remembered (Recently played, recent searches, " +
                   "podcast positions) until you turn it off or close Sevbify.", Library.privateSession) {
                Library.privateSession = it; Library.changed(save = false) }
        }
        item {
            Muted(tr("No account, no ads, no tracking, nothing sold. Online, Sevbify only contacts what each feature needs: ") +
                  "Deezer (search, radio, genres), Wikipedia (artist info), DuckDuckGo (only a finished search whose results look wrong, for “Did you mean”), Apple (podcast directory), the podcasts' own " +
                  "feeds, the Internet Archive (audiobooks), Bandcamp and YouTube (full songs, downloads), Spotify or Apple " +
                  "Music only when you import a link, LRCLIB for lyrics, song.link when you share a song, SponsorBlock for YouTube episodes, and GitHub for updates.")
        }
        item { Heading(tr("Your Sevbify profile")) }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(tr("One small file with your playlists, folders, podcasts, audiobooks, where you stopped, recently ") +
                     "played, recent searches and settings. Open it in Sevbify on any device: Android, iPhone, " +
                     "Windows, Mac or Linux. It stays where you save it; Sevbify never uploads it.",
                     style = MaterialTheme.typography.bodySmall)
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { exporter.launch(com.sevbify.app.Profile.FILE_NAME) }) { Text(tr("Export"), color = C.Text) }
                    OutlinedButton(onClick = { importer.launch(arrayOf("*/*")) }) { Text(tr("Import"), color = C.Text) }
                }
            }
        }
        item {
            Toggle(tr("Keep a copy in Downloads"), "Saves your profile to Download/Sevbify whenever you leave Sevbify, so " +
                   "it's still there if the app is uninstalled (then: Import, and pick it). Only on this phone.",
                   s.profileBackup) { s.profileBackup = it; Library.changed() }
        }
        }
        "playback" -> {
        item { Toggle(tr("Autoplay"), "When your music ends, keep playing similar songs.", s.autoplay) { s.autoplay = it; Library.changed() } }
        item {
            Toggle(tr("Lyrics"), "Show lyrics under Now playing: from a .lrc file next to your song, or from LRCLIB (a free lyrics " +
                   "database; only the song's name and length are sent).", s.lyrics) { s.lyrics = it; Library.changed() }
        }
        item {
            Toggle(tr("Skip sponsor segments in YouTube episodes"), "Jumps over ad reads, \"like and subscribe\" reminders " +
                   "and self-promotion that viewers marked on SponsorBlock. Private: the episode isn't named, only a " +
                   "4-character code shared by many videos is sent. YouTube's own ads never play in Sevbify.",
                   s.skipSponsors) { s.skipSponsors = it; Library.changed() }
        }
        item {
            Muted(tr("Songs you don't have yet always play in full (found on Bandcamp, then YouTube). A 30-second preview ") +
                  "only plays when you pick Preview from a song's menu.")
        }
        }
        "offline" -> {
        item { Toggle(tr("Data saver"), "Smaller song downloads and 360p video podcasts.", dataSaverOn()) { setDataSaver(it) } }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(tr("Download and stream from"), style = MaterialTheme.typography.bodyLarge)
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
            Muted(tr("Songs are saved in your phone's Music folder under Sevbify/<Artist>, so other apps and your PC see them. ") +
                  "Podcast episodes and audiobook chapters stay inside Sevbify.")
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp)) { OutlinedButton(onClick = { Nav.go(Screen.Downloads) }) { Text(tr("Downloads"), color = C.Text) } }
        }
        item { Heading(tr("Your music")) }
        item {
            var folders by remember { mutableStateOf(s.musicFolders.joinToString(", ")) }
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(tr("Music folders"), style = MaterialTheme.typography.bodyLarge)
                Text(tr("Folders on the phone Sevbify plays music from (separate with commas). Only these are read."),
                     style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(folders, { folders = it }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
                OutlinedButton(onClick = {
                    s.musicFolders = folders.split(",").map { it.trim() }.filter { it.isNotEmpty() }.toMutableList()
                    Library.changed()
                    (context as? com.sevbify.app.MainActivity)?.rescan()
                    Nav.say(tr("Music folders saved"))
                }, modifier = Modifier.padding(top = 6.dp)) { Text(tr("Save"), color = C.Text) }
            }
        }
        item {
            val treePicker = androidx.activity.compose.rememberLauncherForActivityResult(
                androidx.activity.result.contract.ActivityResultContracts.OpenDocumentTree()) { uri ->
                if (uri != null) {
                    if (com.sevbify.app.CloudFolders.add(context, uri)) {
                        (context as? com.sevbify.app.MainActivity)?.rescan()
                        Nav.say("Folder added: its songs appear in Your Songs")
                    } else Nav.say("⚠ That app didn't allow Sevbify to read the folder")
                }
            }
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(tr("Folders from other apps"), style = MaterialTheme.typography.bodyLarge)
                Text("An SD card, or a cloud app that offers folders in Android's file picker: Nextcloud, OneDrive, " +
                     "Dropbox, Proton Drive and others. Sevbify can only read the folders you pick, and your sign-in " +
                     "stays in that app. Cloud songs need the internet unless that app keeps them offline. (Google " +
                     "Drive's picker only allows single files, not folders.)", style = MaterialTheme.typography.bodySmall)
                s.cloudFolders.toList().forEach { f ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(com.sevbify.app.CloudFolders.name(context, f), maxLines = 1,
                             style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        IconButton(onClick = {
                            com.sevbify.app.CloudFolders.remove(context, f)
                            (context as? com.sevbify.app.MainActivity)?.rescan()
                        }) { Icon(Icons.Filled.Close, "Remove", tint = C.Sub) }
                    }
                }
                OutlinedButton(onClick = { treePicker.launch(null) }, modifier = Modifier.padding(top = 6.dp)) {
                    Text(tr("Add a folder"), color = C.Text)
                }
            }
        }
        item { ServersSection() }
        }
        "car" -> {
        item { CarSettings() }
        }
        "quality" -> {
        item {
            Choice(tr("Download quality"),
                   if (s.songQuality == "small") "Save space: a lower-bitrate original, about half the size. Slightly less " +
                       "detail with good headphones."
                   else "Best: the original audio with nothing lost (.m4a). A song can't be better than its source " +
                       "(YouTube ~128-160 kbps, Bandcamp 128 kbps), so this is also the smallest full-quality file. " +
                       "Plays in Samsung Music, VLC and on your PC.",
                   listOf("best" to tr("Best quality"), "small" to tr("Save space")), s.songQuality) { s.songQuality = it; Library.changed() }
        }
        item {
            Choice(tr("Audiobook quality"), "LibriVox records every chapter at both; speech sounds the same at 64 kbps.",
                   listOf("standard" to "Standard (64 kbps)", "high" to "High (128 kbps)"), s.bookQuality) {
                s.bookQuality = it; Library.changed()
            }
        }
        item {
            Choice(tr("Video podcast quality"), "When watching. Higher uses more data; the best YouTube has up to your choice is used.",
                   listOf("auto" to "Auto", "360" to "360p", "480" to "480p", "720" to "720p", "1080" to "1080p"), s.videoQuality) {
                s.videoQuality = it; Library.changed()
            }
        }
        }
        else -> {
        item {
            Muted("Sevbify ${Library.coreVersion} for Android. Built with AI help. Not affiliated with Spotify, YouTube, " +
                  "Bandcamp, Apple, Deezer or Sevby LLC.")
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = {
                    scope.launch {
                        update = try { com.sevbify.app.Updater.check(manual = true) }
                                 catch (e: Exception) {
                                     if (e is kotlinx.coroutines.CancellationException) throw e
                                     "Couldn't check: ${e.message}"
                                 }
                    }
                }) { Text(tr("Check for updates"), color = C.Text) }
                Spacer(Modifier.width(12.dp))
                Text(update, style = MaterialTheme.typography.bodySmall)
            }
        }
        item {
            Toggle(tr("Keep yt-dlp up to date"), "yt-dlp is what finds and downloads songs on YouTube; YouTube changes often. " +
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
                }) { Text(tr("Update yt-dlp now"), color = C.Text) }
                Spacer(Modifier.width(12.dp))
                Text(ytdlp, style = MaterialTheme.typography.bodySmall)
            }
        }
        }
        }
        item { Gap(32.dp) }
    }
}

/** Android 13+: the system's per-app language page for Sevbify; older Android: the phone's language settings. */
private fun openAppLanguage(context: android.content.Context) {
    val i = if (android.os.Build.VERSION.SDK_INT >= 33)
        android.content.Intent(android.provider.Settings.ACTION_APP_LOCALE_SETTINGS, android.net.Uri.parse("package:${context.packageName}"))
    else android.content.Intent(android.provider.Settings.ACTION_LOCALE_SETTINGS)
    try { context.startActivity(i.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {
        Nav.say(tr("Change Sevbify's language in your phone's Settings → Apps → Sevbify → Language"))
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
