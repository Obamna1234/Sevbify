package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.media3.common.MediaItem
import androidx.media3.common.Player as M3Player
import androidx.media3.exoplayer.ExoPlayer
import com.sevbify.app.Bridge
import com.sevbify.app.Player
import com.sevbify.app.Track
import kotlinx.coroutines.delay

/** Song menu → Preview: the 30-second clip in a small window with a seek bar. It's the only place a clip plays;
 *  everything else streams the full song. Runs on its own player, so the main song is only paused. */
@Composable
fun PreviewDialog(t: Track) {
    val context = LocalContext.current
    var url by remember(t) { mutableStateOf(t.previewUrl) }
    var missing by remember(t) { mutableStateOf(false) }
    val exo = remember(t) { ExoPlayer.Builder(context).build() }
    var playing by remember { mutableStateOf(false) }
    var pos by remember { mutableLongStateOf(0L) }
    var len by remember { mutableLongStateOf(30_000L) }
    var drag by remember { mutableFloatStateOf(-1f) }

    LaunchedEffect(t) {
        if (url.isEmpty()) {
            url = try { (Bridge.call("preview_url", t.artist, t.title) as? String).orEmpty() } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                ""
            }
            if (url.isEmpty()) { missing = true; return@LaunchedEffect }
        }
        Player.pause()
        exo.setMediaItem(MediaItem.fromUri(url))
        exo.prepare()
        exo.play()
        while (true) {
            playing = exo.isPlaying
            pos = exo.currentPosition
            if (exo.duration > 0) len = exo.duration
            if (exo.playbackState == M3Player.STATE_ENDED) playing = false
            delay(200)
        }
    }
    DisposableEffect(t) { onDispose { exo.release() } }

    Dialog(onDismissRequest = { Nav.previewFor = null }) {
        Column(Modifier.fillMaxWidth().background(C.Elevated, RoundedCornerShape(12.dp)).padding(20.dp)) {
            Text(t.title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium)
            Text(if (missing) "No preview for this song" else "${t.artist} · 30-second preview",
                 maxLines = 1, style = MaterialTheme.typography.bodySmall.copy(color = C.Sub))
            if (!missing) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 12.dp)) {
                    IconButton(onClick = {
                        if (exo.isPlaying) exo.pause()
                        else { if (exo.playbackState == M3Player.STATE_ENDED) exo.seekTo(0); exo.play() }
                    }) {
                        Icon(if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                             if (playing) "Pause" else "Play", tint = C.Text)
                    }
                    Spacer(Modifier.width(8.dp))
                    SeekBar(progress = if (len > 0) pos.toFloat() / len else 0f,
                            onSeek = { f -> exo.seekTo((f * len).toLong()); if (!exo.isPlaying) exo.play() },
                            onDrag = { f -> drag = f ?: -1f },
                            modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(8.dp))
                    val shown = if (drag >= 0f) (drag * len).toLong() else pos
                    Text("${shown / 60000}:${"%02d".format((shown / 1000) % 60)}",
                         style = MaterialTheme.typography.bodySmall.copy(color = C.Sub))
                }
            }
        }
    }
}
