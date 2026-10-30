package com.sevbify.app.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowCircleDown
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.outlined.ArrowCircleDown
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.SubcomposeAsyncImage
import com.sevbify.app.Downloads
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Track

/** A cover picture (from the web or the phone), with Spotify's grey music-note box while it loads. */
@Composable
fun Cover(url: String?, size: Dp, shape: Shape = RoundedCornerShape(4.dp), modifier: Modifier = Modifier) {
    val box = modifier.size(size).clip(shape)
    if (url.isNullOrEmpty()) {
        Placeholder(box, size)
        return
    }
    SubcomposeAsyncImage(model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = box,
                         loading = { Placeholder(Modifier.fillMaxSize(), size) },
                         error = { Placeholder(Modifier.fillMaxSize(), size) })
}

@Composable
private fun Placeholder(modifier: Modifier, size: Dp) {
    Box(modifier.background(C.Card), contentAlignment = Alignment.Center) {
        Icon(Icons.Filled.MusicNote, null, tint = C.Dim, modifier = Modifier.size(size * 0.45f))
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.titleLarge, modifier = modifier.padding(start = 16.dp, end = 16.dp,
                                                                                         top = 24.dp, bottom = 12.dp))
}

/** Spotify's filter chip: grey pill, green when chosen. */
@Composable
fun Chip(text: String, selected: Boolean, onClick: () -> Unit) {
    Surface(onClick = onClick, shape = RoundedCornerShape(50), color = if (selected) C.Green else C.Card) {
        Text(text, style = MaterialTheme.typography.labelMedium.copy(fontSize = 13.sp),
             color = if (selected) C.Black else C.Text, maxLines = 1, softWrap = false,
             modifier = Modifier.padding(horizontal = 14.dp, vertical = 7.dp))
    }
}

/**
 * One song in a list, like Spotify's Android rows: cover, title (green while playing), a small ⬇ when it isn't
 * downloaded (green when it is, for songs you streamed and saved), the artist, and ••• for the song's menu.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TrackRow(t: Track, onClick: () -> Unit, onMore: () -> Unit, number: Int? = null, selected: Boolean = false,
             onLongClick: (() -> Unit)? = null, showCover: Boolean = true) {
    @Suppress("UNUSED_VARIABLE") val tick = Library.changes + Downloads.doneCount
    val playing = Player.current?.matchKey == t.matchKey
    val have = t.isLocal || Library.localFor(t) != null
    val state = Downloads.stateOf(t)
    Row(Modifier.fillMaxWidth().background(if (selected) C.Highlight else C.Bg)
            .combinedClickable(onClick = onClick, onLongClick = onLongClick ?: onMore)
            .padding(start = 16.dp, end = 4.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically) {
        if (number != null) {
            Text("$number", style = MaterialTheme.typography.bodySmall, modifier = Modifier.width(28.dp))
        }
        if (showCover) {
            Cover(t.art, 48.dp)
            Spacer(Modifier.width(12.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis,
                 style = MaterialTheme.typography.bodyLarge.copy(color = if (playing) C.Green else C.Text))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (have && !t.isLocal) {
                    Icon(Icons.Filled.ArrowCircleDown, "Downloaded", tint = C.Green, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(4.dp))
                } else if (!have && !t.isItem) {
                    Icon(Icons.Outlined.ArrowCircleDown, "Not downloaded", tint = C.Dim, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(4.dp))
                }
                if (t.explicit) {
                    Box(Modifier.background(C.Sub, RoundedCornerShape(2.dp)).padding(horizontal = 3.dp)) {
                        Text("E", fontSize = 9.sp, fontWeight = FontWeight.Bold, color = C.Black)
                    }
                    Spacer(Modifier.width(4.dp))
                }
                val sub = when (state) {
                    Downloads.State.DOWNLOADING -> "Downloading…"
                    Downloads.State.QUEUED -> "Waiting to download"
                    Downloads.State.FAILED -> "Download failed" +
                        (Downloads.notes[if (t.isItem) t.itemKey else t.matchKey]?.let { ": " + it.take(80) } ?: "")
                    Downloads.State.STOPPED -> "Download stopped"
                    null -> t.artist
                }
                Text(sub, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
                     color = if (state == Downloads.State.FAILED) C.Red else C.Sub)
            }
        }
        IconButton(onClick = onMore) { Icon(Icons.Filled.MoreVert, "More", tint = C.Sub) }
    }
}

/** The big green round play button. */
@Composable
fun GreenPlay(onClick: () -> Unit, size: Dp = 52.dp, playing: Boolean = false) {
    Surface(onClick = onClick, shape = CircleShape, color = C.Green, modifier = Modifier.size(size)) {
        Box(contentAlignment = Alignment.Center) {
            Icon(if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                 if (playing) "Pause" else "Play", tint = C.Black, modifier = Modifier.size(size * 0.55f))
        }
    }
}

