package com.sevbify.app.ui

import kotlinx.coroutines.launch
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CreateNewFolder
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Folder
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
    Nav.addTo?.let { AddToSheet(it) }
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
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated) {
        Column(Modifier.navigationBarsPadding()) {
            Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Cover(t.art, 48.dp)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium)
                    Text(t.artist, maxLines = 1, style = MaterialTheme.typography.bodySmall)
                }
            }
            HorizontalDivider(color = C.Highlight)
            SheetItem(Icons.Filled.AddCircleOutline, "Add to playlist") { close(); Nav.addTo = listOf(t) }
            if (m.playlist != null && m.row >= 0) {
                SheetItem(Icons.Filled.RemoveCircleOutline, "Remove from this playlist") {
                    close(); Library.removeAt(m.playlist, listOf(m.row))
                }
            }
            SheetItem(Icons.AutoMirrored.Filled.QueueMusic, "Add to queue") { close(); Player.addToQueue(t); Nav.say("Added to queue") }
            if (!t.isItem) {
                val have = Library.localFor(t) != null
                val st = Downloads.stateOf(t)
                when {
                    have -> SheetItem(Icons.Filled.ArrowCircleDown, "Downloaded", enabled = false) {}
                    st == Downloads.State.QUEUED || st == Downloads.State.DOWNLOADING ->
                        SheetItem(Icons.Filled.Cancel, "Cancel download") { close(); Downloads.cancel(t.matchKey) }
                    else -> SheetItem(Icons.Filled.Download, if (st == Downloads.State.FAILED) "Try download again" else "Download") {
                        close()
                        if (Downloads.request(listOf(t)) > 0) Nav.say("Downloading ${t.title}")
                    }
                }
                SheetItem(Icons.Filled.Radio, "Go to song radio", enabled = Library.settings.online) { close(); Player.startRadio(t) }
                if (t.artist.isNotEmpty() && t.artist != "Unknown Artist") {
                    SheetItem(Icons.Filled.Person, "Go to artist") { close(); Nav.nowPlayingOpen = false; Nav.go(Screen.Artist(t.artist)) }
                }
                if (t.album.isNotEmpty()) {
                    SheetItem(Icons.Filled.Album, "Go to album") {
                        close(); Nav.nowPlayingOpen = false
                        goToAlbum(t)
                    }
                }
            }
            SheetItem(Icons.Filled.Share, "Share") { close(); Nav.shareFor = t }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlaylistMenuSheet(pl: com.sevbify.app.Playlist) {
    val close = { Nav.playlistMenu = null }
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated) {
        Column(Modifier.navigationBarsPadding()) {
            Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                PlaylistCover(pl, 48.dp)
                Spacer(Modifier.width(12.dp))
                Text(pl.name, style = MaterialTheme.typography.titleMedium)
            }
            HorizontalDivider(color = C.Highlight)
            SheetItem(Icons.AutoMirrored.Filled.QueueMusic, "Add to queue") { close(); pl.tracks.forEach { Player.addToQueue(it) } }
            SheetItem(Icons.Filled.Edit, "Edit details") { close(); askName(pl.name) { Library.rename(pl, it) } }
            SheetItem(Icons.Filled.Delete, "Delete") { close(); confirmDelete(pl.name) { Library.delete(pl); Nav.back() } }
            val pending = pl.tracks.filter { !it.isLocal && Library.localFor(it) == null }
            SheetItem(Icons.Filled.Download, if (pending.isEmpty()) "Downloaded" else "Download ${pending.size} songs",
                      enabled = pending.isNotEmpty()) { close(); Downloads.request(pending) }
            SheetItem(Icons.Filled.MusicNote, "Create playlist") { close(); Nav.go(Screen.PlaylistPage(Library.newPlaylist().id)) }
            SheetItem(Icons.Filled.CreateNewFolder, "Create folder") { close(); Library.createFolder() }
            SheetItem(if (pl.pinned) Icons.Filled.PushPin else Icons.Filled.PushPin, if (pl.pinned) "Unpin playlist" else "Pin playlist") {
                close(); pl.pinned = !pl.pinned; Library.changed()
            }
            HorizontalDivider(color = C.Highlight)
            Text("Move to folder", style = MaterialTheme.typography.labelMedium.copy(color = C.Sub),
                 modifier = Modifier.padding(start = 20.dp, top = 12.dp))
            SheetItem(Icons.Filled.Add, "Create folder") {
                close(); val f = Library.createFolder(); pl.folder = f; Library.changed()
            }
            Library.folders.forEach { f ->
                SheetItem(Icons.Filled.Folder, f, enabled = pl.folder != f) { close(); pl.folder = f; Library.changed() }
            }
            if (pl.folder.isNotEmpty()) SheetItem(Icons.Filled.Folder, "Remove from folder") { close(); pl.folder = ""; Library.changed() }
        }
    }
}

/** "Add to playlist" like Spotify's: New playlist at the top, then your playlists. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddToSheet(tracks: List<Track>) {
    val close = { Nav.addTo = null }
    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated) {
        Text("Add to playlist", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 20.dp))
        Gap(8.dp)
        LazyColumn(Modifier.navigationBarsPadding()) {
            item {
                SheetItem(Icons.Filled.Add, "New playlist") {
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
    ModalBottomSheet(onDismissRequest = onClose, containerColor = C.Elevated) {
        Column(Modifier.navigationBarsPadding().padding(bottom = 12.dp)) {
            SheetItem(Icons.Filled.MusicNote, "Playlist") {
                onClose(); Nav.tab = Tab.LIBRARY; Nav.go(Screen.PlaylistPage(Library.newPlaylist().id))
            }
            SheetItem(Icons.Filled.Folder, "Folder") { onClose(); Library.createFolder(); Nav.tab = Tab.LIBRARY }
            SheetItem(Icons.Filled.Link, "Import a playlist") { onClose(); Nav.tab = Tab.LIBRARY; Nav.go(Screen.Import()) }
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
    "" -> Color(0xFF509BF5)                    // made in Sevbify: blue
    "file" -> Color(0xFFAF7BFF)                // imported from a file (.txt / .csv / .m3u): purple
    else -> Color(0xFFFFA42B)                  // imported from a link (Spotify / Apple Music): orange
}

/** A playlist's picture: its own cover, or Spotify's 2x2 of album covers; with the optional origin border. */
@Composable
fun PlaylistCover(pl: com.sevbify.app.Playlist, size: Dp, modifier: Modifier = Modifier) {
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
