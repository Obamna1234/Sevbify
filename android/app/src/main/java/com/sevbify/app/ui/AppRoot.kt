package com.sevbify.app.ui

import com.sevbify.app.tr

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.draggable
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import kotlinx.coroutines.launch
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
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.CheckCircle
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
import androidx.compose.ui.focus.focusRequester
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
    LaunchedEffect(Unit) { kotlinx.coroutines.delay(1200); Tour.showOnFirstStart() }   // first start: what Sevbify can do
    LaunchedEffect(Nav.toast) {
        if (Nav.toast.isNotEmpty()) { snack.showSnackbar(Nav.toast); Nav.toast = "" }
    }
    LaunchedEffect(Player.status) {
        val s = Player.status
        if (s.startsWith("⚠") || s.startsWith("Couldn't") || s.startsWith("You're offline")) Nav.toast = s
    }
    BackHandler(enabled = true) { if (!Nav.back()) Nav.tab = Tab.HOME }
    CoverPicker()
    Nav.creditsFor?.let { CreditsDialog(it) }

    if (com.sevbify.app.VideoPlayer.inPip) {
        // The picture-in-picture mini player: only the video.
        Box(Modifier.fillMaxSize().background(C.Black)) { VideoSurface(showControls = false) }
        return
    }
    Box(Modifier.fillMaxSize().background(C.Black)) {
        androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
            // Spotify's profile menu: it slides in from the left and pushes the whole app (bar and player too).
            val density = androidx.compose.ui.platform.LocalDensity.current
            val drawerW = maxWidth * 0.82f
            val drawerPx = with(density) { drawerW.toPx() }
            val scope = androidx.compose.runtime.rememberCoroutineScope()
            // How far open the menu is (0 = closed, 1 = open). Your finger moves it directly (no per-move animations
            // queued behind each other, which made it stutter and sometimes stop half open); letting go glides it
            // the rest of the way with your swipe's speed, and a quick flick is enough either way.
            var pos by remember { androidx.compose.runtime.mutableFloatStateOf(0f) }
            var dragging by remember { mutableStateOf(false) }
            val job = remember { arrayOfNulls<kotlinx.coroutines.Job>(1) }
            val flick = with(density) { 500.dp.toPx() }
            fun glide(to: Float, velocity: Float = 0f) {
                job[0]?.cancel()
                job[0] = scope.launch {
                    androidx.compose.animation.core.animate(pos, to, velocity / drawerPx,
                        androidx.compose.animation.core.spring(dampingRatio = 1f, stiffness = 500f)) { v, _ -> pos = v }
                }
            }
            LaunchedEffect(Nav.drawerOpen) { if (!dragging) glide(if (Nav.drawerOpen) 1f else 0f) }
            val drag = androidx.compose.foundation.gestures.rememberDraggableState { d ->
                job[0]?.cancel(); dragging = true
                pos = (pos + d / drawerPx).coerceIn(0f, 1f)
            }
            fun settle(velocity: Float) {
                dragging = false
                val o = if (kotlin.math.abs(velocity) > flick) velocity > 0 else pos >= 0.5f
                if (Nav.drawerOpen != o) Nav.drawerOpen = o
                glide(if (o) 1f else 0f, velocity)
            }
            fun Modifier.dragMenu() = this.draggable(drag, androidx.compose.foundation.gestures.Orientation.Horizontal,
                onDragStopped = { v -> settle(v) })
            if (pos > 0f) {
                ProfileDrawer(Modifier.width(drawerW).graphicsLayer { translationX = -(1f - pos) * drawerPx * 0.35f })
            }
            Column(Modifier.fillMaxSize().graphicsLayer { translationX = pos * drawerPx }) {
                Box(Modifier.weight(1f).fillMaxWidth().background(C.Bg)) { Pages() }
                BottomArea()
            }
            if (pos > 0f) {
                Box(Modifier.fillMaxSize().graphicsLayer { translationX = pos * drawerPx }
                        .background(Color.Black.copy(alpha = 0.45f * pos))
                        .clickable(interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
                                   indication = null) { Nav.drawerOpen = false }
                        .dragMenu())
            } else if (Nav.stack.size == 1 && !Nav.nowPlayingOpen) {
                Box(Modifier.width(20.dp).fillMaxHeight().dragMenu())       // swipe right from the left edge
            }
        }
        AnimatedVisibility(Nav.nowPlayingOpen, enter = slideInVertically { it }, exit = slideOutVertically { it }) {
            NowPlayingScreen()
        }
        if (Player.videoMode && !Nav.nowPlayingOpen && !com.sevbify.app.VideoPlayer.fullscreen) FloatingVideo()   // keeps playing while you browse
        if (Player.videoMode && com.sevbify.app.VideoPlayer.fullscreen) FullscreenVideo()
        AnimatedVisibility(Nav.lyricsOpen, enter = slideInVertically { it }, exit = slideOutVertically { it }) { LyricsScreen() }
        Nav.shareFor?.let { ShareSheet(it) }
        Nav.supportFor?.let { SupportSheet(it) }
        Nav.supportShow?.let { ShowSupportSheet(it) }
        if (Nav.connectOpen) ConnectSheet()
        SnackbarHost(snack, Modifier.align(Alignment.BottomCenter).padding(bottom = 140.dp))
        Sheets()
        Dialogs()
    }
}

