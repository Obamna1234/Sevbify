package com.sevbify.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.sevbify.app.Library

/** The feature tour: a few pages with a screenshot each (assets/tour, made by tools/tour_images.py from the
 *  Android screenshots, playing openly licensed music). Opens once on the first start; "Don't show this again"
 *  keeps it closed; Settings → About and updates → Feature tour opens it again. */
object Tour {
    var open by mutableStateOf(false)
    var fromSettings by mutableStateOf(false)

    val pages = listOf(
        Triple("search.jpg", "Search everywhere at once",
            "One search looks through YouTube, Bandcamp, SoundCloud, Deezer and the music on your phone. Play any result straight away, full length."),
        Triple("save.jpg", "Save and download",
            "Tap ⊕ to save a song to Liked Songs or a playlist, and ⋮ for more: download it, add it to the queue, start its radio."),
        Triple("import.jpg", "Bring your Spotify playlists",
            "Share a playlist from Spotify to Sevbify, or paste its link in Your Library → + → Import. More than 100 songs? Paste the copied songs too. Your Spotify account is never signed in to."),
        Triple("radio.jpg", "Now playing and song radio",
            "Tap the mini player for the full player with lyrics and the queue. ⋮ → Go to song radio for an endless mix like any song."),
        Triple("podcast.jpg", "Podcasts and audiobooks",
            "Follow podcasts (with their video versions) and free audiobooks. Sevbify remembers where you stopped."),
        Triple("lyrics.jpg", "Lyrics",
            "Lyrics follow the song under Now playing; tap them to open them full screen."),
        Triple("pair.jpg", "Send music to your computer",
            "Settings → Your computer → Pair, and scan the code Sevbify shows on your computer. Songs and folders go straight to it over your own Wi-Fi, encrypted."),
        Triple("support.jpg", "Support the artist",
            "⋮ → Support the artist to buy their music straight from them: their own Bandcamp page or official shop."),
        Triple("settings.jpg", "Private by design",
            "No account, no ads, no tracking. Settings has a private session, data saving, downloads and more. You can open this tour again from Settings → About."),
    )

    fun showOnFirstStart() { if (!Library.settings.tourSeen) { fromSettings = false; open = true } }
    fun showAgain() { fromSettings = true; open = true }
}

@Composable
fun FeatureTourDialog() {
    if (!Tour.open) return
    val context = LocalContext.current
    var index by remember { mutableIntStateOf(0) }
    var never by remember { mutableStateOf(true) }
    val pages = remember {          // the pages whose picture is in the app (all of them if none are)
        val have = try { context.assets.list("tour")?.toSet() ?: emptySet() } catch (_: Exception) { emptySet() }
        Tour.pages.filter { it.first in have }.ifEmpty { Tour.pages }
    }
    fun close() {
        if (!Tour.fromSettings && never) { Library.settings.tourSeen = true; Library.changed() }
        Tour.open = false
    }
    Dialog(onDismissRequest = { close() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(Modifier.fillMaxSize().background(C.Bg).statusBarsPadding().navigationBarsPadding().padding(20.dp)
            .pointerInput(Unit) {
                var drag = 0f
                detectHorizontalDragGestures(onDragEnd = {
                    if (drag < -80) index = (index + 1).coerceAtMost(pages.size - 1)
                    if (drag > 80) index = (index - 1).coerceAtLeast(0)
                    drag = 0f
                }) { c, d -> c.consume(); drag += d }
            }) {
            val (pic, title, text) = pages[index]
            val bmp = remember(pic) {
                try { context.assets.open("tour/$pic").use { BitmapFactory.decodeStream(it) } } catch (_: Exception) { null }
            }
            Box(Modifier.weight(1f).fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Color(0xFF181818)),
                contentAlignment = Alignment.Center) {
                if (bmp != null) Image(bmp.asImageBitmap(), title, contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize())
            }
            Spacer(Modifier.height(16.dp))
            Text(title, style = MaterialTheme.typography.headlineSmall)
            Text(text, style = MaterialTheme.typography.bodyMedium, color = C.Sub, modifier = Modifier.padding(top = 6.dp).height(84.dp))
            Text(pages.indices.joinToString(" ") { if (it == index) "●" else "○" }, color = C.Sub,
                 modifier = Modifier.align(Alignment.CenterHorizontally).padding(vertical = 8.dp))
            if (!Tour.fromSettings) Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = never, onCheckedChange = { never = it })
                Text("Don't show this again", style = MaterialTheme.typography.bodyMedium)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                val last = index == pages.size - 1
                if (!last) TextButton(onClick = { close() }) { Text("Skip", color = C.Text) }
                Spacer(Modifier.weight(1f))
                if (index > 0) TextButton(onClick = { index-- }) { Text("Back", color = C.Text) }
                Button(onClick = { if (last) close() else index++ },
                       colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) {
                    Text(if (last) "Done" else "Next")
                }
            }
        }
    }
}
