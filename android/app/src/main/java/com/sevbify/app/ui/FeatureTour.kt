package com.sevbify.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Equalizer
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MusicVideo
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.PlaylistAdd
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sevbify.app.Library
import kotlinx.coroutines.launch

/** "How to use Sevbify": the short guide shown on the first start (and from Settings → About → How to use Sevbify).
 *  Swipe or tap Next; each page is one thing most people use, with where to find it. Pictures are drawn icons, so
 *  they look the same on every phone and never show anyone else's music. "Don't show this again" keeps it closed. */
object Tour {
    var open by mutableStateOf(false)
    var fromSettings by mutableStateOf(false)

    data class Page(val icon: ImageVector, val colour: Color, val title: String, val text: String)

    val pages = listOf(
        Page(Icons.Filled.Headphones, Color(0xFF1ED760), "Welcome to Sevbify",
            "Free music with no account, no ads and no tracking. Your library, playlists and downloads stay on your phone."),
        Page(Icons.Filled.Search, Color(0xFF4F8BFF), "Search and play",
            "Search finds songs, artists, albums, podcasts and audiobooks. Tap any song to play it in full."),
        Page(Icons.Filled.AddCircleOutline, Color(0xFFE91E63), "Save what you like",
            "Tap ⊕ (in the player or next to a song) to add it to Liked Songs or a playlist. ⋮ has more: add to queue, song radio, hide."),
        Page(Icons.Filled.PlaylistAdd, Color(0xFFFF9800), "Playlists and folders",
            "Create (+) makes a playlist or a folder. Import a playlist brings in a Spotify, Apple Music or Deezer playlist from its link."),
        Page(Icons.Filled.Download, Color(0xFF00BFA5), "Download for offline",
            "Tap ↓ on a song or playlist to keep it on your phone. Smart downloads (Settings) can do it for songs you play a lot."),
        Page(Icons.Filled.Mic, Color(0xFF9C27B0), "Podcasts and audiobooks",
            "Follow podcasts and play free audiobooks. Sevbify remembers where you stopped. ⊕ saves an episode to Your Episodes."),
        Page(Icons.Filled.MusicVideo, Color(0xFF3F51B5), "Now Playing",
            "Tap the mini player: lyrics, Canvas loops, the queue, sleep timer and more. Swipe the cover to skip."),
        Page(Icons.Filled.People, Color(0xFFFF5252), "Share and Blend",
            "Share a playlist as a link a friend can add or merge into theirs. Blend mixes your taste with a friend's. No server: the link is the playlist."),
        Page(Icons.Filled.Computer, Color(0xFF607D8B), "Your computer",
            "Settings → Your computer → Pair. Send songs across, see what the computer plays and control it, on your own Wi-Fi."),
        Page(Icons.Filled.Equalizer, Color(0xFF8BC34A), "Your sound",
            "Settings → Playback: equaliser, volume levelling, mono audio and fades between songs."),
        Page(Icons.Filled.Lock, Color(0xFF1ED760), "Private by design",
            "Private session hides what you play. Nothing is sent to anyone. You can open this guide again from Settings → About."),
    )

    fun showOnFirstStart() { if (!Library.settings.tourSeen) { fromSettings = false; open = true } }
    fun showAgain() { fromSettings = true; open = true }
}

/** Full screen over the app (not a separate window), so it sits between the status bar and the navigation bar. */
@Composable
fun FeatureTourDialog() {
    if (!Tour.open) return
    val pages = Tour.pages
    val pager = rememberPagerState { pages.size }
    val scope = rememberCoroutineScope()
    var never by remember { mutableStateOf(true) }
    fun close() {
        if (!Tour.fromSettings && never) { Library.settings.tourSeen = true; Library.changed() }
        Tour.open = false
    }
    BackHandler { if (pager.currentPage > 0) scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } else close() }
    Box(Modifier.fillMaxSize().background(C.Bg)
        .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {}   // nothing behind is tapped
        .systemBarsPadding()) {
        Column(Modifier.fillMaxSize().padding(horizontal = 20.dp, vertical = 12.dp)) {
            HorizontalPager(pager, modifier = Modifier.weight(1f).fillMaxWidth()) { i ->
                val p = pages[i]
                Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center) {
                    Box(Modifier.fillMaxWidth().widthIn(max = 420.dp).aspectRatio(1.3f).clip(RoundedCornerShape(24.dp))
                        .background(Brush.linearGradient(listOf(p.colour, p.colour.copy(alpha = 0.35f), Color(0xFF181818)))),
                        contentAlignment = Alignment.Center) {
                        Icon(p.icon, null, tint = Color.White, modifier = Modifier.size(110.dp))
                    }
                    Spacer(Modifier.height(28.dp))
                    Text(p.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(10.dp))
                    Text(p.text, style = MaterialTheme.typography.bodyLarge, color = C.Sub)
                }
            }
            // Page dots: the current one stretches, like Spotify's.
            Row(Modifier.align(Alignment.CenterHorizontally).padding(vertical = 14.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                pages.indices.forEach { i ->
                    val on = i == pager.currentPage
                    val w by animateDpAsState(if (on) 22.dp else 8.dp, label = "dot")
                    val c by animateColorAsState(if (on) C.Green else C.Sub.copy(alpha = 0.5f), label = "dotc")
                    Box(Modifier.height(8.dp).width(w).clip(CircleShape).background(c))
                }
            }
            if (!Tour.fromSettings) Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = never, onCheckedChange = { never = it })
                Text("Don't show this again", style = MaterialTheme.typography.bodyMedium)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                val last = pager.currentPage == pages.size - 1
                if (!last) TextButton(onClick = { close() }) { Text("Skip", color = C.Text) }
                Spacer(Modifier.weight(1f))
                if (pager.currentPage > 0) TextButton(onClick = { scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } }) {
                    Text("Back", color = C.Text)
                }
                Button(onClick = { if (last) close() else scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } },
                       colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) {
                    Text(if (last) "Start listening" else "Next")
                }
            }
        }
    }
}
