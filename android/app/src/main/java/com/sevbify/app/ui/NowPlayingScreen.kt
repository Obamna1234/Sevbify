package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.height
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
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.RepeatOne
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material.icons.filled.AutoAwesome
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
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.CheckCircle
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
    // Like Spotify: the player fills the screen; scroll down for the lyrics preview.
    LazyColumn(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(colour, Color(0xFF121212))))
                   .statusBarsPadding().navigationBarsPadding()) {
    val canvasOn = com.sevbify.app.CanvasLoop.current != null && !Player.videoMode && !com.sevbify.app.CanvasLoop.showCover
    item {
    // Canvas, like Spotify's: the loop fills the whole player behind everything, darker at the top and bottom so the
    // words and buttons stay readable, and the cover moves next to the song's name.
    Box(Modifier.fillParentMaxHeight().fillMaxWidth()) {
    if (canvasOn) {
        CanvasView(Modifier.matchParentSize())
        Box(Modifier.matchParentSize().background(Brush.verticalGradient(
            0f to Color(0x99000000), 0.18f to Color.Transparent, 0.5f to Color.Transparent, 0.72f to Color(0xCC000000), 1f to Color(0xEE000000))))
    }
    Column(Modifier.fillMaxSize().padding(horizontal = 20.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Nav.nowPlayingOpen = false }) { Icon(Icons.Filled.KeyboardArrowDown, "Close", Modifier.size(32.dp), tint = C.Text) }
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(tr("PLAYING FROM"), style = MaterialTheme.typography.labelSmall.copy(color = C.Text))
                Text(Player.sourceName.ifEmpty { "Sevbify" }, maxLines = 1, overflow = TextOverflow.Ellipsis,
                     style = MaterialTheme.typography.labelLarge)
            }
            IconButton(onClick = { Nav.songMenu = SongMenu(t, queue = Player.context.toList(), source = Player.sourceName) }) {
                Icon(Icons.Filled.MoreVert, "More", tint = C.Text)
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
                    // (In full screen the picture is shown there: one player can only draw on one screen.)
                    if (!com.sevbify.app.VideoPlayer.fullscreen) {
                        VideoSurface(showControls = false)
                        VideoControls(fullscreen = false)
                    }
                }
                val v = com.sevbify.app.VideoPlayer
                Text(v.error.ifEmpty { "Pinch to fill the screen, double-tap the sides to skip 10 s. Close this screen and the video keeps playing in a small window." +
                         (v.height.takeIf { it > 0 }?.let { " Playing ${it}p." } ?: "") },
                     style = MaterialTheme.typography.bodySmall.copy(color = if (v.error.isNotEmpty()) C.Red else C.Sub),
                     textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp))
            } else if (!canvasOn) {
                Cover(t.art, 340.dp, RoundedCornerShape(8.dp), Modifier.aspectRatio(1f))
            }
            if (com.sevbify.app.CanvasLoop.current != null && !Player.videoMode) {
                if (canvasOn) Spacer(Modifier.weight(1f))
                CanvasCoverSwitch(Modifier.padding(top = 16.dp))
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (canvasOn) { Cover(t.art, 48.dp, RoundedCornerShape(4.dp)); Spacer(Modifier.size(12.dp)) }
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
            val saved = isSaved(t)
            IconButton(onClick = { saveTap(t) }) {
                Icon(if (saved) Icons.Filled.CheckCircle else Icons.Filled.AddCircleOutline, if (saved) "Saved in…" else "Add to Liked Songs",
                     tint = if (saved) C.Green else C.Sub, modifier = Modifier.size(28.dp))
            }
        }
        val d = Player.duration.coerceAtLeast(1)
        SeekBar(progress = (Player.position.toFloat() / d).coerceIn(0f, 1f),
                onSeek = { Player.seekTo((it * d).toLong()) },
                onDrag = { v -> dragging = v != null; if (v != null) dragValue = v })
        Row {
            Text(clock(if (dragging) (dragValue * d).toLong() else Player.position), style = MaterialTheme.typography.labelSmall)
            Spacer(Modifier.weight(1f))
            Text(clock(Player.duration), style = MaterialTheme.typography.labelSmall)
        }
        Box(Modifier.fillMaxWidth().height(18.dp), contentAlignment = Alignment.Center) {      // fixed height: no jump
            if (Player.status.isNotEmpty()) {
                Text(Player.status, style = MaterialTheme.typography.labelSmall, maxLines = 1, textAlign = TextAlign.Center,
                     modifier = Modifier.fillMaxWidth())
            }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Player.toggleShuffle() }) {
                Icon(if (Player.smartShuffle) Icons.Filled.AutoAwesome else Icons.Filled.Shuffle, if (Player.smartShuffle) "Smart Shuffle" else "Shuffle", tint = if (Player.shuffle) C.Green else C.Text)
            }
            IconButton(onClick = { Player.previous() }) { Icon(Icons.Filled.SkipPrevious, "Previous", Modifier.size(40.dp), tint = C.Text) }
            Surface(onClick = { Player.playPause() }, shape = CircleShape, color = Color.White, modifier = Modifier.size(68.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(if (Player.showPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                         if (Player.showPlaying) "Pause" else "Play", tint = Color.Black, modifier = Modifier.size(38.dp))
                }
            }
            IconButton(onClick = { Player.next() }) { Icon(Icons.Filled.SkipNext, "Next", Modifier.size(40.dp), tint = C.Text) }
            IconButton(onClick = { Player.cycleRepeat() }) {
                Icon(if (Player.repeat == "one") Icons.Filled.RepeatOne else Icons.Filled.Repeat, "Repeat",
                     tint = if (Player.repeat == "off") C.Text else C.Green)
            }
        }
        Row(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Nav.connectOpen = true }) {
                Icon(Icons.Filled.Devices, "Connect to a device",
                     tint = if (AudioOutput.kind != "speaker") C.Green else C.Text)
            }
            if (AudioOutput.kind != "speaker") {
                Text(AudioOutput.name, color = C.Green, style = MaterialTheme.typography.labelMedium, maxLines = 1,
                     overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            } else Spacer(Modifier.weight(1f))
            IconButton(onClick = { Nav.shareFor = t }) { Icon(Icons.Filled.Share, "Share", tint = C.Text) }
            IconButton(onClick = { Nav.queueOpen = true }) { Icon(Icons.AutoMirrored.Filled.QueueMusic, "Queue", tint = C.Text) }
        }
    }
    }
    }
    item { LyricsCard(t) }
    item { Gap(24.dp) }
    }
    if (Nav.queueOpen) QueueSheet()
}