/** The open page, with Spotify's moves: a new page slides in from the right over the old one (which drifts a
 *  little left), Back slides it away again, and switching tabs cross-fades. Each page keeps its scroll position. */
@Composable
private fun Pages() {
    val holder = androidx.compose.runtime.saveable.rememberSaveableStateHolder()
    androidx.compose.animation.AnimatedContent(
        targetState = Nav.tab to Nav.stack.toList(),
        transitionSpec = {
            val t = androidx.compose.animation.core.tween<androidx.compose.ui.unit.IntOffset>(280)
            val f = androidx.compose.animation.core.tween<Float>(280)
            when (Nav.motion) {
                "push" -> (androidx.compose.animation.slideInHorizontally(t) { it } togetherWith
                           (androidx.compose.animation.slideOutHorizontally(t) { -it / 4 } + androidx.compose.animation.fadeOut(f, 0.6f)))
                    .apply { targetContentZIndex = 1f }
                "pop" -> ((androidx.compose.animation.slideInHorizontally(t) { -it / 4 } + androidx.compose.animation.fadeIn(f, 0.6f)) togetherWith
                          androidx.compose.animation.slideOutHorizontally(t) { it })
                    .apply { targetContentZIndex = -1f }
                else -> androidx.compose.animation.fadeIn(androidx.compose.animation.core.tween(160)) togetherWith
                        androidx.compose.animation.fadeOut(androidx.compose.animation.core.tween(160))
            }
        }, label = "pages") { (tab, stack) ->
        val screen = stack.last()
        Box(Modifier.fillMaxSize().background(C.Bg)) {
            holder.SaveableStateProvider("$tab/${stack.size}/${screen::class.simpleName}") { CurrentScreen(screen) }
        }
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
        is Screen.SettingsPage -> SettingsPageScreen(screen.key)
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
            NavItem(tr("Home"), Icons.Filled.Home, Icons.Outlined.Home, Nav.tab == Tab.HOME) { Nav.switch(Tab.HOME) }
            NavItem(tr("Search"), Icons.Filled.Search, Icons.Outlined.Search, Nav.tab == Tab.SEARCH) { Nav.switch(Tab.SEARCH) }
            NavItem(tr("Your Library"), Icons.Filled.LibraryMusic, Icons.Outlined.LibraryMusic, Nav.tab == Tab.LIBRARY) {
                Nav.switch(Tab.LIBRARY)
            }
            NavItem(tr("Create"), Icons.Filled.Add, Icons.Filled.Add, false) { createOpen = true }
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
                        Text(tr(" ") + AudioOutput.name, maxLines = 1, overflow = TextOverflow.Ellipsis,
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
            if (!t.isItem) {
                val liked = Library.changes.let { isSaved(t) }
                IconButton(onClick = { saveTap(t) }) {
                    Icon(if (liked) Icons.Filled.CheckCircle else Icons.Filled.AddCircleOutline,
                         if (liked) "Saved in…" else "Add to Liked Songs", tint = if (liked) C.Green else C.Text)
                }
            }
            IconButton(onClick = { Player.playPause() }) {
                Icon(if (Player.showPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                     if (Player.showPlaying) "Pause" else "Play", tint = C.Text, modifier = Modifier.size(30.dp))
            }
        }
        val d = Player.duration
        ThinProgress(if (d > 0) Player.position.toFloat() / d else 0f,
                     Modifier.align(Alignment.BottomCenter).padding(horizontal = 8.dp))
    }
}

@Composable
private fun Dialogs() {
    Player.noticeFor?.let {
        AlertDialog(
            onDismissRequest = { Player.acceptNotice(false) },
            title = { Text(tr("Full songs, free")) },
            text = {
                Text(tr("Sevbify plays every song in full by finding it on Bandcamp or YouTube. No account, nothing to sign in to.") +
                     "\n\nOne thing to know: YouTube's terms ask people to listen in its own app, so it's your choice. " +
                     "You can change it any time in Settings. Songs on your phone always play from your files.")
            },
            confirmButton = {
                androidx.compose.material3.Button(onClick = { Player.acceptNotice(true) },
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = androidx.compose.ui.graphics.Color.Black)) {
                    Text(tr("Play full songs"))
                }
            },
            dismissButton = { TextButton(onClick = { Player.acceptNotice(false) }) { Text(tr("Previews only"), color = C.Text) } },
            containerColor = C.Elevated,
        )
    }
    com.sevbify.app.Updater.offer?.let { r -> UpdateDialog(r) }
    com.sevbify.app.ImportCheck.review?.let { (pl, problems) -> ImportReviewDialog(pl, problems) }
    Nav.chosicFor?.let { (id, link) -> ChosicDialog(id, link) }
    if (Nav.carTip) CarTipDialog()
    PairDialogs()
    FeatureTourDialog()
    if (Nav.wrappedOpen) WrappedDialog { Nav.wrappedOpen = false }
    if (Nav.sleepOpen) AlertDialog(onDismissRequest = { Nav.sleepOpen = false }, containerColor = C.Elevated,
        title = { Text("Sleep timer") },
        text = { Column {
            listOf(5, 15, 30, 45, 60).forEach { m ->
                TextButton(onClick = { com.sevbify.app.Player.setSleep(m); Nav.sleepOpen = false }) { Text("$m minutes", color = C.Text) }
            }
            TextButton(onClick = { com.sevbify.app.Player.setSleep(-1); Nav.sleepOpen = false }) {
                Text("End of this ${if (com.sevbify.app.Player.current?.isItem == true) "episode" else "song"}", color = C.Text) }
            if (com.sevbify.app.Player.sleepAt != null || com.sevbify.app.Player.sleepAtEnd)
                TextButton(onClick = { com.sevbify.app.Player.setSleep(null); Nav.sleepOpen = false }) { Text("Turn off timer", color = C.Green) }
        } },
        confirmButton = {})
    if (Nav.hideNoteOpen) {
        var never by remember { mutableStateOf(true) }
        AlertDialog(onDismissRequest = { Nav.hideNoteOpen = false },
            title = { Text("Hidden") },
            text = { Column {
                Text("It won't play by itself any more: playlists, albums, radio and mixes skip it. You can still play it " +
                     "by picking it yourself.\n\nChanged your mind? Settings → Playback → Hidden songs and artists lists " +
                     "everything you've hidden, with a switch to bring each one back.")
                Row(verticalAlignment = Alignment.CenterVertically) {
                    androidx.compose.material3.Checkbox(checked = never, onCheckedChange = { never = it })
                    Text("Don't show this again")
                }
            } },
            confirmButton = { TextButton(onClick = {
                Nav.hideNoteOpen = false
                if (never) { com.sevbify.app.Library.settings.hideNoteSeen = true; com.sevbify.app.Library.changed() }
            }) { Text("OK", color = C.Green) } },
            containerColor = C.Elevated)
    }
    Nav.confirm?.let { (title, text, action) ->
        AlertDialog(onDismissRequest = { Nav.confirm = null },
                    title = { Text(title) }, text = { Text(text) },
                    confirmButton = { TextButton(onClick = { Nav.confirm = null; action() }) { Text(tr("Delete"), color = C.Green) } },
                    dismissButton = { TextButton(onClick = { Nav.confirm = null }) { Text(tr("Cancel"), color = C.Text) } },
                    containerColor = C.Elevated)
    }
    Nav.rename?.let { (start, done) ->
        // Like Spotify: the name is selected, so typing replaces it straight away.
        var text by remember(start) {
            mutableStateOf(androidx.compose.ui.text.input.TextFieldValue(start, androidx.compose.ui.text.TextRange(0, start.length)))
        }
        val focus = remember { androidx.compose.ui.focus.FocusRequester() }
        LaunchedEffect(start) { focus.requestFocus() }
        AlertDialog(onDismissRequest = { Nav.rename = null },
                    title = { Text(Nav.renameTitle) },
                    text = { OutlinedTextField(text, { text = it }, singleLine = true,
                                               modifier = Modifier.focusRequester(focus)) },
                    confirmButton = { TextButton(onClick = { Nav.rename = null; done(text.text.trim().ifEmpty { start }) }) {
                        Text(Nav.renameButton, color = C.Green) } },
                    dismissButton = { TextButton(onClick = { Nav.rename = null }) { Text(tr("Cancel"), color = C.Text) } },
                    containerColor = C.Elevated)
    }
}

