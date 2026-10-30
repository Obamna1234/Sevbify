package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.OpenInFull
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.ui.PlayerView
import com.sevbify.app.Player
import com.sevbify.app.VideoPlayer
import kotlin.math.roundToInt

/** The video itself (Now playing, the floating mini player and the picture-in-picture window use it). */
@androidx.annotation.OptIn(markerClass = [androidx.media3.common.util.UnstableApi::class])
@Composable
fun VideoSurface(showControls: Boolean, modifier: Modifier = Modifier.fillMaxSize()) {
    val context = LocalContext.current
    AndroidView(
        factory = { PlayerView(it).apply { player = VideoPlayer.get(context); useController = showControls } },
        update = { view ->
            view.player = VideoPlayer.player ?: VideoPlayer.get(context)
            view.useController = showControls
        },
        modifier = modifier,
    )
}

/** Now playing's switch between the cover art and the video of a video podcast episode (like Spotify's). */
@Composable
fun AudioVideoSwitch() {
    val context = LocalContext.current
    val video = Player.videoMode
    Row(Modifier.clip(RoundedCornerShape(50)).background(Color(0x33FFFFFF)).padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        listOf(false to "Audio", true to "Video").forEach { (isVideo, label) ->
            val on = video == isVideo
            Box(Modifier.clip(RoundedCornerShape(50)).background(if (on) Color.White else Color.Transparent)
                    .clickable(enabled = !on) { if (isVideo) Player.switchToVideo(context) else Player.switchToAudio() }
                    .padding(horizontal = 16.dp, vertical = 6.dp)) {
                Text(label, color = if (on) Color.Black else C.Text)
            }
        }
    }
}

/**
 * The in-app mini player for a video podcast (like YouTube's): it keeps playing over the app while you browse.
 * Drag it anywhere; drag the corner handle to make it bigger or smaller; tap it to open Now playing; × goes back
 * to listening (audio only) at the same point.
 */
@Composable
fun FloatingVideo() {
    val density = LocalDensity.current
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val maxW = maxWidth.value
        val maxH = maxHeight.value
        var widthDp by remember { mutableFloatStateOf((maxW * 0.55f).coerceIn(180f, 320f)) }
        val w = widthDp.coerceIn(160f, maxW - 16f)
        val h = w * 9f / 16f
        var x by remember { mutableFloatStateOf(maxW - w - 12f) }
        var y by remember { mutableFloatStateOf(maxH - h - 170f) }      // just above the mini player and tabs
        x = x.coerceIn(4f, (maxW - w - 4f).coerceAtLeast(4f))
        y = y.coerceIn(4f, (maxH - h - 4f).coerceAtLeast(4f))
        Box(Modifier.offset { IntOffset(with(density) { x.dp.roundToPx() }, with(density) { y.dp.roundToPx() }) }
                .size(w.dp, h.dp).shadow(12.dp, RoundedCornerShape(10.dp)).clip(RoundedCornerShape(10.dp))
                .background(Color.Black)) {
            VideoSurface(showControls = false)
            if (VideoPlayer.loading) CircularProgressIndicator(Modifier.align(Alignment.Center).size(28.dp), color = C.Green)
            // A see-through layer on top takes the touches (the video view would swallow them).
            Box(Modifier.fillMaxSize()
                    .pointerInput(Unit) {
                        detectDragGestures { change, drag ->
                            change.consume()
                            x += drag.x / density.density
                            y += drag.y / density.density
                        }
                    }
                    .clickable { Nav.nowPlayingOpen = true })
            SmallButton(if (VideoPlayer.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        if (VideoPlayer.playing) "Pause" else "Play", Modifier.align(Alignment.Center)) { Player.playPause() }
            SmallButton(Icons.Filled.Close, "Close the video (keep listening)", Modifier.align(Alignment.TopEnd)) {
                Player.switchToAudio()
            }
            // Resize handle (bottom-left corner): drag left/up for bigger, right/down for smaller.
            Box(Modifier.align(Alignment.BottomStart).size(36.dp)
                    .pointerInput(Unit) {
                        detectDragGestures { change, drag ->
                            change.consume()
                            val grow = (-drag.x + -drag.y * 16f / 9f) / 2f / density.density
                            val newW = (widthDp + grow).coerceIn(160f, maxW - 16f)
                            x -= newW - widthDp
                            y -= (newW - widthDp) * 9f / 16f
                            widthDp = newW
                        }
                    }, contentAlignment = Alignment.Center) {
                Icon(Icons.Filled.OpenInFull, "Resize", tint = Color.White, modifier = Modifier.size(18.dp))
            }
        }
    }
}

@Composable
private fun SmallButton(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.padding(4.dp).size(32.dp).clip(CircleShape).background(Color(0x99000000)).clickable(onClick = onClick),
        contentAlignment = Alignment.Center) {
        Icon(icon, label, tint = Color.White, modifier = Modifier.size(20.dp))
    }
}