@Composable
fun Muted(text: String, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.bodySmall, modifier = modifier.padding(horizontal = 16.dp, vertical = 8.dp))
}

@Composable
fun Gap(h: Dp = 8.dp) = Spacer(Modifier.height(h))

/** A square card for shelves (album, playlist, show, book) - round for artists. */
@Composable
fun ShelfCard(title: String, subtitle: String, image: String?, round: Boolean = false, onClick: () -> Unit) {
    Column(Modifier.width(150.dp).clip(RoundedCornerShape(6.dp))
               .combinedClickableCompat(onClick).padding(end = 12.dp)) {
        Cover(image, 140.dp, if (round) CircleShape else RoundedCornerShape(4.dp))
        Gap(8.dp)
        Text(title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall)
        if (subtitle.isNotEmpty()) {
            Text(subtitle, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
fun Modifier.combinedClickableCompat(onClick: () -> Unit, onLongClick: (() -> Unit)? = null): Modifier =
    this.combinedClickable(onClick = onClick, onLongClick = onLongClick)

val Pill = RoundedCornerShape(50)
val Rows = Arrangement.spacedBy(8.dp)


/** Top-left of Home and Your Library (where Spotify shows your profile picture): Sevbify has no accounts, so
 *  it's the Sevbify logo, and it opens Settings. */
@androidx.compose.runtime.Composable
fun SettingsBadge() {
    androidx.compose.foundation.Image(
        androidx.compose.ui.res.painterResource(com.sevbify.app.R.drawable.sevbify_logo), "Settings",
        modifier = androidx.compose.ui.Modifier.size(32.dp).clip(androidx.compose.foundation.shape.CircleShape)
            .clickable { Nav.go(Screen.Settings) })
}

/** Spotify's progress bar: a thin line (white played, grey left) with a small round dot that grows while you drag.
 *  Tap or drag anywhere on it to move through the song. `onSeek` gets 0..1 when you let go. */
@Composable
fun SeekBar(progress: Float, onSeek: (Float) -> Unit, onDrag: (Float?) -> Unit = {}, modifier: Modifier = Modifier) {
    var width by androidx.compose.runtime.remember { androidx.compose.runtime.mutableIntStateOf(1) }
    var drag by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf<Float?>(null) }
    val shown = (drag ?: progress).coerceIn(0f, 1f)
    fun at(x: Float) = (x / width.coerceAtLeast(1)).coerceIn(0f, 1f)
    androidx.compose.foundation.Canvas(
        modifier.fillMaxWidth().height(24.dp)
            .onSizeChanged { width = it.width }
            .pointerInput(Unit) {
                detectTapGestures { o -> onSeek(at(o.x)) }
            }
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragStart = { o -> drag = at(o.x); onDrag(drag) },
                    onHorizontalDrag = { change, _ -> drag = at(change.position.x); onDrag(drag) },
                    onDragEnd = { drag?.let(onSeek); drag = null; onDrag(null) },
                    onDragCancel = { drag = null; onDrag(null) },
                )
            }
            .semantics { contentDescription = "Song position"; stateDescription = "${(shown * 100).toInt()}%" }
    ) {
        val y = size.height / 2
        val line = 4.dp.toPx()
        val x = size.width * shown
        drawLine(Color(0x4DFFFFFF), Offset(0f, y), Offset(size.width, y), strokeWidth = line, cap = StrokeCap.Round)
        drawLine(Color.White, Offset(0f, y), Offset(x, y), strokeWidth = line, cap = StrokeCap.Round)
        drawCircle(Color.White, radius = (if (drag != null) 8.dp else 6.dp).toPx(), center = Offset(x, y))
    }
}

/** The mini player's thin progress line (no dot), like Spotify's. */
@Composable
fun ThinProgress(progress: Float, modifier: Modifier = Modifier) {
    androidx.compose.foundation.Canvas(modifier.fillMaxWidth().height(2.dp)) {
        val y = size.height / 2
        drawLine(Color(0x33FFFFFF), Offset(0f, y), Offset(size.width, y), strokeWidth = size.height, cap = StrokeCap.Round)
        drawLine(Color.White, Offset(0f, y), Offset(size.width * progress.coerceIn(0f, 1f), y), strokeWidth = size.height,
                 cap = StrokeCap.Round)
    }
}