/** Ask before deleting, Spotify's way. Never deletes your music files. */
fun confirmDelete(what: String, action: () -> Unit) {
    Nav.confirm = Triple("Delete from Your Library?", "This will delete $what from Your Library. Your music files stay where they are.", action)
}

fun askName(start: String, title: String = "Name", button: String = "Save", done: (String) -> Unit) {
    Nav.renameTitle = title; Nav.renameButton = button
    Nav.rename = start to done
}

/** Spotify's way: name the folder first, then it's made. */
fun askNewFolder(then: (String) -> Unit = {}) {
    askName("New Folder", "Name your folder", "Create") { then(Library.createFolder(it)) }
}

@Suppress("unused")
private fun keepLibrary() = Library.changes

/** Choose cover picture: Android's photo picker (no permission needed; only the photo you pick is shared with the
 *  app), then a 640-pixel copy is kept in the app's own folder as the playlist's cover. */
@Composable
private fun CoverPicker() {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val pick = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia()) { uri ->
        val pl = Nav.coverFor
        Nav.coverFor = null
        if (uri == null || pl == null) return@rememberLauncherForActivityResult
        com.sevbify.app.SevbifyApp.instance.scope.launch {
            val saved = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                runCatching {
                    val src = ctx.contentResolver.openInputStream(uri)?.use { android.graphics.BitmapFactory.decodeStream(it) }
                        ?: return@runCatching null
                    val side = minOf(src.width, src.height)
                    val square = android.graphics.Bitmap.createBitmap(src, (src.width - side) / 2, (src.height - side) / 2, side, side)
                    val small = android.graphics.Bitmap.createScaledBitmap(square, 640, 640, true)
                    val dir = java.io.File(ctx.filesDir, "covers").apply { mkdirs() }
                    dir.listFiles { f -> f.name.startsWith(pl.id + "-") }?.forEach { it.delete() }
                    val f = java.io.File(dir, "${pl.id}-${System.currentTimeMillis()}.jpg")
                    f.outputStream().use { small.compress(android.graphics.Bitmap.CompressFormat.JPEG, 88, it) }
                    android.net.Uri.fromFile(f).toString()
                }.getOrNull()
            }
            if (saved != null) { pl.coverUrl = saved; Library.changed(); Nav.say("Cover picture changed") }
            else Nav.say("⚠ Couldn't use that picture")
        }
    }
    LaunchedEffect(Nav.coverFor) {
        if (Nav.coverFor != null) pick.launch(androidx.activity.result.PickVisualMediaRequest(
            androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia.ImageOnly))
    }
}

