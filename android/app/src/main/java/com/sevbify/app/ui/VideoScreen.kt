package com.sevbify.app.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.content.pm.ActivityInfo
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Cast
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.ClosedCaptionOff
import androidx.compose.material.icons.filled.Forward10
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.material.icons.filled.OpenInFull
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay10
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.sevbify.app.Player
import com.sevbify.app.VideoPlayer
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

/** The video itself (Now playing, the floating mini player, full screen and the picture-in-picture window use it).
 *  Captions show on it when they're switched on; `VideoPlayer.zoomFill` fills the screen instead of fitting. */
@androidx.annotation.OptIn(markerClass = [androidx.media3.common.util.UnstableApi::class])
@Composable
fun VideoSurface(showControls: Boolean, modifier: Modifier = Modifier.fillMaxSize()) {
    val context = LocalContext.current
    AndroidView(
        factory = { PlayerView(it).apply {
            player = VideoPlayer.get(context); useController = showControls
            subtitleView?.setApplyEmbeddedStyles(false)
            subtitleView?.setFractionalTextSize(0.0533f)
            keepScreenOn = true                                    // the screen stays on while you watch
        } },
        update = { view ->
            view.player = VideoPlayer.player ?: VideoPlayer.get(context)
            view.useController = showControls
            view.resizeMode = if (VideoPlayer.zoomFill) AspectRatioFrameLayout.RESIZE_MODE_ZOOM
                              else AspectRatioFrameLayout.RESIZE_MODE_FIT
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

/** Two fingers: pinch out = fill the screen, pinch in = fit (like YouTube). One finger is left alone. */
private suspend fun PointerInputScope.detectPinchZoom(onPinch: (Float) -> Unit) {
    awaitEachGesture {
        awaitFirstDown(requireUnconsumed = false)
        var total = 1f
        do {
            val ev = awaitPointerEvent()
            if (ev.changes.size >= 2) { total *= ev.calculateZoom(); ev.changes.forEach { it.consume() } }
        } while (ev.changes.any { it.pressed })
        if (total > 1.12f || total < 0.88f) onPinch(total)
    }
}

private fun activityOf(context: Context): Activity? {
    var c = context
    while (c is ContextWrapper) { if (c is Activity) return c; c = c.baseContext }
    return null
}

/**
 * Controls drawn over the video: tap to show/hide; double-tap the left or right side to go back/forward 10 s
 * (the middle toggles fill/fit); pinch to fill/fit. Play/pause, ±10 s, a seek bar, captions, speed, cast and
 * full screen. They fade away after 3 seconds while it plays.
 */
@Composable
fun VideoControls(fullscreen: Boolean, modifier: Modifier = Modifier.fillMaxSize()) {
    val context = LocalContext.current
    val v = VideoPlayer
    var shown by remember { mutableStateOf(true) }
    var bump by remember { mutableIntStateOf(0) }
    var flash by remember { mutableStateOf("") }
    var pos by remember { mutableLongStateOf(0L) }
    var dur by remember { mutableLongStateOf(0L) }
    var dragTo by remember { mutableStateOf<Float?>(null) }
    var captionMenu by remember { mutableStateOf(false) }
    LaunchedEffect(shown, bump, v.playing) { if (shown && v.playing) { delay(3000); shown = false } }
    LaunchedEffect(flash) { if (flash.isNotEmpty()) { delay(900); flash = "" } }
    LaunchedEffect(shown) { while (shown) { pos = v.position(); dur = v.duration(); delay(400) } }
    fun jump(ms: Long) { v.seekBy(ms); flash = if (ms < 0) "−10 s" else "+10 s"; bump++ }

    Box(modifier
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = { shown = !shown; bump++ },
                    onDoubleTap = { o ->
                        when {
                            o.x < size.width / 3f -> jump(-10_000)
                            o.x > size.width * 2f / 3f -> jump(10_000)
                            else -> { v.zoomFill = !v.zoomFill; flash = if (v.zoomFill) "Fill" else "Fit" }
                        }
                    })
            }
            .pointerInput(Unit) { detectPinchZoom { total -> v.zoomFill = total > 1f; flash = if (v.zoomFill) "Fill" else "Fit" } }) {
        if (flash.isNotEmpty()) {
            Text(flash, color = Color.White, modifier = Modifier.align(Alignment.Center).clip(RoundedCornerShape(50))
                .background(Color(0x99000000)).padding(horizontal = 16.dp, vertical = 8.dp))
        }
        if (v.loading) CircularProgressIndicator(Modifier.align(Alignment.Center).size(32.dp), color = C.Green)
        AnimatedVisibility(shown, enter = fadeIn(), exit = fadeOut()) {
            Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xAA000000), Color(0x22000000), Color(0xAA000000))))) {
                // top: back (full screen) · captions · speed · cast
                Row(Modifier.align(Alignment.TopStart).fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    if (fullscreen) VideoIcon(Icons.AutoMirrored.Filled.ArrowBack, "Exit full screen") { v.fullscreen = false }
                    Text(Player.current?.title.orEmpty(), color = Color.White, maxLines = 1,
                         overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, modifier = Modifier.weight(1f).padding(horizontal = 8.dp))
                    if (v.captions.isNotEmpty()) {
                        Box {
                            VideoIcon(if (v.captionsOn) Icons.Filled.ClosedCaption else Icons.Filled.ClosedCaptionOff,
                                      if (v.captionsOn) "Captions on" else "Captions off") { captionMenu = true; bump++ }
                            DropdownMenu(captionMenu, { captionMenu = false }) {
                                DropdownMenuItem(text = { Text(if (v.captionsOn) "Off" else "Off  ✓") },
                                                 onClick = { v.setCaptions(false); captionMenu = false })
                                v.captions.forEach { c ->
                                    DropdownMenuItem(text = { Text(c.name + if (v.captionsOn && v.captionLang == c.lang) "  ✓" else "") },
                                                     onClick = { if (v.captionLang == c.lang) v.setCaptions(true) else v.chooseCaption(c.lang); captionMenu = false })
                                }
                            }
                        }
                    }
                    Text(if (v.speed == 1f) "1×" else "${v.speed.toString().removeSuffix(".0")}×", color = Color.White,
                         modifier = Modifier.clip(RoundedCornerShape(50)).clickable {
                             val steps = listOf(0.75f, 1f, 1.25f, 1.5f, 2f)
                             v.changeSpeed(steps[(steps.indexOf(v.speed).let { if (it < 0) 1 else it } + 1) % steps.size]); bump++
                         }.padding(horizontal = 10.dp, vertical = 8.dp))
                    VideoIcon(Icons.Filled.Cast, "Cast: show this on a TV") { castToTv(context) }
                }
                // middle: −10 · play/pause · +10
                Row(Modifier.align(Alignment.Center), horizontalArrangement = Arrangement.spacedBy(28.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    VideoIcon(Icons.Filled.Replay10, "Back 10 seconds", 40.dp) { jump(-10_000) }
                    VideoIcon(if (v.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (v.playing) "Pause" else "Play", 56.dp) {
                        Player.playPause(); bump++
                    }
                    VideoIcon(Icons.Filled.Forward10, "Forward 10 seconds", 40.dp) { jump(10_000) }
                }
                // bottom: time · seek bar · full screen
                Column(Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
                    SeekBar(progress = if (dur > 0) pos.toFloat() / dur else 0f,
                            onSeek = { f -> if (dur > 0) { v.player?.seekTo((f * dur).toLong()); pos = (f * dur).toLong() }; bump++ },
                            onDrag = { dragTo = it; bump++ })
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        val shownPos = dragTo?.let { (it * dur).toLong() } ?: pos
                        Text("${clock(shownPos)} / ${clock(dur)}", color = Color.White, style = androidx.compose.material3.MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.weight(1f))
                        VideoIcon(if (fullscreen) Icons.Filled.FullscreenExit else Icons.Filled.Fullscreen,
                                  if (fullscreen) "Exit full screen" else "Full screen") { v.fullscreen = !fullscreen }
                    }
                }
            }
        }
    }
}

