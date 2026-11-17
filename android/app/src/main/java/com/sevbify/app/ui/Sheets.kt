package com.sevbify.app.ui

import com.sevbify.app.tr

import kotlinx.coroutines.launch
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.clickable
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.Album
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.PlayCircleOutline
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CreateNewFolder
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material.icons.filled.RemoveCircleOutline
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Downloads
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Track

@Composable
fun Sheets() {
    Nav.songMenu?.let { SongMenuSheet(it) }
    Nav.playlistMenu?.let { PlaylistMenuSheet(it) }
    Nav.folderMenu?.let { FolderMenuSheet(it) }
    Nav.addTo?.let { AddToSheet(it) }
    Nav.previewFor?.let { PreviewDialog(it) }
}

/** Hand text (a shared playlist or taste link) to Android's share sheet: the user picks the app and person. */
fun shareText(context: android.content.Context, text: String) {
    val send = android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain")
        .putExtra(android.content.Intent.EXTRA_TEXT, text)
    context.startActivity(android.content.Intent.createChooser(send, "Share").addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
}

/** Blend: send your taste (top artists and songs, no dates) to a friend. */
fun shareTaste(context: android.content.Context) {
    com.sevbify.app.SevbifyApp.instance.scope.launch {
        try {
            val link = com.sevbify.app.Bridge.call("taste_link", com.sevbify.app.Library.listensJson()) as? String ?: return@launch
            shareText(context, "Let's make a Blend in Sevbify (paste this in Import a playlist, then send me yours):\n$link")
        } catch (e: Exception) { Nav.say("⚠ Couldn't make the link: ${e.message}") }
    }
}

/** After hiding something: the first time, a note on where to undo it; after that, a short message. */
fun hideNote(on: Boolean) {
    if (on && !com.sevbify.app.Library.settings.hideNoteSeen) Nav.hideNoteOpen = true
    else Nav.say(if (on) "Hidden · undo in Settings → Playback → Hidden songs and artists" else "It'll play again")
}

@Composable
fun SheetItem(icon: ImageVector, text: String, enabled: Boolean = true, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(enabled = enabled, onClick = onClick).padding(horizontal = 20.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (enabled) C.Sub else C.Dim, modifier = Modifier.size(24.dp))
        Spacer(Modifier.width(16.dp))
        Text(text, style = MaterialTheme.typography.bodyLarge.copy(color = if (enabled) C.Text else C.Dim))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SongMenuSheet(m: SongMenu) {
    val t = m.track
    val close = { Nav.songMenu = null }
    val context = LocalContext.current
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()).navigationBarsPadding()) {
            Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Cover(t.art, 48.dp)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium)
                    Text(t.artist, maxLines = 1, style = MaterialTheme.typography.bodySmall)
                }
            }
            HorizontalDivider(color = C.Highlight)
            SheetItem(Icons.Filled.AddCircleOutline, tr("Add to playlist")) { close(); Nav.addTo = listOf(t) }
            if (m.playlist != null && m.row >= 0) {
                SheetItem(Icons.Filled.RemoveCircleOutline, tr("Remove from this playlist")) {
                    close(); Library.removeAt(m.playlist, listOf(m.row))
                }
            }
            SheetItem(Icons.AutoMirrored.Filled.QueueMusic, tr("Add to queue")) { close(); Player.addToQueue(t); Nav.say(tr("Added to queue")) }
            if (!t.isItem) {
                val have = Library.localFor(t) != null
                val st = Downloads.stateOf(t)
                when {
                    have -> SheetItem(Icons.Filled.ArrowCircleDown, tr("Downloaded"), enabled = false) {}
                    st == Downloads.State.QUEUED || st == Downloads.State.DOWNLOADING ->
                        SheetItem(Icons.Filled.Cancel, tr("Cancel download")) { close(); Downloads.cancel(t.matchKey) }
                    else -> SheetItem(Icons.Filled.Download, tr(if (st == Downloads.State.FAILED) "Try download again" else "Download")) {
                        close()
                        if (Downloads.request(listOf(t)) > 0) Nav.say("Downloading ${t.title}")
                    }
                }
                SheetItem(Icons.Filled.Radio, tr("Go to song radio"), enabled = Library.settings.online) { close(); Player.startRadio(t) }
                if (t.artist.isNotEmpty() && t.artist != "Unknown Artist") {
                    SheetItem(Icons.Filled.Person, tr("Go to artist")) { close(); Nav.nowPlayingOpen = false; Nav.go(Screen.Artist(t.artist)) }
                }
                if (t.album.isNotEmpty()) {
                    SheetItem(Icons.Filled.Album, tr("Go to album")) {
                        close(); Nav.nowPlayingOpen = false
                        goToAlbum(t)
                    }
                }
            }
            if (!t.isItem) {
                val liked = Library.isLiked(t)
                SheetItem(if (liked) Icons.Filled.CheckCircle else Icons.Filled.AddCircleOutline,
                          if (liked) "Remove from Liked Songs" else "Add to Liked Songs") { close(); Library.toggleLike(t) }
            }
            SheetItem(Icons.Filled.Share, tr("Share")) { close(); Nav.shareFor = t }
            if (t.source == "podcast") {
                val saved = com.sevbify.app.Library.isSavedEpisode(t)
                SheetItem(if (saved) Icons.Filled.RemoveCircleOutline else Icons.Filled.AddCircleOutline,
                          if (saved) "Remove from Your Episodes" else "Save to Your Episodes") {
                    close(); com.sevbify.app.Library.saveEpisode(t, !saved)
                }
                val played = t.itemKey in com.sevbify.app.Library.finished
                SheetItem(Icons.Filled.CheckCircle, if (played) "Mark as not played" else "Mark as played") {
                    close(); com.sevbify.app.Library.markPlayed(t, !played)
                }
            }
            if (com.sevbify.app.Player.current?.matchKey == t.matchKey) {
                val p = com.sevbify.app.Player
                SheetItem(Icons.Filled.Bedtime, if (p.sleepAt != null || p.sleepAtEnd) "Sleep timer (on)" else "Sleep timer") {
                    close(); Nav.sleepOpen = true
                }
                if (t.isItem) SheetItem(Icons.Filled.Speed, "Playback speed: ${p.speed.toString().removeSuffix(".0")}×") {
                    val steps = listOf(0.8f, 1f, 1.2f, 1.5f, 1.75f, 2f)
                    p.changeSpeed(steps[(steps.indexOf(p.speed).let { if (it < 0) 0 else it } + 1) % steps.size])
                }
            }
            if (!t.isItem && t.artist.isNotBlank() && t.artist != "Unknown Artist")
                SheetItem(Icons.Filled.Favorite, "Support the artist") { close(); Nav.supportFor = t }
            if (!t.isItem) {
                val hiddenSong = com.sevbify.app.Hidden.songHidden(t)
                SheetItem(Icons.Filled.Block, if (hiddenSong) "Show this song again" else "Hide song") {
                    close(); com.sevbify.app.Hidden.set("song", t.artist, t.title, !hiddenSong); hideNote(!hiddenSong)
                }
                if (t.artist.isNotBlank() && t.artist != "Unknown Artist") {
                    val hiddenArtist = com.sevbify.app.Hidden.artistHidden(t.artist)
                    SheetItem(Icons.Filled.Block, if (hiddenArtist) "Play ${t.artist} again" else "Don't play this artist") {
                        close(); com.sevbify.app.Hidden.set("artist", t.artist, "", !hiddenArtist); hideNote(!hiddenArtist)
                    }
                }
            }
            if (com.sevbify.app.PairLink.connected && !t.isItem)
                SheetItem(Icons.Filled.Computer, "Add to ${com.sevbify.app.PairLink.computer?.name ?: "computer"}'s queue") {
                    close(); com.sevbify.app.PairLink.addToComputerQueue(t)
                    Nav.say("Added to ${com.sevbify.app.PairLink.computer?.name ?: "the computer"}'s queue")
                }
            if (com.sevbify.app.PairLink.connected && t.localUri.isNotEmpty())
                SheetItem(Icons.Filled.Computer, "Send to ${com.sevbify.app.PairLink.computer?.name ?: "computer"}") {
                    close(); com.sevbify.app.PairLink.send(listOf(t))
                }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlaylistMenuSheet(pl: com.sevbify.app.Playlist) {
    val close = { Nav.playlistMenu = null }
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()).navigationBarsPadding()) {
            Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                PlaylistCover(pl, 48.dp)
                Spacer(Modifier.width(12.dp))
                Text(pl.name, style = MaterialTheme.typography.titleMedium)
            }
            HorizontalDivider(color = C.Highlight)
            SheetItem(Icons.AutoMirrored.Filled.QueueMusic, tr("Add to queue")) { close(); pl.tracks.forEach { Player.addToQueue(it) } }
            if (com.sevbify.app.PairLink.connected) {
                val mine = pl.tracks.mapNotNull { t -> if (t.localUri.isNotEmpty()) t else Library.localFor(t) }
                SheetItem(Icons.Filled.Computer, "Send to ${com.sevbify.app.PairLink.computer?.name ?: "computer"}",
                          enabled = mine.isNotEmpty()) { close(); com.sevbify.app.PairLink.send(mine, pl.name) }
            }
            val context = androidx.compose.ui.platform.LocalContext.current
            SheetItem(Icons.Filled.Share, "Share with a friend") {
                close()
                com.sevbify.app.SevbifyApp.instance.scope.launch {
                    try {
                        val tracks = org.json.JSONArray().also { a -> pl.tracks.forEach { a.put(it.toJson()) } }
                        val link = com.sevbify.app.Bridge.call("share_link", pl.name, tracks.toString()) as? String ?: return@launch
                        shareText(context, "Here's my playlist “${pl.name}” for Sevbify (paste it in Import a playlist):\n$link")
                    } catch (e: Exception) { Nav.say("⚠ Couldn't make the link: ${e.message}") }
                }
            }
            SheetItem(Icons.Filled.Edit, tr("Edit details")) { close(); askName(pl.name) { Library.rename(pl, it) } }
            SheetItem(Icons.Filled.Edit, if (pl.description.isEmpty()) "Add description" else "Edit description") {
                close(); askName(pl.description, "Description") { pl.description = it.trim().take(300); Library.changed() }
            }
            SheetItem(Icons.Filled.Image, "Choose cover picture") { close(); Nav.coverFor = pl }
            if (pl.coverUrl.startsWith("file:")) SheetItem(Icons.Filled.Image, "Remove cover picture") {
                close()
                runCatching { java.io.File(android.net.Uri.parse(pl.coverUrl).path ?: "").delete() }
                pl.coverUrl = ""; Library.changed()
            }
            SheetItem(Icons.Filled.Delete, tr("Delete playlist")) {
                close()
                confirmDelete(pl.name) {
                    val open = (Nav.top as? Screen.PlaylistPage)?.id == pl.id
                    Library.delete(pl)
                    if (open) Nav.back()
                }
            }
            val pending = pl.tracks.filter { !it.isLocal && Library.localFor(it) == null }
            SheetItem(Icons.Filled.Download, if (pending.isEmpty()) "Downloaded" else "Download ${pending.size} songs",
                      enabled = pending.isNotEmpty()) { close(); Downloads.request(pending) }
            SheetItem(Icons.Filled.MusicNote, tr("Create playlist")) { close(); Nav.go(Screen.PlaylistPage(Library.newPlaylist().id)) }
            SheetItem(Icons.Filled.CreateNewFolder, tr("Create folder")) { close(); askNewFolder() }
            SheetItem(if (pl.pinned) Icons.Filled.PushPin else Icons.Filled.PushPin, tr(if (pl.pinned) "Unpin playlist" else "Pin playlist")) {
                close(); pl.pinned = !pl.pinned; Library.changed()
            }
            HorizontalDivider(color = C.Highlight)
            Text(tr("Move to folder"), style = MaterialTheme.typography.labelMedium.copy(color = C.Sub),
                 modifier = Modifier.padding(start = 20.dp, top = 12.dp))
            SheetItem(Icons.Filled.Add, tr("Create folder")) {
                close(); askNewFolder { f -> pl.folder = f; Library.changed() }
            }
            Library.folders.forEach { f ->
                SheetItem(Icons.Filled.Folder, f, enabled = pl.folder != f) { close(); pl.folder = f; Library.changed() }
            }
            if (pl.folder.isNotEmpty()) SheetItem(Icons.Filled.Folder, tr("Remove from folder")) { close(); pl.folder = ""; Library.changed() }
        }
    }
}

