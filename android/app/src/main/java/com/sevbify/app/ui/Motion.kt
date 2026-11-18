package com.sevbify.app.ui

import com.sevbify.app.tr
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.NewReleases
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.sevbify.app.Library
import kotlinx.coroutines.launch

/** Spotify's swipe between filter chips (Home: All / Music / Podcasts / Audiobooks; Your Library's filters):
 *  a real pager, so the next page follows your finger beside this one (no blank gap or flicker), a quick flick is
 *  enough, and tapping a chip slides across to it. Rows that scroll sideways keep their own swipes first. */
@Composable
fun SwipePages(index: Int, count: Int, onChange: (Int) -> Unit, modifier: Modifier = Modifier,
               content: @Composable (Int) -> Unit) {
    val pager = androidx.compose.foundation.pager.rememberPagerState(initialPage = index) { count }
    // A chip was tapped: slide to it.
    LaunchedEffect(index) { if (pager.currentPage != index && !pager.isScrollInProgress) pager.animateScrollToPage(index) }
    // A swipe settled on another page: select its chip.
    val now by androidx.compose.runtime.rememberUpdatedState(index)
    val change by androidx.compose.runtime.rememberUpdatedState(onChange)
    LaunchedEffect(pager) {
        androidx.compose.runtime.snapshotFlow { pager.settledPage }.collect { if (it != now) change(it) }
    }
    androidx.compose.foundation.pager.HorizontalPager(pager, modifier, key = { it }, verticalAlignment = Alignment.Top) { page ->
        Box(Modifier.fillMaxSize().background(C.Bg)) { content(page) }
    }
}

/** Spotify's profile menu: slides in from the left (or swipe from the left edge of a main tab) and pushes the
 *  page aside. Sevbify has no account, so it holds your profile file, recently played, downloads and Settings. */
@Composable
fun ProfileDrawer(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    fun go(screen: Screen) { Nav.drawerOpen = false; Nav.go(screen) }
    Column(modifier.fillMaxHeight().background(C.Elevated).statusBarsPadding().padding(top = 12.dp)) {
        Row(Modifier.fillMaxWidth().clickable { go(Screen.SettingsPage("privacy")) }.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically) {
            SettingsBadgeImage(44)
            Spacer(Modifier.width(12.dp))
            Column {
                Text("Sevbify", style = MaterialTheme.typography.titleLarge)
                Text(tr("Your Sevbify profile"), style = MaterialTheme.typography.bodySmall, color = C.Sub)
            }
        }
        HorizontalDivider(color = C.Highlight)
        DrawerItem(Icons.Filled.Notifications, "New for you") {
            Nav.drawerOpen = false
            com.sevbify.app.SevbifyApp.instance.scope.launch {
                try {
                    val shows = org.json.JSONArray().also { a -> Library.shows.forEach { a.put(it.json) } }
                    val items = com.sevbify.app.Bridge.arr("whats_new", shows.toString(), Library.listensJson())
                    val tracks = (0 until items.length()).map { com.sevbify.app.Track.fromJson(items.getJSONObject(it).getJSONObject("track")) }
                    if (tracks.isEmpty()) Nav.say("Nothing new in the last two weeks: follow shows and play artists you like")
                    else Nav.go(Screen.Collection("new", "New for you", tracks, "", saveable = true))
                } catch (e: Exception) { Nav.say("⚠ ${e.message}") }
            }
        }
        DrawerItem(Icons.Filled.NewReleases, "What's new in Sevbify") {
            Nav.drawerOpen = false
            try {
                context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW,
                    android.net.Uri.parse("https://github.com/Obamna1234/Sevbify/releases")).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
            } catch (_: Exception) {}
        }
        DrawerItem(Icons.Filled.History, "Recently played") {
            go(Screen.Collection("recent", tr("Recently played"), Library.recent.toList(), "", saveable = false))
        }
        DrawerItem(Icons.Filled.Download, "Downloads") { go(Screen.Downloads) }
        DrawerItem(Icons.Filled.BarChart, "Your Wrapped") { Nav.drawerOpen = false; Nav.wrappedOpen = true }
        DrawerItem(Icons.Filled.Settings, "Settings and privacy") { go(Screen.Settings) }
    }
}

@Composable
private fun DrawerItem(icon: ImageVector, text: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = C.Text, modifier = Modifier.size(24.dp))
        Spacer(Modifier.width(16.dp))
        Text(tr(text), style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
fun SettingsBadgeImage(sizeDp: Int) {
    androidx.compose.foundation.Image(
        androidx.compose.ui.res.painterResource(com.sevbify.app.R.drawable.sevbify_logo), null,
        modifier = Modifier.size(sizeDp.dp).clip(CircleShape))
}

/** A strip along the left edge of a main tab: swipe right from it to open the profile menu. */
@Composable
fun DrawerEdge(modifier: Modifier = Modifier, onDrag: (Float) -> Unit, onEnd: () -> Unit) {
    Box(modifier.width(20.dp).fillMaxHeight().pointerInput(Unit) {
        detectHorizontalDragGestures(onDragEnd = onEnd, onDragCancel = onEnd) { change, d -> change.consume(); onDrag(d) }
    })
}

@Suppress("unused")
private fun keep() = Modifier.fillMaxSize()
