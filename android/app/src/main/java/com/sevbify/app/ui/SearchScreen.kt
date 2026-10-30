package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Show
import com.sevbify.app.Track
import kotlinx.coroutines.delay
import org.json.JSONObject

val TileColours = listOf(0xFFE13300, 0xFF1E3264, 0xFF8400E7, 0xFF148A08, 0xFFE8115B, 0xFF477D95, 0xFFBA5D07,
                         0xFF503750, 0xFF0D73EC, 0xFF8D67AB, 0xFF27856A, 0xFFAF2896)

/** Search like Spotify's on Android: Browse all while empty; your songs first, then the web, artists, podcasts. */
@Composable
fun SearchScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    var query by rememberSaveable { mutableStateOf("") }
    var chip by rememberSaveable { mutableStateOf("all") }
    var web by remember { mutableStateOf<List<Track>>(emptyList()) }
    var artists by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var shows by remember { mutableStateOf<List<Show>>(emptyList()) }
    var books by remember { mutableStateOf<List<Show>>(emptyList()) }
    var note by remember { mutableStateOf("") }
    var genres by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var better by remember { mutableStateOf("") }               // "Did you mean …?"

    LaunchedEffect(Library.settings.online) {
        if (Library.settings.online && genres.isEmpty()) {
            try { val a = Bridge.arr("genres"); genres = (0 until a.length()).map { a.getJSONObject(it) } } catch (_: Exception) {}
        }
    }
    // Recent searches, like Spotify's: a search you stay on for a moment is remembered (only on this phone).
    LaunchedEffect(query) {
        if (better.isNotEmpty() && query.trim() != better) better = ""
        if (query.trim().length < 2) return@LaunchedEffect
        delay(2500)
        Library.rememberSearch(query)
        // Only the finished search, and only when its results look unrelated, is checked for a typo (DuckDuckGo).
        if (Library.settings.online && query.trim().length >= 3) {
            better = try { (Bridge.call("did_you_mean", query.trim()) as? String).orEmpty() } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                ""
            }
        }
    }
    LaunchedEffect(query, chip) {
        web = emptyList(); artists = emptyList(); shows = emptyList(); books = emptyList(); note = ""
        val q = query.trim()
        if (q.length < 2 || !Library.settings.online) return@LaunchedEffect
        delay(450)                                    // wait until typing pauses
        note = "Searching…"
        try {
            if (chip == "all" || chip == "songs") web = Bridge.tracks("search", q, 30).filter { Library.settings.explicitOk || !it.explicit }
            if (chip == "all" || chip == "artists") {
                val a = Bridge.arr("search_artists", q, 10); artists = (0 until a.length()).map { a.getJSONObject(it) }
            }
            if (chip == "all" || chip == "podcasts") {
                val a = Bridge.arr("search_podcasts", q, "us", chip == "podcasts"); shows = (0 until a.length()).map { Show(a.getJSONObject(it)) }
            }
            if (chip == "audiobooks") {
                val a = Bridge.arr("books", "search", q); books = (0 until a.length()).map { Show(a.getJSONObject(it)) }
            }
            note = ""
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
            note = "Web search isn't available right now (${e.message})."
        }
    }

    val local = remember(query, Library.localSongs, tick) {
        // Any language: case and accents don't matter ("beyonce" finds "Beyoncé").
        val q = fold(query.trim())
        if (q.isEmpty()) emptyList() else Library.localSongs.filter {
            q in fold(it.title) || q in fold(it.artist) || q in fold(it.album)
        }.take(50)
    }
    LazyColumn {
        item {
            Column(Modifier.statusBarsPadding().padding(16.dp)) {
                Text(tr("Search"), style = MaterialTheme.typography.headlineMedium)
                Gap(12.dp)
                Row(Modifier.fillMaxWidth().height(48.dp).clip(RoundedCornerShape(6.dp)).background(Color.White)
                        .padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Search, null, tint = Color(0xFF121212))
                    Spacer(Modifier.width(10.dp))
                    Box(Modifier.weight(1f)) {
                        if (query.isEmpty()) Text(tr("What do you want to listen to?"), color = Color(0xFF535353),
                                                  style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold))
                        BasicTextField(query, { query = it }, singleLine = true, cursorBrush = SolidColor(C.Green),
                                       textStyle = TextStyle(color = Color(0xFF121212), fontSize = 16.sp, fontFamily = Figtree,
                                                             fontWeight = FontWeight.SemiBold),
                                       modifier = Modifier.fillMaxWidth())
                    }
                    if (query.isNotEmpty()) IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, "Clear", tint = Color(0xFF121212)) }
                }
            }
        }
        if (query.isBlank() && Library.searches.isNotEmpty()) {
            item {
                Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(tr("Recent searches"), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    androidx.compose.material3.TextButton(onClick = { Library.searches.clear(); Library.changed() }) {
                        Text(tr("Clear"), color = C.Sub)
                    }
                }
            }
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Library.searches.take(10).forEach { q -> Chip(q, false) { query = q } }
                }
            }
            item { Gap(12.dp) }
        }
        if (query.isBlank()) {
            item { Text(tr("Browse all"), style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(start = 16.dp, bottom = 8.dp)) }
            val tiles = listOf(Triple("Podcasts", 0xFF006450L, -1), Triple("Audiobooks", 0xFF1E3264L, -2)) +
                genres.mapIndexed { i, g -> Triple(g.optString("name"), TileColours[i % TileColours.size], g.optInt("id")) }
            items(tiles.chunked(2)) { pair ->
                Row(Modifier.padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    pair.forEach { (name, colour, id) ->
                        val g = genres.firstOrNull { it.optInt("id") == id }
                        BrowseTile(name, Color(colour), g?.optString("picture"), Modifier.weight(1f)) {
                            when (id) {
                                -1 -> Nav.go(Screen.Podcasts)
                                -2 -> Nav.go(Screen.Audiobooks)
                                else -> Nav.go(Screen.Genre(id, name, colour))
                            }
                        }
                    }
                    if (pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
            if (!Library.settings.online) item { Muted(tr("You're offline: music genres come back when you're online.")) }
            item { Gap(24.dp) }
            return@LazyColumn
        }
        item {
            LazyRow(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(listOf("all" to tr("All"), "songs" to "Songs", "artists" to "Artists", "podcasts" to "Podcasts",
                             "audiobooks" to "Audiobooks")) { (k, l) -> Chip(l, chip == k) { chip = k } }
            }
        }
        if (better.isNotEmpty() && better != query.trim()) {
            item {
                androidx.compose.material3.TextButton(onClick = { query = better }, modifier = Modifier.padding(horizontal = 8.dp)) {
                    Text(tr("Did you mean") + "  “$better”?", color = C.Text, style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
        if (local.isNotEmpty() && (chip == "all" || chip == "songs")) {
            item { SectionTitle(tr("In your library")) }
            items(local) { t ->
                TrackRow(t, onClick = { Player.play(t, local, "Search: $query") },
                         onMore = { Nav.songMenu = SongMenu(t, queue = local, source = "Search: $query") })
            }
        }
        if (artists.isNotEmpty()) {
            item { SectionTitle(tr("Artists")) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(artists) { a ->
                        ShelfCard(a.optString("name"), "Artist", a.optString("picture_xl"), round = true) {
                            Nav.go(Screen.Artist(a.optString("name")))
                        }
                    }
                }
            }
        }
        if (web.isNotEmpty()) {
            item { SectionTitle(tr("Songs")) }
            items(web) { t ->
                TrackRow(t, onClick = { Player.play(t, web, "Search: $query") },
                         onMore = { Nav.songMenu = SongMenu(t, queue = web, source = "Search: $query") })
            }
        }
        if (shows.isNotEmpty()) {
            item { SectionTitle(tr("Podcasts")) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(shows) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } }
                }
            }
        }
        if (books.isNotEmpty()) {
            item { SectionTitle(tr("Audiobooks")) }
            items(books) { b ->
                Row(Modifier.fillMaxWidth().clickable { Nav.go(Screen.ShowPage(b)) }.padding(horizontal = 16.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Cover(b.image, 56.dp)
                    Spacer(Modifier.width(12.dp))
                    Column { Text(b.title, style = MaterialTheme.typography.bodyLarge); Text(b.author, style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
        if (!Library.settings.online) item { Muted(tr("You're offline: showing your own songs only.")) }
        if (note.isNotEmpty()) item { Muted(note) }
        item { Gap(24.dp) }
    }
}

/** Spotify's Browse tile: a coloured box, the name top-left, a picture tilted in the corner. */
@Composable
fun BrowseTile(name: String, colour: Color, picture: String?, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.height(100.dp).clip(RoundedCornerShape(6.dp)).background(colour).clickable(onClick = onClick)) {
        Text(name, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
             modifier = Modifier.padding(12.dp))
        if (!picture.isNullOrEmpty()) {
            Cover(picture, 64.dp, RoundedCornerShape(4.dp),
                  Modifier.align(Alignment.BottomEnd).offset(x = 14.dp, y = 4.dp).rotate(25f))
        }
    }
}

/** Lower-case without accents, for searching in any language. */
fun fold(text: String): String =
    java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFKD).replace(Regex("\\p{Mn}+"), "").lowercase()
