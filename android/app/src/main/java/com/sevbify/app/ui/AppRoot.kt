package com.sevbify.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.LibraryMusic
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sevbify.app.Library
import com.sevbify.app.Player

@Composable
fun AppRoot() {
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(Nav.toast) {
        if (Nav.toast.isNotEmpty()) { snack.showSnackbar(Nav.toast); Nav.toast = "" }
    }
    LaunchedEffect(Player.status) {
        val s = Player.status
        if (s.startsWith("⚠") || s.startsWith("Couldn't") || s.startsWith("You're offline")) Nav.toast = s
    }
    BackHandler(enabled = true) { if (!Nav.back()) Nav.tab = Tab.HOME }

    if (com.sevbify.app.VideoPlayer.inPip) {
        // The picture-in-picture mini player: only the video.
        Box(Modifier.fillMaxSize().background(C.Black)) { VideoSurface(showControls = false) }
        return
    }
    Box(Modifier.fillMaxSize().background(C.Black)) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f).fillMaxWidth().background(C.Bg)) { CurrentScreen(Nav.top) }
            BottomArea()
        }
        AnimatedVisibility(Nav.nowPlayingOpen, enter = slideInVertically { it }, exit = slideOutVertically { it }) {
            NowPlayingScreen()
        }
        if (Player.videoMode && !Nav.nowPlayingOpen) FloatingVideo()    // keeps playing while you browse
        AnimatedVisibility(Nav.lyricsOpen, enter = slideInVertically { it }, exit = slideOutVertically { it }) { LyricsScreen() }
        Nav.shareFor?.let { ShareSheet(it) }
        if (Nav.connectOpen) ConnectSheet()
        SnackbarHost(snack, Modifier.align(Alignment.BottomCenter).padding(bottom = 140.dp))
        Sheets()
        Dialogs()
    }
}

@Composable
private fun CurrentScreen(screen: Screen) {
    when (screen) {
        Screen.Home -> HomeScreen()
        Screen.Search -> SearchScreen()
        Screen.Library -> LibraryScreen()
        is Screen.PlaylistPage -> PlaylistScreen(screen.id)
        is Screen.Collection -> CollectionScreen(screen)
        is Screen.Artist -> ArtistScreen(screen.name)
        is Screen.Genre -> GenreScreen(screen)
        Screen.Podcasts -> PodcastsScreen()
        Screen.Audiobooks -> AudiobooksScreen()
        is Screen.ShowPage -> ShowScreen(screen.show)
        Screen.Settings -> SettingsScreen()
        is Screen.Import -> ImportScreen(screen.text)
        Screen.ToDownload -> ToDownloadScreen()
        Screen.YourSongs -> YourSongsScreen()
        Screen.Downloads -> DownloadsScreen()
    }
}

/** Mini player above Spotify's bottom bar (Home · Search · Your Library · Create), over a dark fade. */
@Composable
private fun BottomArea() {
    var createOpen by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth()
               .background(Brush.verticalGradient(listOf(C.Bg, C.Black)))
               .navigationBarsPadding()) {
        if (Player.current != null) MiniPlayer()
        Row(Modifier.fillMaxWidth().height(60.dp), verticalAlignment = Alignment.CenterVertically) {
            NavItem("Home", Icons.Filled.Home, Icons.Outlined.Home, Nav.tab == Tab.HOME) { Nav.switch(Tab.HOME) }
            NavItem("Search", Icons.Filled.Search, Icons.Outlined.Search, Nav.tab == Tab.SEARCH) { Nav.switch(Tab.SEARCH) }
            NavItem("Your Library", Icons.Filled.LibraryMusic, Icons.Outlined.LibraryMusic, Nav.tab == Tab.LIBRARY) {
                Nav.switch(Tab.LIBRARY)
            }
            NavItem("Create", Icons.Filled.Add, Icons.Filled.Add, false) { createOpen = true }
        }
    }
    if (createOpen) CreateSheet { createOpen = false }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.NavItem(label: String, on: ImageVector, off: ImageVector,
                                                                selected: Boolean, onClick: () -> Unit) {
    Column(Modifier.weight(1f).clickable(onClick = onClick).padding(vertical = 6.dp),
           horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(if (selected) on else off, label, tint = if (selected) C.Text else C.Sub, modifier = Modifier.size(26.dp))
        Text(label, style = MaterialTheme.typography.labelSmall.copy(color = if (selected) C.Text else C.Sub))
    }
}

