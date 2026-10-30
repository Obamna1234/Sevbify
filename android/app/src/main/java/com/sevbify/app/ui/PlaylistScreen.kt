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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.material.icons.filled.Close
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.outlined.ArrowCircleDown
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sevbify.app.Bridge
import com.sevbify.app.Downloads
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Track
import com.sevbify.app.toJsonArray
import org.json.JSONObject
import kotlinx.coroutines.launch

fun totalTime(tracks: List<Track>): String {
    val s = tracks.sumOf { it.durationMs } / 1000
    val h = s / 3600; val m = (s % 3600) / 60
    // Spotify's phone app: "2h 48min", or "23min 5s" under an hour.
    return if (h > 0) "${h}h ${m}min" else "${m}min ${s % 60}s"
}

/** The page shared by playlists, albums, artist songs, genre playlists...: Spotify's Android layout. */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun SongsPage(title: String, kind: String, cover: String, tracks: List<Track>, source: String,
              onMore: (() -> Unit)? = null, onSave: (() -> Unit)? = null, playlist: com.sevbify.app.Playlist? = null,
              limit: Int = 0, bottom: androidx.compose.foundation.lazy.LazyListScope.() -> Unit = {},
              extraTop: @Composable () -> Unit = {}) {
    var showAll by remember(title) { mutableStateOf(false) }
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes + Downloads.doneCount
    val colour = rememberCoverColour(cover, Color(0xFF404040))
    val pending = tracks.filter { !it.isItem && !it.isLocal && Library.localFor(it) == null }
    val playingHere = Player.sourceName == source && Player.current != null
    // Choosing songs: hold a song (or Download → Choose songs) to tick several, then download / queue / add them.
    var selection by remember(source) { mutableStateOf(setOf<Int>()) }
    var selecting by remember(source) { mutableStateOf(false) }
    var askDownload by remember(source) { mutableStateOf(false) }
    if (askDownload) DownloadChoiceSheet(title, cover, pending.size, onAll = {
        askDownload = false
        val n = Downloads.request(pending); Nav.say(if (n > 0) "Downloading $n songs" else "Already downloading")
    }, onChoose = {
        askDownload = false
        selection = tracks.indices.filter { tracks[it] in pending }.toSet(); selecting = true
    }, onDismiss = { askDownload = false })
    androidx.activity.compose.BackHandler(enabled = selecting) { selecting = false; selection = emptySet() }
    LazyColumn {
        if (selecting) {
            stickyHeader {
                SelectionBar(selection.size, tracks.size,
                    onAll = { selection = tracks.indices.toSet() }, onNone = { selection = emptySet() },
                    onDownload = {
                        val chosen = selection.sorted().map { tracks[it] }
                        val n = Downloads.request(chosen)
                        Nav.say(if (n > 0) "Downloading $n songs" else "Those songs are downloaded already")
                        selecting = false; selection = emptySet()
                    },
                    onQueue = { selection.sorted().forEach { Player.addToQueue(tracks[it]) }; Nav.say("Added ${selection.size} to queue")
                                selecting = false; selection = emptySet() },
                    onAddTo = { Nav.addTo = selection.sorted().map { tracks[it] }; selecting = false; selection = emptySet() },
                    onCancel = { selecting = false; selection = emptySet() })
            }
        }
        item {
            Column(Modifier.fillMaxWidth().background(Brush.verticalGradient(listOf(colour, C.Bg)))
                       .statusBarsPadding().padding(bottom = 8.dp)) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    when {
                        playlist != null -> PlaylistCover(playlist, 230.dp)
                        kind == "Radio" -> RadioCover(title, cover, 230.dp)
                        else -> Cover(cover, 230.dp)
                    }
                }
                Gap(16.dp)
                Text(title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(horizontal = 16.dp))
                if (kind == "Radio") {
                    // Like Spotify: "With Turboslash, Isidor, Nightstop and more"
                    val seedArtist = tracks.firstOrNull()?.artist ?: ""
                    val others = tracks.map { it.artist }.filter { it.isNotBlank() && it != seedArtist }.distinct().take(3)
                    if (others.isNotEmpty()) {
                        Text("With ${others.joinToString(", ")} and more", style = MaterialTheme.typography.bodySmall,
                             modifier = Modifier.padding(horizontal = 16.dp, vertical = 2.dp))
                    }
                }
                Gap(6.dp)
                Text(listOf(kind, "${tracks.size} songs", totalTime(tracks)).filter { it.isNotEmpty() }.joinToString(" • "),
                     style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = 16.dp))
                extraTop()
                Row(Modifier.fillMaxWidth().padding(start = 8.dp, end = 16.dp, top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (pending.isEmpty() && tracks.isNotEmpty()) {
                        IconButton(onClick = { Nav.say("Every song is downloaded") }) {
                            Icon(Icons.Filled.ArrowCircleDown, "Downloaded", tint = C.Green, modifier = Modifier.size(30.dp))
                        }
                    } else {
                        IconButton(onClick = { askDownload = true }) {
                            Icon(Icons.Outlined.ArrowCircleDown, "Download", tint = C.Sub, modifier = Modifier.size(30.dp))
                        }
                    }
                    if (onSave != null) {
                        IconButton(onClick = onSave) { Icon(Icons.Filled.Add, "Save to Your Library", tint = C.Sub, modifier = Modifier.size(28.dp)) }
                    }
                    if (onMore != null) IconButton(onClick = onMore) { Icon(Icons.Filled.MoreVert, "More", tint = C.Sub) }
                    Spacer(Modifier.weight(1f))
                    IconButton(onClick = { Player.toggleShuffle() }) {
                        Icon(Icons.Filled.Shuffle, "Shuffle", tint = if (Player.shuffle) C.Green else C.Sub, modifier = Modifier.size(28.dp))
                    }
                    Spacer(Modifier.width(8.dp))
                    GreenPlay(onClick = {
                        if (playingHere) Player.playPause() else Player.playAll(tracks, source, shuffled = Player.shuffle)
                    }, playing = playingHere && Player.isPlaying)
                }
            }
        }
        if (playlist != null) {
            item {
                Row(Modifier.fillMaxWidth().clickable { Nav.switch(Tab.SEARCH) }.padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(48.dp).clip(RoundedCornerShape(4.dp)).background(C.Card), contentAlignment = Alignment.Center) {
                        Icon(Icons.Filled.Add, null, tint = C.Sub)
                    }
                    Spacer(Modifier.width(12.dp))
                    Text("Add to this playlist", style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
        if (tracks.isEmpty()) item { Muted("No songs here yet. Search for songs and use ••• → Add to playlist.") }
        // Artist pages show the top 5 with "See more", like Spotify.
        val shown = if (limit > 0 && !showAll && !selecting) tracks.take(limit) else tracks
        itemsIndexed(shown) { i, t ->
            val toggle = { selection = if (i in selection) selection - i else selection + i }
            if (selecting) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    androidx.compose.material3.Checkbox(i in selection, { toggle() },
                        colors = androidx.compose.material3.CheckboxDefaults.colors(checkedColor = C.Green, checkmarkColor = Color.Black))
                    Box(Modifier.weight(1f)) {
                        TrackRow(t, onClick = toggle, onMore = toggle, selected = i in selection, onLongClick = toggle)
                    }
                }
            } else {
                TrackRow(t, onClick = { Player.play(t, tracks, source) },
                         onMore = { Nav.songMenu = SongMenu(t, playlist, if (playlist != null) i else -1, tracks, source) },
                         onLongClick = { selecting = true; selection = setOf(i) })
            }
        }
        if (limit > 0 && tracks.size > limit && !selecting) {
            item {
                androidx.compose.material3.TextButton(onClick = { showAll = !showAll }, modifier = Modifier.padding(start = 8.dp)) {
                    Text(if (showAll) "Show less" else "See more", color = C.Sub, fontWeight = FontWeight.Bold)
                }
            }
        }
        bottom()
        item { Gap(24.dp) }
    }
}

