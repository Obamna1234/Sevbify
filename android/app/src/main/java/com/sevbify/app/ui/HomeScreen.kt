package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Show
import com.sevbify.app.Track

/** Home, like Spotify's on Android: chips, eight quick tiles, then shelves. */
@Composable
fun HomeScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    var chip by rememberSaveable { mutableStateOf("all") }
    var popular by remember { mutableStateOf<List<Track>>(emptyList()) }
    var topShows by remember { mutableStateOf<List<Show>>(emptyList()) }
    LaunchedEffect(Library.settings.online) {
        if (!Library.settings.online) return@LaunchedEffect
        try {
            val a = Bridge.obj("genre_overview", 0).getJSONArray("tracks")
            popular = (0 until a.length()).map { Track.fromJson(a.getJSONObject(it)) }
        } catch (_: Exception) {}
        try {
            val a = Bridge.arr("top_shows", java.util.Locale.getDefault().country.lowercase().ifEmpty { "us" })
            topShows = (0 until a.length()).map { Show(a.getJSONObject(it)) }
        } catch (_: Exception) {}
    }
    LazyColumn(Modifier.background(Brush.verticalGradient(0f to Color(0xFF1E3264).copy(alpha = 0.55f), 0.25f to C.Bg))) {
        item {
            Row(Modifier.statusBarsPadding().horizontalScroll(rememberScrollState())
                    .padding(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SettingsBadge()
                listOf("all" to tr("All"), "music" to "Music", "podcasts" to "Podcasts", "audiobooks" to "Audiobooks").forEach { (k, l) ->
                    Chip(l, chip == k) { chip = if (chip == k) "all" else k }
                }
            }
        }
        if (chip == "podcasts" || chip == "audiobooks") {
            item { ShowsHomePart(chip, topShows) }
            // Explore, like Spotify's: a shelf per category (each loads when you scroll to it).
            if (Library.settings.online) {
                if (chip == "podcasts") {
                    items(PODCAST_CATEGORIES, key = { "pc" + it.first }) { (id, name) ->
                        CategoryShelf("Top in $name") {
                            val a = Bridge.arr("top_in_category", id, java.util.Locale.getDefault().country.lowercase().ifEmpty { "us" })
                            (0 until a.length()).map { Show(a.getJSONObject(it)) }
                        }
                    }
                } else {
                    item { CategoryShelf("New free audiobooks") {
                        val a = Bridge.arr("books", "newest", ""); (0 until a.length()).map { Show(a.getJSONObject(it)) } } }
                    items(BOOK_CATEGORIES, key = { "bc" + it.second }) { (name, subject) ->
                        CategoryShelf(name) {
                            val a = Bridge.arr("books", "category", subject)
                            (0 until a.length()).map { Show(a.getJSONObject(it)) }
                        }
                    }
                }
            }
            item { Gap(24.dp) }
            return@LazyColumn
        }
        val tiles = Library.playlists.sortedByDescending { maxOf(it.lastPlayed, it.created) }.take(7)
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                val all: List<Pair<String, () -> Unit>> = listOf<Pair<String, () -> Unit>>(
                    "Your Songs" to { Nav.go(Screen.YourSongs) }) + tiles.map { pl -> pl.name to { Nav.go(Screen.PlaylistPage(pl.id)) } }
                val covers = listOf("") + tiles.map { playlistCover(it) }
                all.chunked(2).forEachIndexed { r, pair ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        pair.forEachIndexed { c, (name, go) ->
                            QuickTile(name, covers[r * 2 + c], go, Modifier.weight(1f))
                        }
                        if (pair.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }
        }
        if (Library.recent.isNotEmpty()) {
            item { SectionTitle(tr("Recently played")) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(Library.recent.take(15).toList()) { t ->
                        ShelfCard(t.title, t.artist, t.art) { Player.play(t, Library.recent.toList(), "Recently played") }
                    }
                }
            }
        }
        if (Library.playlists.isNotEmpty()) {
            item { SectionTitle(tr("Your playlists")) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(Library.playlists.toList()) { pl ->
                        ShelfCard(pl.name, "Playlist • ${pl.tracks.size} songs", playlistCover(pl)) { Nav.go(Screen.PlaylistPage(pl.id)) }
                    }
                }
            }
        }
        if (popular.isNotEmpty()) {
            item { SectionTitle(tr("Popular right now")) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(popular.take(15)) { t -> ShelfCard(t.title, t.artist, t.art) { Player.play(t, popular, "Popular right now") } }
                }
            }
        }
        if (Library.playlists.isEmpty() && Library.recent.isEmpty()) {
            item {
                Muted(tr("Welcome to Sevbify. Search for a song, make a playlist with Create (+), or import one from Spotify ") +
                      "under Your Library. Songs on your phone show up in Your Songs.")
            }
        }
        item { Gap(24.dp) }
    }
}

