package com.sevbify.app.ui

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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.outlined.ArrowCircleDown
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Bridge
import com.sevbify.app.Downloads
import com.sevbify.app.Episode
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Show
import com.sevbify.app.Track
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
private fun PageTop(title: String) {
    Row(Modifier.statusBarsPadding(), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
        Text(title, style = MaterialTheme.typography.headlineMedium)
    }
}

/** Podcasts: Apple's directory (search, Top podcasts) and a box for a YouTube channel or RSS link. */
@Composable
fun PodcastsScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    var query by rememberSaveable { mutableStateOf("") }
    var link by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<Show>>(emptyList()) }
    var top by remember { mutableStateOf<List<Show>>(emptyList()) }
    val scope = rememberCoroutineScope()
    val country = java.util.Locale.getDefault().country.lowercase().ifEmpty { "us" }
    LaunchedEffect(Unit) {
        try { val a = Bridge.arr("top_shows", country); top = (0 until a.length()).map { Show(a.getJSONObject(it)) } } catch (_: Exception) {}
    }
    LazyColumn {
        item { PageTop("Podcasts") }
        item {
            OutlinedTextField(query, { query = it }, singleLine = true, placeholder = { Text("What do you want to listen to?") },
                              keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                              keyboardActions = KeyboardActions(onSearch = {
                                  scope.launch {
                                      try { val a = Bridge.arr("search_podcasts", query, country); results = (0 until a.length()).map { Show(a.getJSONObject(it)) } }
                                      catch (e: Exception) { Nav.say("⚠ ${e.message}") }
                                  }
                              }),
                              modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        }
        item {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(link, { link = it }, singleLine = true, placeholder = { Text("YouTube channel or RSS link") },
                                  modifier = Modifier.weight(1f))
                Spacer(Modifier.width(8.dp))
                OutlinedButton(onClick = {
                    scope.launch {
                        try { Nav.go(Screen.ShowPage(Show(Bridge.obj("show_link", link)))) } catch (e: Exception) { Nav.say("⚠ ${e.message}") }
                    }
                }) { Text("Open", color = C.Text) }
            }
        }
        val mine = Library.shows.filter { !it.isBook }
        if (mine.isNotEmpty()) {
            item { SectionTitle("Your shows") }
            item { LazyRow(Modifier.padding(start = 16.dp)) { items(mine) { s -> ShelfCard(s.title, s.author, s.image) { Nav.go(Screen.ShowPage(s)) } } } }
        }
        if (results.isNotEmpty()) {
            item { SectionTitle("Results") }
            items(results) { s -> ShowRow(s) }
        }
        if (top.isNotEmpty()) {
            item { SectionTitle("Top podcasts") }
            items(top) { s -> ShowRow(s) }
        }
        if (!Library.settings.online) item { Muted("You're offline. Downloaded episodes still play from Your Library.") }
        item { Gap(24.dp) }
    }
}

/** Free public-domain audiobooks from LibriVox (Internet Archive). */
@Composable
fun AudiobooksScreen() {
    var query by rememberSaveable { mutableStateOf("") }
    var books by remember { mutableStateOf<List<Show>>(emptyList()) }
    var heading by remember { mutableStateOf("Popular free audiobooks") }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        try { val a = Bridge.arr("books", "popular", ""); books = (0 until a.length()).map { Show(a.getJSONObject(it)) } } catch (_: Exception) {}
    }
    LazyColumn {
        item { PageTop("Audiobooks") }
        item {
            OutlinedTextField(query, { query = it }, singleLine = true, placeholder = { Text("Search by title or author") },
                              keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                              keyboardActions = KeyboardActions(onSearch = {
                                  scope.launch {
                                      try { val a = Bridge.arr("books", "search", query); books = (0 until a.length()).map { Show(a.getJSONObject(it)) }; heading = "Results" }
                                      catch (e: Exception) { Nav.say("⚠ ${e.message}") }
                                  }
                              }),
                              modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp))
        }
        item { Muted("Free audiobooks of public-domain books, read by LibriVox volunteers.") }
        item { SectionTitle(heading) }
        items(books) { b -> ShowRow(b) }
        item { Gap(24.dp) }
    }
}

@Composable
private fun ShowRow(s: Show) {
    Row(Modifier.fillMaxWidth().clickable { Nav.go(Screen.ShowPage(s)) }.padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Cover(s.image, 64.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(s.title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyLarge)
            Text(s.author, maxLines = 1, style = MaterialTheme.typography.bodySmall)
        }
    }
}

