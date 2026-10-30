package com.sevbify.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SpeakerGroup
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.Player
import com.sevbify.app.Track
import org.json.JSONObject

// ==================================================================================================================
// Sharing: Sevbify has no accounts, so a shared song is its link on Spotify or YouTube (or a song.link page)
// ==================================================================================================================

/** Like Spotify's share sheet: the song as a card, then where to share it. Links are looked up only now. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShareSheet(t: Track) {
    val context = LocalContext.current
    var links by remember(t.matchKey) { mutableStateOf<JSONObject?>(null) }
    var failed by remember(t.matchKey) { mutableStateOf("") }
    LaunchedEffect(t.matchKey) {
        try { links = Bridge.obj("share_links", t.artist, t.title, t.pageUrl, t.durationMs) }
        catch (e: Exception) { failed = e.message ?: "" }
    }
    fun link(kind: String) = links?.optString(kind).orEmpty()
    fun exact(kind: String) = links?.optJSONObject("exact")?.optBoolean(kind) == true
    fun send(url: String) {
        if (url.isEmpty()) return
        context.startActivity(Intent.createChooser(
            Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, shareText(t, url)), "Share"))
        Nav.shareFor = null
    }
    fun copy(url: String, what: String) {
        if (url.isEmpty()) return
        context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Song link", url))
        Nav.say("$what link copied")
        Nav.shareFor = null
    }
    ModalBottomSheet(onDismissRequest = { Nav.shareFor = null }, containerColor = C.Elevated) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(bottom = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            // The song card (what Spotify shows as a sticker)
            Column(Modifier.width(220.dp).clip(RoundedCornerShape(10.dp)).background(Color(0xFF2A2A2A)).padding(14.dp)) {
                Cover(t.art, 192.dp, RoundedCornerShape(6.dp))
                Gap(10.dp)
                Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall)
                Text(t.artist, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall.copy(color = C.Sub))
            }
            Gap(16.dp)
            if (links == null && failed.isEmpty()) Muted("Finding the song's links…")
            if (failed.isNotEmpty()) Muted("Couldn't look up links ($failed); search links are used.")
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                ShareTarget(Icons.Filled.MusicNote, Color(0xFF1ED760), if (exact("spotify")) "Spotify" else "Spotify\n(search)") {
                    send(link("spotify").ifEmpty { searchUrl("spotify", t) })
                }
                ShareTarget(Icons.Filled.PlayArrow, Color(0xFFFF0033), if (exact("youtube")) "YouTube" else "YouTube\n(search)") {
                    send(link("youtube").ifEmpty { searchUrl("youtube", t) })
                }
                if (link("songlink").isNotEmpty()) {
                    ShareTarget(Icons.Filled.Link, Color(0xFF3D7BFF), "Any app\n(song.link)") { send(link("songlink")) }
                }
                ShareTarget(Icons.Filled.ContentCopy, Color(0xFF3E3E3E), "Copy\nSpotify link") {
                    copy(link("spotify").ifEmpty { searchUrl("spotify", t) }, "Spotify")
                }
                ShareTarget(Icons.Filled.ContentCopy, Color(0xFF3E3E3E), "Copy\nYouTube link") {
                    copy(link("youtube").ifEmpty { searchUrl("youtube", t) }, "YouTube")
                }
            }
            Gap(8.dp)
            Muted("Spotify or YouTube opens your phone's share menu with the link. Your recent contacts there come from " +
                  "Android itself; Sevbify never sees them.")
        }
    }
}

private fun searchUrl(kind: String, t: Track): String {
    val q = android.net.Uri.encode("${t.artist} ${t.title}")
    return if (kind == "spotify") "https://open.spotify.com/search/$q" else "https://www.youtube.com/results?search_query=$q"
}

private fun shareText(t: Track, url: String) = "${t.title}" + (if (t.artist.isNotEmpty()) " by ${t.artist}" else "") + "\n$url"

@Composable
private fun ShareTarget(icon: ImageVector, colour: Color, label: String, onClick: () -> Unit) {
    Column(Modifier.width(76.dp).clickable(onClick = onClick), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(56.dp).clip(CircleShape).background(colour), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Color.White, modifier = Modifier.size(26.dp))
        }
        Gap(6.dp)
        Text(label, style = MaterialTheme.typography.bodySmall, maxLines = 2, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
    }
}

// ==================================================================================================================
// Connect: where the sound comes out (this phone's speaker, wired or Bluetooth headphones)
// ==================================================================================================================

/** The phone's current audio output, kept up to date as headphones connect and disconnect. */
object AudioOutput {
    var name by mutableStateOf("This phone")
    var kind by mutableStateOf("speaker")           // speaker | wired | bluetooth | usb
    private var started = false