/** Canvas or the cover: a small switch under the picture whenever this song has a Canvas loop. */
@Composable
private fun CanvasCoverSwitch(modifier: Modifier = Modifier) {
    val cover = com.sevbify.app.CanvasLoop.showCover
    Row(modifier.clip(RoundedCornerShape(50)).background(Color(0x55000000)).padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        listOf(false to "Canvas", true to "Cover").forEach { (isCover, label) ->
            val on = cover == isCover
            Box(Modifier.clip(RoundedCornerShape(50)).background(if (on) Color.White else Color.Transparent)
                    .clickable(enabled = !on) { com.sevbify.app.CanvasLoop.showCover = isCover }
                    .padding(horizontal = 16.dp, vertical = 6.dp)) {
                Text(tr(label), color = if (on) Color.Black else C.Text, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QueueSheet() {
    // Spotify's queue: what's playing and from where, what's next, and Shuffle / Repeat / Timer along the bottom.
    ModalBottomSheet(onDismissRequest = { Nav.queueOpen = false }, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Box(Modifier.fillMaxWidth().navigationBarsPadding()) {
            LazyColumn(Modifier.fillMaxWidth().padding(bottom = 76.dp)) {
                item {
                    Column(Modifier.padding(horizontal = 16.dp)) {
                        Text(tr("Queue"), style = MaterialTheme.typography.titleLarge)
                        val from = Player.sourceName.ifEmpty { "Sevbify" }
                        val where = if (AudioOutput.kind != "speaker") " · ${AudioOutput.name}" else ""
                        Text("Playing from $from$where", style = MaterialTheme.typography.bodySmall, maxLines = 1,
                             overflow = TextOverflow.Ellipsis)
                    }
                }
                Player.current?.let { cur ->
                    item { SectionTitle(tr("Now playing")) }
                    item { TrackRow(cur, onClick = {}, onMore = { Nav.songMenu = SongMenu(cur) }) }
                }
                if (Player.userQueue.isNotEmpty()) {
                    item { SectionTitle(tr("Next in queue")) }
                    itemsIndexed(Player.userQueue.toList()) { i, t ->
                        TrackRow(t, onClick = {}, onMore = { Player.removeFromQueue(i) })
                    }
                }
                val rest = Player.context.drop(Player.index + 1)
                if (rest.isNotEmpty()) {
                    item { SectionTitle((if (Player.shuffle) "Shuffling from: " else "Next from: ") + Player.sourceName) }
                    itemsIndexed(rest.take(100)) { i, t ->
                        TrackRow(t, onClick = { Player.jumpTo(Player.index + 1 + i) }, onMore = { Nav.songMenu = SongMenu(t) })
                    }
                }
                item { Gap(24.dp) }
            }
            Row(Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(C.Elevated).padding(horizontal = 16.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                QueueButton(if (Player.smartShuffle) Icons.Filled.AutoAwesome else Icons.Filled.Shuffle,
                            if (Player.smartShuffle) "Smart Shuffle" else "Shuffle", Player.shuffle, Modifier.weight(1f)) { Player.toggleShuffle() }
                QueueButton(if (Player.repeat == "one") Icons.Filled.RepeatOne else Icons.Filled.Repeat, "Repeat",
                            Player.repeat != "off", Modifier.weight(1f)) { Player.cycleRepeat() }
                QueueButton(Icons.Filled.Timer, "Timer", Player.sleepAt != null || Player.sleepAtEnd, Modifier.weight(1f)) { Nav.sleepOpen = true }
            }
        }
    }
}

@Composable
private fun QueueButton(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, on: Boolean,
                        modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.clip(RoundedCornerShape(8.dp)).background(Color(0x22FFFFFF)).clickable(onClick = onClick).padding(vertical = 8.dp),
           horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, label, tint = if (on) C.Green else C.Text)
        Text(tr(label), style = MaterialTheme.typography.labelSmall, color = if (on) C.Green else C.Text)
    }
}