@Composable
private fun MiniPlayer() {
    val t = Player.current ?: return
    val colour = rememberCoverColour(t.art)
    Box(Modifier.padding(horizontal = 8.dp).fillMaxWidth().clip(RoundedCornerShape(6.dp))
            .background(colour).clickable { Nav.nowPlayingOpen = true }) {
        Row(Modifier.padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
            Cover(t.art, 40.dp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall)
                if (AudioOutput.kind != "speaker" && Player.status.isEmpty()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(AudioOutput.icon, null, tint = C.Green, modifier = Modifier.size(14.dp))
                        Text(" " + AudioOutput.name, maxLines = 1, overflow = TextOverflow.Ellipsis,
                             style = MaterialTheme.typography.bodySmall.copy(color = C.Green))
                    }
                } else {
                    Text(Player.status.takeIf { it.endsWith("…") } ?: t.artist, maxLines = 1, overflow = TextOverflow.Ellipsis,
                         style = MaterialTheme.typography.bodySmall.copy(color = Color(0xFFDDDDDD)))
                }
            }
            IconButton(onClick = { Nav.connectOpen = true }) {
                Icon(Icons.Filled.Devices, "Connect to a device", tint = if (AudioOutput.kind != "speaker") C.Green else C.Text)
            }
            IconButton(onClick = { Player.playPause() }) {
                Icon(if (Player.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                     if (Player.isPlaying) "Pause" else "Play", tint = C.Text, modifier = Modifier.size(30.dp))
            }
        }
        val d = Player.duration
        LinearProgressIndicator(progress = { if (d > 0) (Player.position.toFloat() / d).coerceIn(0f, 1f) else 0f },
                                modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(horizontal = 8.dp)
                                    .height(2.dp),
                                color = C.Text, trackColor = Color(0x33FFFFFF))
    }
}

@Composable
private fun Dialogs() {
    Player.noticeFor?.let {
        AlertDialog(
            onDismissRequest = { Player.acceptNotice(false) },
            title = { Text("Play full songs?") },
            text = {
                Text("Songs you don't have yet can stream in full from Bandcamp or YouTube (found by Sevbify, nothing " +
                     "is signed in to). Streaming YouTube without its own player and ads goes against YouTube's terms. " +
                     "Choose Previews to hear 30-second previews instead. You can change this in Settings.")
            },
            confirmButton = { TextButton(onClick = { Player.acceptNotice(true) }) { Text("Play full songs") } },
            dismissButton = { TextButton(onClick = { Player.acceptNotice(false) }) { Text("Previews") } },
            containerColor = C.Elevated,
        )
    }
    Nav.confirm?.let { (title, text, action) ->
        AlertDialog(onDismissRequest = { Nav.confirm = null },
                    title = { Text(title) }, text = { Text(text) },
                    confirmButton = { TextButton(onClick = { Nav.confirm = null; action() }) { Text("Delete", color = C.Green) } },
                    dismissButton = { TextButton(onClick = { Nav.confirm = null }) { Text("Cancel", color = C.Text) } },
                    containerColor = C.Elevated)
    }
    Nav.rename?.let { (start, done) ->
        var text by remember(start) { mutableStateOf(start) }
        AlertDialog(onDismissRequest = { Nav.rename = null },
                    title = { Text("Name") },
                    text = { OutlinedTextField(text, { text = it }, singleLine = true) },
                    confirmButton = { TextButton(onClick = { Nav.rename = null; done(text) }) { Text("Save", color = C.Green) } },
                    dismissButton = { TextButton(onClick = { Nav.rename = null }) { Text("Cancel", color = C.Text) } },
                    containerColor = C.Elevated)
    }
}

/** Ask before deleting, Spotify's way. Never deletes your music files. */
fun confirmDelete(what: String, action: () -> Unit) {
    Nav.confirm = Triple("Delete from Your Library?", "This will delete $what from Your Library. Your music files stay where they are.", action)
}

fun askName(start: String, done: (String) -> Unit) { Nav.rename = start to done }

@Suppress("unused")
private fun keepLibrary() = Library.changes
