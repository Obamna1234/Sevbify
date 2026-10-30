package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Library
import com.sevbify.app.Playlist

/** Your Library like Spotify's on Android: chips, Recents sort, Your Songs, To download, folders, playlists, shows. */
@Composable
fun LibraryScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    var chip by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf<String?>(null) }
    var open by remember { mutableStateOf(setOf<String>()) }
    var createOpen by remember { mutableStateOf(false) }
    val sort = Library.settings.librarySort
    val q = filter?.trim()?.lowercase() ?: ""

    fun sorted(list: List<Playlist>) = when (sort) {
        "alpha" -> list.sortedBy { it.name.lowercase() }
        "added" -> list.sortedByDescending { it.created }
        else -> list.sortedByDescending { maxOf(it.lastPlayed, it.created) }
    }.sortedByDescending { it.pinned }

    var sortOpen by remember { mutableStateOf(false) }
    val grid = Library.settings.libraryView == "grid"
    val chipKeys = listOf("", "playlists", "podcasts", "audiobooks", "downloaded")
    Column {
    // Header, chips and Sort stay put; the list under them swipes between the filters (like Spotify).
    Column {
            Row(Modifier.statusBarsPadding().padding(start = 16.dp, end = 4.dp, top = 10.dp),
                verticalAlignment = Alignment.CenterVertically) {
                SettingsBadge()
                Spacer(Modifier.width(12.dp))
                Text(tr("Your Library"), style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
                IconButton(onClick = { filter = if (filter == null) "" else null }) { Icon(Icons.Filled.Search, "Search Your Library") }
                IconButton(onClick = { createOpen = true }) { Icon(Icons.Filled.Add, "Create") }
            }
        if (filter != null) {
                OutlinedTextField(filter ?: "", { filter = it }, singleLine = true, placeholder = { Text(tr("Search in Your Library")) },
                                  modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        }
            LazyRow(Modifier.padding(vertical = 10.dp), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (chip.isNotEmpty()) item {
                    Box(Modifier.size(32.dp).clip(CircleShape).background(C.Card).clickable { chip = "" },
                        contentAlignment = Alignment.Center) { Icon(Icons.Filled.Close, "Show everything", Modifier.size(18.dp)) }
                }
                items(listOf("playlists" to tr("Playlists"), "podcasts" to tr("Podcasts"), "audiobooks" to tr("Audiobooks"),
                             "downloaded" to tr("Downloaded")).filter { chip.isEmpty() || chip == it.first }) { (k, l) ->
                    Chip(l, chip == k) { chip = if (chip == k) "" else k }
                }
            }
            Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Row(Modifier.weight(1f).clickable { sortOpen = true }.padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.AutoMirrored.Filled.Sort, null, tint = C.Text, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(tr(when (sort) { "alpha" -> "Alphabetical"; "added" -> "Recently added"; else -> "Recents" }),
                         style = MaterialTheme.typography.labelLarge)
                }
                // List / grid, like Spotify's button on the right.
                IconButton(onClick = { Library.settings.libraryView = if (grid) "list" else "grid"; Library.changed() }) {
                    Icon(if (grid) Icons.AutoMirrored.Filled.List else Icons.Filled.GridView,
                         if (grid) "Show as list" else "Show as grid", tint = C.Text, modifier = Modifier.size(20.dp))
                }
            }
    }
    SwipePages(chipKeys.indexOf(chip).coerceAtLeast(0), chipKeys.size, { chip = chipKeys[it] }) {
    LazyColumn {
        if ((chip == "" || chip == "playlists" || chip == "downloaded") && (q.isEmpty() || "your songs".contains(q))) {
            item {
                LibRow("Your Songs", "Songs on your phone • ${Library.localSongs.size}", null,
                       Brush.linearGradient(listOf(Color(0xFF450AF5), Color(0xFFC4EFD9))), "♥") { Nav.go(Screen.YourSongs) }
            }
        }
        if ((chip == "") && (q.isEmpty() || "to download".contains(q))) {
            val n = Library.toDownload().size
            item {
                LibRow("To download", "Not downloaded yet • $n songs", null,
                       Brush.linearGradient(listOf(Color(0xFF1ED760), Color(0xFF0E7A36))), "⬇") { Nav.go(Screen.ToDownload) }
            }
        }
        if (chip == "" || chip == "playlists" || chip == "downloaded") {
            val all = Library.playlists.filter { q.isEmpty() || q in it.name.lowercase() }
                .filter { chip != "downloaded" || (it.tracks.isNotEmpty() && it.tracks.all { t -> Library.localFor(t) != null }) }
            val inFolders = if (q.isEmpty() && chip != "downloaded") Library.folders.toList() else emptyList()
            for (f in inFolders) {
                val kids = sorted(all.filter { it.folder == f })
                item {
                    Row(Modifier.fillMaxWidth().combinedClickableCompat(onClick = { open = if (f in open) open - f else open + f },
                                                                        onLongClick = { Nav.folderMenu = f })
                            .padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(64.dp).clip(RoundedCornerShape(4.dp)).background(C.Card), contentAlignment = Alignment.Center) {
                            Icon(Icons.Filled.Folder, null, tint = C.Sub, modifier = Modifier.size(30.dp))
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(f, style = MaterialTheme.typography.bodyLarge)
                            Text("${kids.size} playlists", style = MaterialTheme.typography.bodySmall)
                        }
                        Icon(if (f in open) Icons.Filled.KeyboardArrowDown else Icons.Filled.KeyboardArrowRight, null, tint = C.Sub)
                    }
                }
                if (f in open) items(kids, key = { "f" + it.id }) { pl -> PlaylistRow(pl, indent = true) }
            }
            val loose = sorted(all.filter { inFolders.isEmpty() || it.folder.isEmpty() || it.folder !in inFolders })
            if (grid) {
                items(loose.chunked(3), key = { row -> "g" + row.first().id }) { row ->
                    Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        row.forEach { pl -> PlaylistTile(pl, Modifier.weight(1f)) }
                        repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
            } else items(loose, key = { it.id }) { pl -> PlaylistRow(pl) }
        }
        if (chip == "" || chip == "podcasts" || chip == "audiobooks") {
            val shows = Library.shows.filter { (chip == "" || (chip == "audiobooks") == it.isBook) && (q.isEmpty() || q in it.title.lowercase()) }
            items(shows, key = { "s" + it.key }) { s ->
                LibRow(s.title, (if (s.isBook) "Audiobook" else "Podcast") + " • ${s.author}", s.image) { Nav.go(Screen.ShowPage(s)) }
            }
        }
        item { Gap(24.dp) }
    }
    }
    }
    if (createOpen) CreateSheet { createOpen = false }
    if (sortOpen) SortSheet(sort) { picked -> sortOpen = false; if (picked != null) { Library.settings.librarySort = picked; Library.changed() } }
}