/** Long-press a folder in Your Library: rename or delete it (its playlists are kept). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FolderMenuSheet(folder: String) {
    val close = { Nav.folderMenu = null }
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()).navigationBarsPadding()) {
            Text(folder, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
            HorizontalDivider(color = C.Highlight)
            SheetItem(Icons.Filled.Edit, tr("Rename folder")) {
                close(); askName(folder, "Rename folder") { Library.renameFolder(folder, it) }
            }
            SheetItem(Icons.Filled.Delete, tr("Delete folder")) {
                close()
                Nav.confirm = Triple("Delete folder?", "“$folder” is removed. The playlists in it stay in Your Library.",
                                     { Library.deleteFolder(folder) })
            }
        }
    }
}

/** "Add to playlist" like Spotify's: New playlist at the top, then your playlists. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddToSheet(tracks: List<Track>) {
    val close = { Nav.addTo = null }
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Text(tr("Add to playlist"), style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 20.dp))
        Gap(8.dp)
        LazyColumn(Modifier.navigationBarsPadding()) {
            item {
                SheetItem(Icons.Filled.Add, tr("New playlist")) {
                    close(); val pl = Library.newPlaylist(tracks = tracks); Nav.say("Added to ${pl.name}")
                }
            }
            items(Library.playlists.toList()) { pl ->
                Row(Modifier.fillMaxWidth().clickable { close(); Library.add(pl, tracks); Nav.say("Added to ${pl.name}") }
                        .padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    PlaylistCover(pl, 48.dp)
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(pl.name, style = MaterialTheme.typography.bodyLarge)
                        Text("${pl.tracks.size} songs", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreateSheet(onClose: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onClose, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.navigationBarsPadding().padding(bottom = 12.dp)) {
            SheetItem(Icons.Filled.MusicNote, tr("Playlist")) {
                onClose(); Nav.tab = Tab.LIBRARY; Nav.go(Screen.PlaylistPage(Library.newPlaylist().id))
            }
            SheetItem(Icons.Filled.Folder, tr("Folder")) { onClose(); Nav.tab = Tab.LIBRARY; askNewFolder() }
            SheetItem(Icons.Filled.Link, tr("Import a playlist")) { onClose(); Nav.tab = Tab.LIBRARY; Nav.go(Screen.Import()) }
            val ctx = androidx.compose.ui.platform.LocalContext.current
            SheetItem(Icons.Filled.Share, "Blend with a friend") { onClose(); shareTaste(ctx) }
        }
    }
}

/** A playlist's cover: its own picture, else the first song's. */
fun playlistCover(pl: com.sevbify.app.Playlist): String =
    pl.coverUrl.ifEmpty { playlistCovers(pl).firstOrNull() ?: "" }