@Composable
fun PlaylistScreen(id: String) {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    val pl = Library.playlists.firstOrNull { it.id == id }
    if (pl == null) { Muted("This playlist was deleted."); return }
    LaunchedEffect(pl.id) {
        pl.lastPlayed = System.currentTimeMillis()
        // Imported songs often have no cover yet: look them up (a few at a time, like Windows).
        val bare = pl.tracks.withIndex().filter { !it.value.isLocal && it.value.coverUrl.isEmpty() }
        for (chunk in bare.chunked(8)) {
            try {
                val fixed = Bridge.arr("enrich", chunk.map { it.value }.toJsonArray().toString())
                chunk.forEachIndexed { j, iv ->
                    if (iv.index < pl.tracks.size && pl.tracks[iv.index].matchKey == iv.value.matchKey) {
                        val f = Track.fromJson(fixed.getJSONObject(j))
                        pl.tracks[iv.index] = iv.value.copy(coverUrl = f.coverUrl, album = iv.value.album.ifEmpty { f.album },
                                                            previewUrl = iv.value.previewUrl.ifEmpty { f.previewUrl },
                                                            durationMs = if (iv.value.durationMs > 0) iv.value.durationMs else f.durationMs)
                    }
                }
                Library.changed()
            } catch (_: Exception) { break }
        }
    }
    SongsPage(pl.name, "Playlist", playlistCover(pl), pl.tracks.toList(), pl.name, onMore = { Nav.playlistMenu = pl }, playlist = pl)
}

