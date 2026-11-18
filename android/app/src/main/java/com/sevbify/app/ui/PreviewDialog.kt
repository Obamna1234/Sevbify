package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.automirrored.filled.QueueMusic
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import com.sevbify.app.tr
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

/** Song menu → Preview (30 s), like a small Spotify player over the app: whatever was playing pauses, the clip plays
 *  on its own player, and the slider can be dragged anywhere in the 30 seconds. Restart goes back to 0:00, Add to
 *  queue keeps the song for later, ⊕ saves it. "Play full song" plays the whole song now (the one you were playing
 *  stays as the previous song); Close (✕, Back or tapping outside) carries on with your song where it paused. */
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
    val wasPlaying = remember(t) { Player.showPlaying }
    val colour = rememberCoverColour(t.art, Color(0xFF3B4F6B))

    LaunchedEffect(t) {
        Player.pause()
        if (url.isEmpty()) {
            url = try { (Bridge.call("preview_url", t.artist, t.title) as? String).orEmpty() } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                ""
            }
            if (url.isEmpty()) { missing = true; return@LaunchedEffect }
        }
        exo.setMediaItem(MediaItem.fromUri(url))
        exo.prepare()
        exo.play()
        while (true) {
            playing = exo.isPlaying
            pos = exo.currentPosition
            if (exo.duration > 0) len = exo.duration
            if (exo.playbackState == M3Player.STATE_ENDED) playing = false
            delay(100)
        }
    }
    DisposableEffect(t) { onDispose { exo.release() } }

    fun close() { Nav.previewFor = null; if (wasPlaying && !Player.showPlaying) Player.playPause() }
    fun full() { Nav.previewFor = null; Player.playFullNow(t) }

    Dialog(onDismissRequest = { close() }) {
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                .background(Brush.verticalGradient(listOf(colour, Color(0xFF1F2733), Color(0xFF181818))))
                .padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Plainly a preview: a green badge, and "of 0:30" under the slider.
                Text(tr("30-SECOND PREVIEW"), color = Color.Black, style = MaterialTheme.typography.labelMedium,
                     fontWeight = FontWeight.Bold,
                     modifier = Modifier.clip(RoundedCornerShape(50)).background(C.Green).padding(horizontal = 10.dp, vertical = 4.dp))
                Spacer(Modifier.weight(1f))
                IconButton(onClick = { close() }) { Icon(Icons.Filled.Close, "Close", tint = C.Text) }
            }
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().aspectRatio(1f)) {
                Cover(t.art, 400.dp, RoundedCornerShape(8.dp), Modifier.fillMaxSize())
                Text("0:30", color = Color.White, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
                     modifier = Modifier.align(Alignment.BottomEnd).padding(8.dp).clip(RoundedCornerShape(4.dp))
                         .background(Color(0xCC000000)).padding(horizontal = 6.dp, vertical = 2.dp))
            }
            Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleLarge,
                         fontWeight = FontWeight.Bold)
                    Text(t.artist, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium.copy(color = C.Sub))
                }
                val saved = isSaved(t)
                IconButton(onClick = { saveTap(t) }) {
                    Icon(if (saved) Icons.Filled.CheckCircle else Icons.Filled.AddCircleOutline, if (saved) "Saved in…" else "Add to Liked Songs",
                         tint = if (saved) C.Green else C.Sub, modifier = Modifier.size(28.dp))
                }
            }
            if (missing) {
                Text(tr("There's no preview for this song, but you can play the full song."), color = C.Sub,
                     style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 16.dp))
            } else {
                Spacer(Modifier.height(10.dp))
                SeekBar(progress = if (len > 0) pos.toFloat() / len else 0f,
                        onSeek = { f -> exo.seekTo((f * len).toLong()); if (!exo.isPlaying) exo.play() },
                        onDrag = { f -> drag = f ?: -1f })
                val shown = if (drag >= 0f) (drag * len).toLong() else pos
                Row {
                    Text(clock(shown), style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.weight(1f))
                    Text(clock(len), style = MaterialTheme.typography.labelSmall)
                }
                Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically) {
                    PreviewSide(Icons.Filled.Replay, "Restart") { exo.seekTo(0); exo.play() }
                    Surface(onClick = {
                        if (exo.isPlaying) exo.pause()
                        else { if (exo.playbackState == M3Player.STATE_ENDED) exo.seekTo(0); exo.play() }
                    }, shape = CircleShape, color = Color.White, modifier = Modifier.size(62.dp)) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (playing) "Pause" else "Play",
                                 tint = Color.Black, modifier = Modifier.size(34.dp))
                        }
                    }
                    PreviewSide(Icons.AutoMirrored.Filled.QueueMusic, "Add to queue") {
                        Player.addToQueue(t); Nav.say(tr("Added to queue"))
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = { full() }, modifier = Modifier.weight(1f).height(48.dp),
                       colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) {
                    Icon(Icons.Filled.PlayArrow, null); Spacer(Modifier.width(4.dp)); Text(tr("Play full song"), fontWeight = FontWeight.Bold)
                }
                OutlinedButton(onClick = { close() }, modifier = Modifier.weight(1f).height(48.dp)) { Text(tr("Close"), color = C.Text) }
            }
            if (wasPlaying) Text(tr("Close and your song carries on where it was"), color = C.Sub,
                                 style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.Center,
                                 modifier = Modifier.fillMaxWidth().padding(top = 10.dp))
        }
    }
}

@Composable
private fun PreviewSide(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, onClick: () -> Unit) {
    Column(Modifier.width(84.dp).clip(RoundedCornerShape(8.dp)).clickable(onClick = onClick).padding(vertical = 6.dp),
           horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(44.dp).border(2.dp, Color.White, CircleShape), contentAlignment = Alignment.Center) {
            Icon(icon, tr(label), tint = C.Text, modifier = Modifier.size(22.dp))
        }
        Text(tr(label), style = MaterialTheme.typography.labelSmall, color = C.Sub)
    }
}