@Composable
private fun VideoIcon(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, size: androidx.compose.ui.unit.Dp = 28.dp,
                      onClick: () -> Unit) {
    Box(Modifier.size(size + 16.dp).clip(CircleShape).clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Icon(icon, label, tint = Color.White, modifier = Modifier.size(size))
    }
}

/** Show it on a TV: opens the phone's own Cast / screen-mirroring screen (it mirrors what you see, so use it with
 *  full screen). Sevbify doesn't talk to Google's Cast service itself: YouTube's links only work for the phone. */
private fun castToTv(context: Context) {
    try {
        context.startActivity(Intent(Settings.ACTION_CAST_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (e: Exception) {
        Nav.say("Swipe down for Quick Settings and tap Cast, Screen cast or Smart View")
    }
}

/** Landscape full screen: no bars, screen kept on, back returns. Pinch to fill, double-tap to skip, like YouTube. */
@Composable
fun FullscreenVideo() {
    val context = LocalContext.current
    val view = LocalView.current
    BackHandler(enabled = true) { VideoPlayer.fullscreen = false }
    DisposableEffect(Unit) {
        val activity = activityOf(context)
        val window = activity?.window
        val controller = window?.let { WindowCompat.getInsetsController(it, view) }
        activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        controller?.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller?.hide(WindowInsetsCompat.Type.systemBars())
        onDispose {
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            controller?.show(WindowInsetsCompat.Type.systemBars())
        }
    }
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        VideoSurface(showControls = false)
        VideoControls(fullscreen = true)
    }
}

/**
 * The in-app mini player for a video podcast (like YouTube's): just the picture, over the app while you browse.
 * Drag it anywhere; pinch it bigger or smaller. Tap it to show a play/pause button, an expand button (opens
 * the full video) and a close button (back to listening); they hide again by themselves. A thin line along the
 * bottom shows how far you are.
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
        var shown by remember { mutableStateOf(false) }
        var bump by remember { mutableIntStateOf(0) }
        var pos by remember { mutableLongStateOf(0L) }
        LaunchedEffect(shown, bump) { if (shown) { delay(3000); shown = false } }
        LaunchedEffect(Unit) { while (true) { pos = VideoPlayer.position(); delay(500) } }
        Box(Modifier.offset { IntOffset(with(density) { x.dp.roundToPx() }, with(density) { y.dp.roundToPx() }) }
                .size(w.dp, h.dp).shadow(12.dp, RoundedCornerShape(10.dp)).clip(RoundedCornerShape(10.dp))
                .background(Color.Black)) {
            VideoSurface(showControls = false)
            if (VideoPlayer.loading) CircularProgressIndicator(Modifier.align(Alignment.Center).size(28.dp), color = C.Green)
            // A see-through layer on top takes the touches (the video view would swallow them): drag = move,
            // pinch = resize, tap = show the buttons, double-tap = open the full video.
            Box(Modifier.fillMaxSize()
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            x += pan.x / density.density
                            y += pan.y / density.density
                            if (zoom != 1f) {
                                val newW = (widthDp * zoom).coerceIn(160f, maxW - 16f)
                                widthDp = newW
                            }
                        }
                    }
                    .pointerInput(Unit) {
                        detectTapGestures(onTap = { shown = !shown; bump++ }, onDoubleTap = { Nav.nowPlayingOpen = true })
                    })
            AnimatedVisibility(shown, enter = fadeIn(), exit = fadeOut()) {
                Box(Modifier.fillMaxSize().background(Color(0x66000000))) {
                    SmallButton(if (VideoPlayer.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                                if (VideoPlayer.playing) "Pause" else "Play", Modifier.align(Alignment.Center)) { Player.playPause(); bump++ }
                    SmallButton(Icons.Filled.OpenInFull, "Open the full video", Modifier.align(Alignment.TopStart)) { Nav.nowPlayingOpen = true }
                    SmallButton(Icons.Filled.Close, "Close the video (keep listening)", Modifier.align(Alignment.TopEnd)) { Player.switchToAudio() }
                }
            }
            val d = VideoPlayer.duration()
            ThinProgress(if (d > 0) pos.toFloat() / d else 0f, Modifier.align(Alignment.BottomCenter))
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
