package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.RepeatOne
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.outlined.ArrowCircleDown
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Downloads
import com.sevbify.app.Library
import com.sevbify.app.Player

fun clock(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, (s % 3600) / 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
}

/** Spotify's full-screen player on Android. */
@Composable
fun NowPlayingScreen() {
    val t = Player.current ?: run { Nav.nowPlayingOpen = false; return }
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes + Downloads.doneCount
    val colour = rememberCoverColour(t.art, Color(0xFF404040))
    var dragging by remember { mutableStateOf(false) }
    var dragValue by remember { mutableFloatStateOf(0f) }
    val have = t.isLocal || Library.localFor(t) != null
    Column(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(colour, Color(0xFF121212))))
               .statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Nav.nowPlayingOpen = false }) { Icon(Icons.Filled.KeyboardArrowDown, "Close", Modifier.size(32.dp)) }
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("PLAYING FROM", style = MaterialTheme.typography.labelSmall.copy(color = C.Text))
                Text(Player.sourceName.ifEmpty { "Sevbify" }, maxLines = 1, overflow = TextOverflow.Ellipsis,
                     style = MaterialTheme.typography.labelLarge)
            }
            IconButton(onClick = { Nav.songMenu = SongMenu(t, queue = Player.context.toList(), source = Player.sourceName) }) {
                Icon(Icons.Filled.MoreVert, "More")
            }
        }
        Column(Modifier.weight(1f).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally,
               verticalArrangement = Arrangement.Center) {
            if (Player.canWatch(t)) {
                AudioVideoSwitch()        // cover art or the video, like Spotify's video podcasts
                Spacer(Modifier.size(16.dp))
            }
            if (Player.videoMode) {
                Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f).clip(RoundedCornerShape(8.dp)).background(Color.Black),
                    contentAlignment = Alignment.Center) {
                    VideoSurface(showControls = false)
                    if (com.sevbify.app.VideoPlayer.loading) androidx.compose.material3.CircularProgressIndicator(color = C.Green)
                }
                val v = com.sevbify.app.VideoPlayer
                Text(v.error.ifEmpty { "Close this screen and the video keeps playing in a small window you can move and resize." +
                         (v.height.takeIf { it > 0 }?.let { " Playing ${it}p." } ?: "") },
                     style = MaterialTheme.typography.bodySmall.copy(color = if (v.error.isNotEmpty()) C.Red else C.Sub),
                     textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp))
            } else {
                Cover(t.art, 340.dp, RoundedCornerShape(8.dp), Modifier.aspectRatio(1f))
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleLarge)
                Text(t.artist, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyLarge.copy(color = C.Sub),
                     modifier = Modifier.clickable { Nav.nowPlayingOpen = false; Nav.go(Screen.Artist(t.artist)) })
            }
            if (!t.isItem) {
                IconButton(onClick = {
                    if (!have) { Downloads.request(listOf(t)); Nav.say("Downloading ${t.title}") }
                }) {
                    Icon(if (have) Icons.Filled.ArrowCircleDown else Icons.Outlined.ArrowCircleDown,
                         if (have) "Downloaded" else "Download", tint = if (have) C.Green else C.Sub, modifier = Modifier.size(28.dp))
                }
            }
            IconButton(onClick = { Nav.addTo = listOf(t) }) {
                Icon(Icons.Filled.AddCircleOutline, "Add to playlist", tint = C.Sub, modifier = Modifier.size(28.dp))
            }
        }
        val d = Player.duration.coerceAtLeast(1)
        Slider(value = if (dragging) dragValue else (Player.position.toFloat() / d).coerceIn(0f, 1f),
               onValueChange = { dragging = true; dragValue = it },
               onValueChangeFinished = { Player.seekTo((dragValue * d).toLong()); dragging = false },
               colors = SliderDefaults.colors(thumbColor = Color.White, activeTrackColor = Color.White,
                                              inactiveTrackColor = Color(0x4DFFFFFF)))
        Row {
            Text(clock(if (dragging) (dragValue * d).toLong() else Player.position), style = MaterialTheme.typography.labelSmall)
            Spacer(Modifier.weight(1f))
            Text(clock(Player.duration), style = MaterialTheme.typography.labelSmall)
        }
        if (Player.status.isNotEmpty()) {
            Text(Player.status, style = MaterialTheme.typography.labelSmall, maxLines = 1, textAlign = TextAlign.Center,
                 modifier = Modifier.fillMaxWidth())
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Player.toggleShuffle() }) {
                Icon(Icons.Filled.Shuffle, "Shuffle", tint = if (Player.shuffle) C.Green else C.Text)
            }
            IconButton(onClick = { Player.previous() }) { Icon(Icons.Filled.SkipPrevious, "Previous", Modifier.size(40.dp)) }
            Surface(onClick = { Player.playPause() }, shape = CircleShape, color = Color.White, modifier = Modifier.size(68.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(if (Player.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                         if (Player.isPlaying) "Pause" else "Play", tint = Color.Black, modifier = Modifier.size(38.dp))
                }
            }
            IconButton(onClick = { Player.next() }) { Icon(Icons.Filled.SkipNext, "Next", Modifier.size(40.dp)) }
            IconButton(onClick = { Player.cycleRepeat() }) {
                Icon(if (Player.repeat == "one") Icons.Filled.RepeatOne else Icons.Filled.Repeat, "Repeat",
                     tint = if (Player.repeat == "off") C.Text else C.Green)
            }
        }
        Row(Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { Nav.queueOpen = true }) { Icon(Icons.AutoMirrored.Filled.QueueMusic, "Queue") }
        }
    }
    if (Nav.queueOpen) QueueSheet()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QueueSheet() {
    ModalBottomSheet(onDismissRequest = { Nav.queueOpen = false }, containerColor = C.Elevated) {
        LazyColumn(Modifier.navigationBarsPadding()) {
            item { Text("Queue", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 16.dp)) }
            Player.current?.let { cur ->
                item { SectionTitle("Now playing") }
                item { TrackRow(cur, onClick = {}, onMore = { Nav.songMenu = SongMenu(cur) }) }
            }
            if (Player.userQueue.isNotEmpty()) {
                item { SectionTitle("Next in queue") }
                itemsIndexed(Player.userQueue.toList()) { i, t ->
                    TrackRow(t, onClick = {}, onMore = { Player.userQueue.removeAt(i) })
                }
            }
            val rest = Player.context.drop(Player.index + 1)
            if (rest.isNotEmpty()) {
                item { SectionTitle("Next from: ${Player.sourceName}") }
                itemsIndexed(rest.take(100)) { i, t ->
                    TrackRow(t, onClick = { Player.jumpTo(Player.index + 1 + i) }, onMore = { Nav.songMenu = SongMenu(t) })
                }
            }
            item { Gap(24.dp) }
        }
    }
}