/** Spotify's picture for a playlist you haven't given one (same rule as core/playlist_cover.py): the covers of the
 *  first 4 *different* albums in the playlist's order as a 2x2 grid; fewer than 4 → the first song's cover alone. */
fun playlistCovers(pl: com.sevbify.app.Playlist): List<String> {
    val seen = HashSet<String>(); val picks = ArrayList<String>(4); var first = ""
    for (t in pl.tracks) {
        val art = t.art
        if (art.isEmpty()) continue
        if (first.isEmpty()) first = art
        val album = t.album.trim().lowercase()
        val key = if (album.isNotEmpty() && album != "unknown album") "a|$album|${t.artist.trim().lowercase()}" else "c|$art"
        if (!seen.add(key)) continue
        picks.add(art)
        if (picks.size == 4) return picks
    }
    return if (first.isEmpty()) emptyList() else listOf(first)
}

/** Colours for Settings ▸ "Show where playlists came from" (off by default). */
fun originColour(origin: String): Color = when (origin) {
    "file" -> Color(0xFF509BF5)                // imported from a file (.txt / .csv / .m3u): blue
    "spotify", "link" -> Color(0xFF1ED760)     // Spotify link: green
    "apple" -> Color(0xFFFFFFFF)               // Apple Music link: white
    "deezer" -> Color(0xFFA238FF)              // Deezer link: purple
    "jamendo" -> Color(0xFFFF8A1F)             // Jamendo link: orange
    else -> Color(0xFF8A8A8A)                  // made in Sevbify: grey
}