    fun start(context: Context) {
        if (started) return
        started = true
        val am = context.getSystemService(AudioManager::class.java)
        am.registerAudioDeviceCallback(object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(added: Array<out AudioDeviceInfo>?) = refresh(am)
            override fun onAudioDevicesRemoved(removed: Array<out AudioDeviceInfo>?) = refresh(am)
        }, null)
        refresh(am)
    }

    private fun refresh(am: AudioManager) {
        val outs = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        fun of(vararg types: Int) = outs.firstOrNull { it.type in types }
        val bt = of(AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLE_SPEAKER)
        val wired = of(AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_WIRED_HEADSET)
        val usb = of(AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_DEVICE)
        when {
            bt != null -> { kind = "bluetooth"; name = bt.productName?.toString()?.ifBlank { null } ?: "Bluetooth" }
            wired != null -> { kind = "wired"; name = "Headphones" }
            usb != null -> { kind = "usb"; name = usb.productName?.toString()?.ifBlank { null } ?: "USB audio" }
            else -> { kind = "speaker"; name = "This phone" }
        }
    }

    val icon: ImageVector get() = if (kind == "speaker") Icons.Filled.PhoneAndroid else Icons.Filled.Headphones
}

/** Spotify's "Connect" sheet: what's playing where, the system's output picker and Bluetooth. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConnectSheet() {
    val context = LocalContext.current
    val t = Player.current
    ModalBottomSheet(onDismissRequest = { Nav.connectOpen = false }, containerColor = C.Elevated) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp)) {
            Text("Connect", style = MaterialTheme.typography.headlineSmall)
            Gap(12.dp)
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Color(0xFF2A2A2A)).padding(16.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(AudioOutput.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (AudioOutput.kind == "bluetooth") Icon(Icons.Filled.Bluetooth, null, tint = C.Sub, modifier = Modifier.size(16.dp))
                        Text(" This phone", style = MaterialTheme.typography.bodyMedium.copy(color = C.Sub))
                    }
                    if (t != null) Text("${t.title} – ${t.artist}", color = C.Green, maxLines = 1, overflow = TextOverflow.Ellipsis,
                                        style = MaterialTheme.typography.bodyMedium)
                }
                Icon(AudioOutput.icon, null, tint = C.Green, modifier = Modifier.size(44.dp))
            }
            Gap(12.dp)
            Muted("Sevbify plays on this phone. To play on a speaker, TV or other headphones, pick them below.")
            Gap(12.dp)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (Build.VERSION.SDK_INT >= 34) {
                    ConnectButton(Icons.Filled.SpeakerGroup, "Choose output", Modifier.weight(1f)) {
                        // Android's own output switcher (phone, Bluetooth, and speakers it can reach)
                        val shown = try { android.media.MediaRouter2.getInstance(context).showSystemOutputSwitcher() } catch (e: Exception) { false }
                        if (!shown) openBluetooth(context)
                    }
                }
                ConnectButton(Icons.Filled.Bluetooth, "Bluetooth", Modifier.weight(1f)) { openBluetooth(context) }
            }
            Gap(16.dp)
        }
    }
}

private fun openBluetooth(context: Context) {
    try { context.startActivity(Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    catch (e: Exception) { Nav.say("Couldn't open Bluetooth settings") }
}

@Composable
private fun ConnectButton(icon: ImageVector, label: String, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.clip(RoundedCornerShape(10.dp)).background(Color(0xFF2A2A2A)).clickable(onClick = onClick).padding(vertical = 14.dp),
           horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, null, tint = C.Green)
        Gap(4.dp)
        Text(label, color = C.Green, style = MaterialTheme.typography.bodyMedium)
    }
}

// ==================================================================================================================
// Lyrics: a preview card under Now playing and the full, time-synced lyrics (like Spotify)
// ==================================================================================================================

object LyricsState {
    var key by mutableStateOf("")
    var lines by mutableStateOf<List<Pair<Long, String>>>(emptyList())     // synced lines, or empty
    var plain by mutableStateOf("")
    var source by mutableStateOf("")
    var status by mutableStateOf("")                                        // "", "Loading…", "No lyrics found"

    suspend fun load(t: Track) {
        if (key == t.matchKey) return
        key = t.matchKey; lines = emptyList(); plain = ""; source = ""; status = "Loading lyrics…"
        try {
            val r = Bridge.call("lyrics", t.artist, t.title, t.album, t.durationMs)
            if (key != t.matchKey) return
            if (r is JSONObject) {
                val a = r.optJSONArray("lines")
                lines = if (a == null) emptyList() else (0 until a.length()).map { i ->
                    val p = a.getJSONArray(i); p.getLong(0) to p.getString(1)
                }
                plain = r.optString("plain"); source = r.optString("source")
                status = if (r.optBoolean("instrumental") && plain.isBlank()) "Instrumental: no lyrics" else ""
            } else status = if (Library.settings.online) "No lyrics found for this song" else "Lyrics need the internet"
        } catch (e: Exception) {
            if (key == t.matchKey) status = "Lyrics aren't available right now"
        }
    }

    fun currentIndex(ms: Long): Int {
        var idx = -1
        for ((i, p) in lines.withIndex()) { if (p.first <= ms) idx = i else break }
        return idx
    }

    val display: List<String> get() = if (lines.isNotEmpty()) lines.map { it.second } else plain.lines()
}

/** The "Lyrics preview" card under Now playing. */
@Composable
fun LyricsCard(t: Track) {
    if (!Library.settings.lyrics || t.isItem) return
    LaunchedEffect(t.matchKey) { LyricsState.load(t) }
    val shown = LyricsState.display.filter { it.isNotBlank() }
    val now = LyricsState.currentIndex(Player.position)
    Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp))
               .background(Color(0xFF4A4A4A)).clickable(enabled = shown.isNotEmpty()) { Nav.lyricsOpen = true }.padding(18.dp)) {
        Text("Lyrics preview", style = MaterialTheme.typography.titleMedium)
        Gap(10.dp)
        if (shown.isEmpty()) {
            Text(LyricsState.status.ifEmpty { "No lyrics" }, style = MaterialTheme.typography.bodyMedium.copy(color = C.Sub))
        } else {
            val start = if (LyricsState.lines.isNotEmpty()) now.coerceAtLeast(0) else 0
            LyricsState.display.drop(start).filter { it.isNotBlank() }.take(5).forEachIndexed { i, line ->
                Text(line, fontSize = 20.sp, fontWeight = FontWeight.Bold, lineHeight = 26.sp,
                     color = if (i == 0 && now >= 0) Color.White else Color(0xCCFFFFFF), modifier = Modifier.padding(vertical = 4.dp))
            }
            Gap(10.dp)
            Box(Modifier.clip(RoundedCornerShape(50)).background(Color.White).clickable { Nav.lyricsOpen = true }
                    .padding(horizontal = 18.dp, vertical = 8.dp)) {
                Text("Show lyrics", color = Color.Black, fontWeight = FontWeight.Bold)
            }
            if (LyricsState.source.isNotEmpty()) {
                Gap(8.dp)
                Text("Lyrics: ${LyricsState.source}", style = MaterialTheme.typography.labelSmall.copy(color = C.Sub))
            }
        }
    }
}