@Composable
fun CollectionScreen(s: Screen.Collection) {
    SongsPage(s.title, s.kind, s.cover, s.tracks, s.title,
              onSave = if (s.saveable) ({
                  val pl = Library.newPlaylist(s.title, s.tracks)
                  if (s.cover.isNotEmpty()) { pl.coverUrl = s.cover; Library.changed() }
                  Nav.say("Saved “${pl.name}” to Your Library")
              }) else null)
}

@Composable
fun YourSongsScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes
    SongsPage("Your Songs", "On your phone", "", Library.localSongs, "Your Songs") {
        if (Library.localSongs.isEmpty()) {
            Muted("No songs found. Sevbify reads the Music folder (and the folders you add in Settings) once you allow " +
                  "access to music. Downloads land in Music/Sevbify.")
        }
    }
}

@Composable
fun ToDownloadScreen() {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes + Downloads.doneCount
    SongsPage("To download", "Not downloaded yet", "", Library.toDownload(), "To download") {
        Muted("Every song in your playlists that isn't on the phone yet. When one arrives it fills its place in every playlist.")
    }
}

@Composable
fun DownloadsScreen() {
    val items = Downloads.states.toList()
    LazyColumn(Modifier.statusBarsPadding()) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Text("Downloads", style = MaterialTheme.typography.headlineMedium)
            }
        }
        item {
            Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (Downloads.paused) Chip("Resume", false) { Downloads.resume() } else Chip("Pause", false) { Downloads.pause() }
                Chip("Stop all", false) { Downloads.stopAll() }
                if (Downloads.states.values.any { it == Downloads.State.STOPPED }) Chip("Resume stopped", false) { Downloads.resume() }
            }
        }
        if (items.isEmpty()) item { Muted("Nothing is downloading.") }
        items(items) { (key, state) ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(key.substringAfter('|').ifEmpty { key }, style = MaterialTheme.typography.bodyLarge)
                    Text(state.name.lowercase().replaceFirstChar { it.uppercase() } +
                             (Downloads.notes[key]?.let { " · $it" } ?: ""), style = MaterialTheme.typography.bodySmall)
                }
                if (state == Downloads.State.FAILED || state == Downloads.State.STOPPED) Chip("Try again", false) { Downloads.retry(key) }
                Spacer(Modifier.width(8.dp))
                Chip("Cancel", false) { Downloads.cancel(key) }
            }
        }
    }
}

@Composable
fun ArtistScreen(name: String) {
    var tracks by remember { mutableStateOf<List<Track>>(emptyList()) }
    var picture by remember { mutableStateOf("") }
    var about by remember { mutableStateOf("") }
    var releases by remember { mutableStateOf<JSONObject?>(null) }
    val mine = Library.localSongs.filter { it.artist.equals(name, true) || it.artist.startsWith("$name ", true) }
    LaunchedEffect(name) {
        if (!Library.settings.online) return@LaunchedEffect
        try {
            val o = Bridge.obj("artist_top", name, 50)
            o.optJSONObject("artist")?.let { picture = it.optString("picture_xl") }
            val a = o.optJSONArray("tracks")
            if (a != null) tracks = (0 until a.length()).map { Track.fromJson(a.getJSONObject(it)) }
            about = Bridge.obj("artist_card", name).optString("summary")
        } catch (_: Exception) {}
        try { releases = Bridge.obj("artist_releases", name) } catch (_: Exception) {}
    }
    val all = tracks + mine.filter { m -> tracks.none { it.matchKey == m.matchKey } }
    SongsPage(name, "Artist", picture, all, "$name", limit = 5, bottom = {
        // Spotify's artist page: the newest releases, then albums, singles & EPs and compilations.
        val r = releases
        fun list(key: String) = r?.optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getJSONObject(it) } } ?: emptyList()
        fun year(o: JSONObject) = o.optString("release_date").take(4)
        val albums = list("albums"); val singles = list("singles"); val comps = list("compilations")
        val latest = (albums + singles).maxByOrNull { it.optString("release_date") }
        if (latest != null) {
            item { SectionTitle("Latest release") }
            item {
                Row(Modifier.fillMaxWidth().clickable { openWebAlbum(latest) }.padding(horizontal = 16.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Cover(latest.optString("cover_xl"), 72.dp)
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(latest.optString("title"), style = MaterialTheme.typography.bodyLarge, maxLines = 2)
                        Text("${kindOf(latest)} • ${year(latest)}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        for ((heading, group) in listOf("Albums" to albums, "Singles and EPs" to singles, "Compilations" to comps)) {
            if (group.isEmpty()) continue
            item { SectionTitle(heading) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(group) { a -> ShelfCard(a.optString("title"), year(a), a.optString("cover_xl")) { openWebAlbum(a) } }
                }
            }
        }
    }) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("Artist radio", false) { (mine + tracks).firstOrNull()?.let { Player.startRadio(it) } }
        }
        if (about.isNotEmpty()) Text(about, style = MaterialTheme.typography.bodySmall, maxLines = 4,
                                     modifier = Modifier.padding(horizontal = 16.dp))
    }
}