@Composable
private fun QuickTile(name: String, cover: String, onClick: () -> Unit, modifier: Modifier) {
    Row(modifier.height(56.dp).clip(RoundedCornerShape(4.dp)).background(C.Card).clickable(onClick = onClick),
        verticalAlignment = Alignment.CenterVertically) {
        if (name == "Your Songs" && cover.isEmpty()) {
            Box(Modifier.size(56.dp).background(Brush.linearGradient(listOf(Color(0xFF450AF5), Color(0xFFC4EFD9)))),
                contentAlignment = Alignment.Center) { Text(tr("♪"), color = Color.White, fontWeight = FontWeight.Bold) }
        } else {
            Cover(cover, 56.dp, RoundedCornerShape(0.dp))
        }
        Spacer(Modifier.width(8.dp))
        Text(name, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.Bold),
             modifier = Modifier.padding(end = 8.dp))
    }
}

@Composable
private fun ShowsHomePart(chip: String, topShows: List<Show>) {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    val mine = Library.shows.filter { if (chip == "audiobooks") it.isBook else !it.isBook }
    if (mine.isNotEmpty()) {
        SectionTitle(if (chip == "audiobooks") "Your audiobooks" else "Your shows")
        LazyRow(Modifier.padding(start = 16.dp)) {
            items(mine) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } }
        }
    }
    if (chip == "podcasts") {
        if (topShows.isNotEmpty()) {
            SectionTitle(tr("Trending podcasts"))
            LazyRow(Modifier.padding(start = 16.dp)) {
                items(topShows) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } }
            }
        }
        Gap(12.dp)
        Row(Modifier.padding(horizontal = 16.dp)) { Chip(tr("Find podcasts"), false) { Nav.go(Screen.Podcasts) } }
    } else {
        // Popular free audiobooks (LibriVox), like the Top podcasts shelf.
        var popular by remember { mutableStateOf<List<Show>>(emptyList()) }
        LaunchedEffect(Library.settings.online) {
            if (Library.settings.online && popular.isEmpty()) {
                try { val a = Bridge.arr("books", "popular", ""); popular = (0 until a.length()).map { Show(a.getJSONObject(it)) } }
                catch (_: Exception) {}
            }
        }
        if (popular.isNotEmpty()) {
            SectionTitle(tr("Popular free audiobooks"))
            LazyRow(Modifier.padding(start = 16.dp)) {
                items(popular) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } }
            }
        }
        Gap(12.dp)
        Row(Modifier.padding(horizontal = 16.dp)) { Chip(tr("Find free audiobooks"), false) { Nav.go(Screen.Audiobooks) } }
    }
}

// Same lists as core/podcasts.PODCAST_CATEGORIES and core/audiobooks.BOOK_CATEGORIES.
internal val PODCAST_CATEGORIES = listOf(
    1303 to "Comedy", 1489 to "News", 1488 to "True Crime", 1324 to "Society & Culture", 1545 to "Sports",
    1512 to "Health & Fitness", 1321 to "Business", 1487 to "History", 1318 to "Technology", 1309 to "TV & Film",
    1533 to "Science", 1304 to "Education", 1301 to "Arts", 1310 to "Music", 1502 to "Leisure",
    1483 to "Fiction", 1305 to "Kids & Family", 1314 to "Religion & Spirituality",
)
internal val BOOK_CATEGORIES = listOf(
    "Fiction" to "fiction", "Mystery" to "mystery", "Science fiction" to "science fiction", "Adventure" to "adventure",
    "Romance" to "romance", "Horror" to "horror", "Fantasy" to "fantasy", "Children" to "children",
    "History" to "history", "Poetry" to "poetry", "Philosophy" to "philosophy", "Biography" to "biography",
)

/** One Explore shelf; nothing is shown when the list is empty or can't be loaded. */
@Composable
internal fun CategoryShelf(title: String, load: suspend () -> List<Show>) {
    var shows by remember(title) { mutableStateOf<List<Show>>(emptyList()) }
    LaunchedEffect(title) { shows = try { load() } catch (e: Exception) {
        if (e is kotlinx.coroutines.CancellationException) throw e; emptyList() } }
    if (shows.isNotEmpty()) {
        SectionTitle(title)
        LazyRow(Modifier.padding(start = 16.dp)) {
            items(shows) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } }
        }
    }
}