/** A podcast, YouTube channel or audiobook: Follow, episodes newest first (or oldest), download, continue. */
@Composable
fun ShowScreen(start: Show) {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes + Downloads.doneCount
    var show by remember { mutableStateOf(start) }
    var episodes by remember { mutableStateOf<List<Episode>>(emptyList()) }
    var note by remember { mutableStateOf("Loading…") }
    var source by remember { mutableStateOf("") }
    var newest by rememberSaveable { mutableStateOf(true) }
    LaunchedEffect(start.key) {
        try {
            if (start.isBook) {
                val a = Bridge.arr("book_chapters", start.json.toString())
                episodes = (0 until a.length()).map { Episode(Track.fromJson(a.getJSONObject(it)), it.toDouble(), "", "") }
            } else {
                val o = Bridge.obj("fetch_show", start.json.toString())
                show = Show(o.getJSONObject("show"))
                source = o.optString("note")
                val a = o.getJSONArray("episodes")
                episodes = (0 until a.length()).map { i ->
                    val e = a.getJSONObject(i)
                    Episode(Track.fromJson(e.getJSONObject("track")), e.optDouble("published"), e.optString("date"), e.optString("description"))
                }
            }
            note = if (episodes.isEmpty()) "No episodes found." else ""
        } catch (e: Exception) {
            note = if (Library.settings.online) "Couldn't load this: ${e.message}" else "You're offline."
        }
    }
    val sorted = if (start.isBook) episodes else episodes.sortedBy { if (newest) -it.published else it.published }
    val items = sorted.map { it.track }
    val colour = rememberCoverColour(show.image, Color(0xFF2D4A5A))
    LazyColumn {
        item {
            Column(Modifier.fillMaxWidth().background(Brush.verticalGradient(listOf(colour, C.Bg))).statusBarsPadding()) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.Bottom) {
                    Cover(show.image, 140.dp)
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(show.title, style = MaterialTheme.typography.headlineMedium, maxLines = 3, overflow = TextOverflow.Ellipsis)
                        Text(show.author, style = MaterialTheme.typography.bodyMedium.copy(color = C.Sub))
                    }
                }
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    val following = Library.follows(show.key)
                    OutlinedButton(onClick = { if (following) Library.unfollow(show.key) else Library.follow(show) }) {
                        Text(if (following) (if (start.isBook) "In Your Library" else "Following")
                             else (if (start.isBook) "Add to Your Library" else "Follow"), color = C.Text)
                    }
                    if (start.isBook && items.isNotEmpty()) {
                        IconButton(onClick = { val n = Downloads.request(items); Nav.say("Downloading $n chapters") }) {
                            Icon(Icons.Outlined.ArrowCircleDown, "Download the book", tint = C.Sub, modifier = Modifier.size(28.dp))
                        }
                    }
                    Spacer(Modifier.weight(1f))
                    if (items.isNotEmpty()) GreenPlay(onClick = {
                        val first = items.firstOrNull { it.itemKey !in Library.finished } ?: items.first()
                        Player.play(first, items, show.title)
                    })
                }
                if (source.isNotEmpty() && show.isYoutube) Muted(source)
                if (show.description.isNotEmpty()) {
                    Text(show.description, maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
                         modifier = Modifier.padding(horizontal = 16.dp))
                }
            }
        }
        if (!start.isBook && episodes.size > 1) {
            item {
                Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Chip("Newest first", newest) { newest = true }
                    Chip("Oldest first", !newest) { newest = false }
                }
            }
        }
        if (note.isNotEmpty()) item { Muted(note) }
        items(sorted) { e -> EpisodeRow(e, items, show) }
        item { Gap(24.dp) }
    }
}

@Composable
private fun EpisodeRow(e: Episode, all: List<Track>, show: Show) {
    val t = e.track
    val playing = Player.current?.itemKey == t.itemKey
    val downloaded = Library.offline[t.itemKey]?.let { java.io.File(it).exists() } == true
    val state = Downloads.stateOf(t)
    val left = Library.resume[t.itemKey]?.let { t.durationMs - it }?.takeIf { it > 0 && t.durationMs > 0 }
    Column(Modifier.fillMaxWidth().clickable { Player.play(t, all, show.title) }.padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(t.title, maxLines = 2, overflow = TextOverflow.Ellipsis,
             style = MaterialTheme.typography.titleSmall.copy(color = if (playing) C.Green else C.Text))
        if (e.description.isNotEmpty()) {
            Text(e.description, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            val bits = listOfNotNull(e.date.ifEmpty { null },
                                     left?.let { "${it / 60000} min left" } ?: t.durationMs.takeIf { it > 0 }?.let { "${it / 60000} min" },
                                     if (t.itemKey in Library.finished) "Played" else null)
            Text(bits.joinToString(" • "), style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            IconButton(onClick = {
                if (!downloaded) { Downloads.request(listOf(t)); Nav.say("Downloading ${t.title}") }
            }) {
                Icon(when { downloaded -> Icons.Filled.ArrowCircleDown; else -> Icons.Outlined.ArrowCircleDown },
                     if (downloaded) "Downloaded" else "Download",
                     tint = if (downloaded) C.Green else if (state != null) C.Text else C.Sub)
            }
            Surface(onClick = { Player.play(t, all, show.title) }, shape = androidx.compose.foundation.shape.CircleShape, color = Color.White,
                    modifier = Modifier.size(32.dp)) {
                Box(contentAlignment = Alignment.Center) { Icon(Icons.Filled.PlayArrow, "Play", tint = Color.Black) }
            }
        }
    }
}