/** A Browse genre: Spotify's coloured page, from Deezer's daily charts for that genre (shared core). */
@Composable
fun GenreScreen(g: Screen.Genre) {
    var data by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(g.id) {
        try { data = Bridge.obj("genre_overview", g.id) } catch (e: Exception) { error = e.message ?: "" }
    }
    LazyColumn {
        item {
            Box(Modifier.fillMaxWidth().background(Brush.verticalGradient(listOf(Color(g.colour), C.Bg))).statusBarsPadding()) {
                Column {
                    IconButton(onClick = { Nav.back() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                    Text(g.name, fontSize = 44.sp, fontWeight = FontWeight.ExtraBold, fontFamily = Figtree, color = C.Text,
                         modifier = Modifier.padding(start = 16.dp, top = 40.dp, bottom = 16.dp))
                }
            }
        }
        val d = data
        if (d == null) { item { Muted(if (error.isNotEmpty()) "Couldn't load ${g.name}: $error" else "Loading…") }; return@LazyColumn }
        val songs = d.optJSONArray("tracks")?.let { a -> (0 until a.length()).map { Track.fromJson(a.getJSONObject(it)) } } ?: emptyList()
        if (songs.isNotEmpty()) {
            item {
                // Play / shuffle the genre's popular songs, like Spotify's genre pages.
                val source = "${g.name}: popular songs"
                val playingHere = Player.current != null && Player.sourceName == source
                Row(Modifier.fillMaxWidth().padding(start = 8.dp, end = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Spacer(Modifier.weight(1f))
                    IconButton(onClick = { Player.toggleShuffle() }) {
                        Icon(Icons.Filled.Shuffle, "Shuffle", tint = if (Player.shuffle) C.Green else C.Sub, modifier = Modifier.size(28.dp))
                    }
                    Spacer(Modifier.width(8.dp))
                    GreenPlay(onClick = {
                        if (playingHere) Player.playPause() else Player.playAll(songs, source, shuffled = Player.shuffle)
                    }, playing = playingHere && Player.isPlaying)
                }
            }
            item { SectionTitle("Popular songs") }
            items(songs.take(10)) { t ->
                TrackRow(t, onClick = { Player.play(t, songs, "${g.name}: popular songs") },
                         onMore = { Nav.songMenu = SongMenu(t, queue = songs, source = g.name) })
            }
        }
        fun shelf(title: String, key: String, image: (JSONObject) -> String, sub: (JSONObject) -> String,
                  open: (JSONObject) -> Unit, round: Boolean = false) {
            val arr = d.optJSONArray(key) ?: return
            if (arr.length() == 0) return
            val list = (0 until arr.length()).map { arr.getJSONObject(it) }
            item { SectionTitle(title) }
            item {
                LazyRow(Modifier.padding(start = 16.dp)) {
                    items(list) { o -> ShelfCard(o.optString("title", o.optString("name")), sub(o), image(o), round) { open(o) } }
                }
            }
        }
        shelf("${g.name} playlists", "playlists", { it.optString("picture_xl") }, { "${it.optInt("nb_tracks")} songs" }, { p -> openWebPlaylist(p) })
        shelf("New releases", "releases", { it.optString("cover_xl") }, { it.optJSONObject("artist")?.optString("name") ?: "" }, { a -> openWebAlbum(a) })
        shelf("Popular albums", "albums", { it.optString("cover_xl") }, { it.optJSONObject("artist")?.optString("name") ?: "" }, { a -> openWebAlbum(a) })
        shelf("Popular artists", "artists", { it.optString("picture_xl") }, { "Artist" }, { a -> Nav.go(Screen.Artist(a.optString("name"))) }, round = true)
        item { Muted("Popular right now, from Deezer's charts for this genre (they change every day).") }
        item { Gap(24.dp) }
    }
}

fun openWebPlaylist(p: JSONObject) {
    com.sevbify.app.SevbifyApp.instance.scope.launchSafely {
        val t = Bridge.tracks("playlist_tracks", p.optLong("id"))
        Nav.go(Screen.Collection("Playlist", p.optString("title"), t, p.optString("picture_xl")))
    }
}

fun openWebAlbum(a: JSONObject) {
    com.sevbify.app.SevbifyApp.instance.scope.launchSafely {
        val t = Bridge.tracks("album_tracks", a.toString())
        Nav.go(Screen.Collection("Album", a.optString("title"), t, a.optString("cover_xl")))
    }
}

fun kotlinx.coroutines.CoroutineScope.launchSafely(block: suspend () -> Unit) {
    launch {
        try { block() } catch (e: Exception) { Nav.say("⚠ ${e.message}") }
    }
}


/** Spotify's "Want to download …?" sheet, without the Premium part: everything at once, or pick the songs. */
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun DownloadChoiceSheet(title: String, cover: String, count: Int, onAll: () -> Unit, onChoose: () -> Unit, onDismiss: () -> Unit) {
    androidx.compose.material3.ModalBottomSheet(onDismissRequest = onDismiss, containerColor = C.Elevated) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp).navigationBarsPadding(),
               horizontalAlignment = Alignment.CenterHorizontally) {
            Cover(cover, 150.dp)
            Gap(16.dp)
            Text("Download $title?", style = MaterialTheme.typography.headlineSmall, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            Gap(6.dp)
            Muted("$count songs aren't on your phone yet. They're saved to Music/Sevbify so they play without internet " +
                  "(and in other music apps).")
            Gap(16.dp)
            androidx.compose.material3.Button(onClick = onAll, colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                containerColor = C.Green, contentColor = Color.Black), modifier = Modifier.fillMaxWidth()) { Text("Download all $count") }
            Gap(8.dp)
            androidx.compose.material3.OutlinedButton(onClick = onChoose, modifier = Modifier.fillMaxWidth()) {
                Text("Choose songs", color = C.Text)
            }
            Gap(16.dp)
        }
    }
}