/** View credits, like Spotify's: who performed, wrote and produced the song (from MusicBrainz). */
@Composable
private fun CreditsDialog(t: com.sevbify.app.Track) {
    var rows by remember(t.matchKey) { mutableStateOf<List<Pair<String, String>>?>(null) }
    LaunchedEffect(t.matchKey) {
        rows = try {
            val a = com.sevbify.app.Bridge.arr("credits", t.artist, t.title)
            (0 until a.length()).map { i ->
                val o = a.getJSONObject(i)
                val roles = o.optJSONArray("roles")?.let { r -> (0 until r.length()).joinToString(", ") { r.getString(it) } } ?: ""
                o.optString("name") to roles
            }
        } catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e; emptyList() }
    }
    androidx.compose.material3.AlertDialog(
        onDismissRequest = { Nav.creditsFor = null },
        confirmButton = { androidx.compose.material3.TextButton(onClick = { Nav.creditsFor = null }) { Text("Close", color = C.Text) } },
        title = { Text("Credits") },
        text = {
            Column {
                Text("${t.title} · ${t.artist}", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
                when {
                    rows == null -> Text("Looking it up…")
                    rows!!.isEmpty() -> Text("No credits found for this song.")
                    else -> rows!!.take(30).forEach { (name, roles) ->
                        Text(name, style = MaterialTheme.typography.bodyLarge)
                        if (roles.isNotEmpty()) Text(roles, style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(6.dp))
                    }
                }
                Text("From MusicBrainz, the open music encyclopedia.", style = MaterialTheme.typography.labelSmall,
                     modifier = Modifier.padding(top = 8.dp))
            }
        },
        containerColor = C.Elevated)
}