/** Full-screen lyrics: the line being sung is white and kept in view; tap a line to jump there (synced lyrics). */
@Composable
fun LyricsScreen() {
    val t = Player.current ?: run { Nav.lyricsOpen = false; return }
    val list = rememberLazyListState()
    val now = LyricsState.currentIndex(Player.position)
    LaunchedEffect(now) { if (now > 2) list.animateScrollToItem((now - 2).coerceAtLeast(0)) }
    Column(Modifier.fillMaxSize().background(Color(0xFF4A4A4A)).statusBarsPadding().navigationBarsPadding()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { Nav.lyricsOpen = false }) { Icon(Icons.Filled.KeyboardArrowDown, "Close", Modifier.size(32.dp)) }
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(t.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(t.artist, style = MaterialTheme.typography.bodySmall, maxLines = 1)
            }
            IconButton(onClick = { Nav.shareFor = t }) { Icon(Icons.Filled.MoreHoriz, "Share") }
        }
        LazyColumn(Modifier.weight(1f).padding(horizontal = 20.dp), state = list) {
            itemsIndexed(LyricsState.display) { i, line ->
                val synced = LyricsState.lines.isNotEmpty()
                Text(line.ifBlank { "♪" }, fontSize = 26.sp, fontWeight = FontWeight.Bold, lineHeight = 32.sp,
                     color = when { !synced -> Color.White; i == now -> Color.White; i < now -> Color(0x99FFFFFF); else -> Color(0x66000000) },
                     modifier = Modifier.padding(vertical = 8.dp).clickable(enabled = synced) { Player.seekTo(LyricsState.lines[i].first) })
            }
            item { Gap(24.dp) }
        }
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(clock(Player.position), style = MaterialTheme.typography.labelSmall)
            Spacer(Modifier.weight(1f))
            Box(Modifier.size(64.dp).clip(CircleShape).background(Color.White).clickable { Player.playPause() }, contentAlignment = Alignment.Center) {
                Icon(if (Player.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                     if (Player.isPlaying) "Pause" else "Play", tint = Color.Black, modifier = Modifier.size(34.dp))
            }
            Spacer(Modifier.weight(1f))
            Text(clock(Player.duration), style = MaterialTheme.typography.labelSmall)
        }
    }
}