/** Shown while choosing songs: how many, select all / none, and what to do with them. */
@Composable
private fun SelectionBar(count: Int, total: Int, onAll: () -> Unit, onNone: () -> Unit, onDownload: () -> Unit,
                         onQueue: () -> Unit, onAddTo: () -> Unit, onCancel: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(C.Elevated).statusBarsPadding().padding(horizontal = 8.dp, vertical = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onCancel) { Icon(Icons.Filled.Close, "Stop choosing") }
            Text("$count selected", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            androidx.compose.material3.TextButton(onClick = if (count == total) onNone else onAll) {
                Text(if (count == total) "Select none" else "Select all", color = C.Green)
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            androidx.compose.material3.Button(onClick = onDownload, enabled = count > 0,
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black),
                modifier = Modifier.weight(1f)) { Text("Download") }
            androidx.compose.material3.OutlinedButton(onClick = onQueue, enabled = count > 0, modifier = Modifier.weight(1f)) {
                Text("Queue", color = C.Text, maxLines = 1)
            }
            androidx.compose.material3.OutlinedButton(onClick = onAddTo, enabled = count > 0, modifier = Modifier.weight(1f)) {
                Text("Add to…", color = C.Text, maxLines = 1)
            }
        }
    }
}

/** A song radio's picture, like Spotify's: the song's cover darkened, with RADIO and the song's name on it. */
@Composable
fun RadioCover(title: String, cover: String, size: Dp) {
    Box(Modifier.size(size).clip(RoundedCornerShape(4.dp))) {
        Cover(cover, size, RoundedCornerShape(0.dp))
        Box(Modifier.matchParentSize().background(Brush.verticalGradient(listOf(Color(0x33000000), Color(0xCC000000)))))
        Column(Modifier.align(Alignment.BottomStart).padding(14.dp)) {
            Text("RADIO", fontSize = 13.sp, fontWeight = FontWeight.ExtraBold, color = C.Green, letterSpacing = 2.sp)
            Text(title.removeSuffix(" Radio"), fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, fontFamily = Figtree,
                 color = Color.White, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

private fun kindOf(a: JSONObject) = when (a.optString("record_type")) {
    "single" -> "Single"; "ep" -> "EP"; "compile" -> "Compilation"; else -> "Album"
}