/** Spotify's "Sort by" sheet. */
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun SortSheet(current: String, done: (String?) -> Unit) {
    androidx.compose.material3.ModalBottomSheet(onDismissRequest = { done(null) }, containerColor = C.Elevated) {
        Column(Modifier.androidxNavPadding()) {
            Text(tr("Sort by"), style = MaterialTheme.typography.titleMedium,
                 modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            listOf("recents" to "Recents", "added" to "Recently added", "alpha" to "Alphabetical").forEach { (k, l) ->
                Row(Modifier.fillMaxWidth().clickable { done(k) }.padding(horizontal = 20.dp, vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text(tr(l), style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                    if (current == k) Icon(Icons.Filled.Check, null, tint = C.Green)
                }
            }
        }
    }
}

private fun Modifier.androidxNavPadding() = this.then(Modifier.padding(bottom = 24.dp))

@Composable
private fun PlaylistTile(pl: Playlist, modifier: Modifier) {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    Column(modifier.combinedClickableCompat(onClick = { Nav.go(Screen.PlaylistPage(pl.id)) }, onLongClick = { Nav.playlistMenu = pl })) {
        androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxWidth()) { PlaylistCover(pl, maxWidth) }
        Text(pl.name, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium,
             modifier = Modifier.padding(top = 6.dp))
        Text("${pl.tracks.size} songs", style = MaterialTheme.typography.bodySmall, maxLines = 1)
    }
}

@Composable
private fun PlaylistRow(pl: Playlist, indent: Boolean = false) {
    // Playlists are edited in place (rename, pin, covers): read the change counter so this row redraws at once.
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    val playing = com.sevbify.app.Player.current != null && com.sevbify.app.Player.sourceName == pl.name
    Row(Modifier.fillMaxWidth().combinedClickableCompat(onClick = { Nav.go(Screen.PlaylistPage(pl.id)) },
                                                         onLongClick = { Nav.playlistMenu = pl })
            .padding(start = if (indent) 32.dp else 16.dp, end = 16.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically) {
        PlaylistCover(pl, 64.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(pl.name, maxLines = 1, overflow = TextOverflow.Ellipsis,
                 style = MaterialTheme.typography.bodyLarge.copy(color = if (playing) C.Green else C.Text))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (pl.pinned) { Icon(Icons.Filled.PushPin, "Pinned", tint = C.Green, modifier = Modifier.size(13.dp)); Spacer(Modifier.width(4.dp)) }
                if (pl.tracks.isNotEmpty() && pl.tracks.all { Library.localFor(it) != null }) {
                    Icon(Icons.Filled.ArrowCircleDown, "Downloaded", tint = C.Green, modifier = Modifier.size(13.dp)); Spacer(Modifier.width(4.dp))
                }
                Text("Playlist • ${pl.tracks.size} songs", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun LibRow(title: String, subtitle: String, image: String?, brush: Brush? = null, glyph: String = "", onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically) {
        if (brush != null) {
            Box(Modifier.size(64.dp).clip(RoundedCornerShape(4.dp)).background(brush), contentAlignment = Alignment.Center) {
                Text(glyph, color = Color.White, style = MaterialTheme.typography.titleLarge)
            }
        } else Cover(image, 64.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyLarge)
            Text(subtitle, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Suppress("unused")
private val unusedIcon: ImageVector = Icons.Filled.Folder