/** A playlist's picture: its own cover, or Spotify's 2x2 of album covers; with the optional origin border. */
@Composable
fun PlaylistCover(pl: com.sevbify.app.Playlist, size: Dp, modifier: Modifier = Modifier) {
    @Suppress("UNUSED_VARIABLE") val tick = com.sevbify.app.Library.changes
    val shape = RoundedCornerShape(4.dp)
    val ring = if (com.sevbify.app.Library.settings.showPlaylistOrigin)
        Modifier.border(if (size >= 100.dp) 4.dp else 2.dp, originColour(pl.origin), shape) else Modifier
    val covers = if (pl.coverUrl.isNotEmpty()) listOf(pl.coverUrl) else playlistCovers(pl)
    Box(modifier.size(size).clip(shape).then(ring)) {
        if (covers.size == 4) {
            Column {
                Row { Cover(covers[0], size / 2, RectangleShape); Cover(covers[1], size / 2, RectangleShape) }
                Row { Cover(covers[2], size / 2, RectangleShape); Cover(covers[3], size / 2, RectangleShape) }
            }
        } else Cover(covers.firstOrNull(), size, shape)
    }
}


/** Like Spotify: the whole album in its own order (downloaded songs play from the phone, the rest stream).
 *  Offline, or when it isn't found online: the album's songs you have on the phone. */
fun goToAlbum(t: com.sevbify.app.Track) {
    val local = com.sevbify.app.Library.localSongs.filter { it.album == t.album && it.artist == t.artist }
    fun fallback() {
        if (local.isNotEmpty()) Nav.go(Screen.Collection("Album", t.album, local, t.art, saveable = false))
        else Nav.go(Screen.Artist(t.artist))
    }
    if (!com.sevbify.app.Library.settings.online) { fallback(); return }
    com.sevbify.app.SevbifyApp.instance.scope.launch {
        try {
            val found = com.sevbify.app.Bridge.call("album_for", t.artist, t.album)
            if (found is org.json.JSONObject) openWebAlbum(found) else fallback()
        } catch (e: Exception) { fallback() }
    }
}
