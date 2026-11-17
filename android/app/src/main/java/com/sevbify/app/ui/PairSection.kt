package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.sevbify.app.PairLink

/** Settings → Your computer: pair with Sevbify on a computer by scanning its QR code; who you're paired with. */
@Composable
fun PairSection() {
    val scanner = androidx.activity.compose.rememberLauncherForActivityResult(ScanContract()) { result ->
        val text = result.contents ?: return@rememberLauncherForActivityResult
        val code = PairLink.parse(text)
        if (code == null) Nav.say("That isn't a Sevbify pairing code") else PairLink.pendingCode = code
    }
    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text("Pair this phone with Sevbify on your computer to send songs and folders either way. It only works on " +
             "your own Wi-Fi: nothing goes through the internet, everything is encrypted, and you say yes to every " +
             "transfer. On the computer: Settings → Your phone → Pair a phone.",
             style = MaterialTheme.typography.bodySmall)
        val c = PairLink.computer
        if (c != null) {
            Row(Modifier.padding(top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(c.name, style = MaterialTheme.typography.bodyLarge)
                    Text(PairLink.status.ifEmpty { "Not connected" } +
                         (if (PairLink.progress.isNotEmpty()) " · ${PairLink.progress}" else ""),
                         style = MaterialTheme.typography.bodySmall, color = if (PairLink.connected) C.Green else C.Sub)
                }
                TextButton(onClick = {
                    Nav.confirm = Triple("Remove ${c.name}?", "This phone forgets the computer. To pair again, scan a new code.") {
                        PairLink.forget(); Nav.say("Removed")
                    }
                }) { Text("Remove", color = C.Text) }
            }
        } else if (PairLink.status.isNotEmpty()) {
            Text(PairLink.status, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
        }
        OutlinedButton(onClick = {
            scanner.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE).setBeepEnabled(false)
                .setOrientationLocked(false).setPrompt("Scan the code on your computer"))
        }, modifier = Modifier.padding(top = 12.dp)) {
            Text(if (c == null) "Pair with a computer" else "Pair with another computer", color = C.Text)
        }
        Text("Your phone's camera app can also scan the code.", style = MaterialTheme.typography.bodySmall,
             modifier = Modifier.padding(top = 8.dp))
    }
}

/** "Pair with <computer>?" after scanning, and "Receive music?" when the computer sends some. */
@Composable
fun PairDialogs() {
    PairLink.pendingCode?.let { code ->
        AlertDialog(onDismissRequest = { PairLink.pendingCode = null },
            title = { Text("Pair with ${code.name}?") },
            text = { Text("Sevbify on this phone and on ${code.name} (${code.addresses.first()}) will be able to send each " +
                          "other music, on your Wi-Fi only. You'll be asked before anything is saved." +
                          (PairLink.computer?.let { "\n\nThis replaces ${it.name}." } ?: "") +
                          "\n\nOnly pair with a code you scanned from your own computer's screen.") },
            confirmButton = { TextButton(onClick = { PairLink.pair(code) }) { Text("Pair", color = C.Green) } },
            dismissButton = { TextButton(onClick = { PairLink.pendingCode = null }) { Text("Cancel", color = C.Text) } },
            containerColor = C.Elevated)
    }
    PairLink.offer?.let { offer ->
        var ready by remember(offer.id) { mutableStateOf(false) }
        LaunchedEffect(offer.id) { kotlinx.coroutines.delay(1000); ready = true }   // no accidental taps
        val mb = offer.total / (1024.0 * 1024.0)
        val names = offer.items.take(3).joinToString(", ") { it.first.substringAfterLast('/') } +
            if (offer.items.size > 3) "…" else ""
        AlertDialog(onDismissRequest = { PairLink.answer(false) },
            title = { Text("Receive music?") },
            text = { Text("${PairLink.computer?.name ?: "Your computer"} wants to send you ${offer.items.size} " +
                          "file${if (offer.items.size == 1) "" else "s"} (${"%.1f".format(mb)} MB)" +
                          (if (offer.title.isNotEmpty()) " — ${offer.title}" else "") + ".\n\n$names\n\n" +
                          "They'll be saved in Music/Sevbify.") },
            confirmButton = {
                Button(onClick = { PairLink.answer(true) }, enabled = ready,
                       colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) { Text("Accept") }
            },
            dismissButton = { TextButton(onClick = { PairLink.answer(false) }) { Text("Decline", color = C.Text) } },
            containerColor = C.Elevated)
    }
}

/** "Support the artist": where to buy this music straight from the artist (core/support.py). Each link shows its
 *  website; nothing opens until you tap it; no link is guessed. */
@Composable
fun SupportSheet(t: com.sevbify.app.Track) = SupportLinksSheet(
    key = t.matchKey, title = "Support ${t.artist}",
    subtitle = "Buy their music straight from them, or from the closest thing.",
    empty = "No links from the artist themselves were found, so none are shown (Sevbify never guesses).",
    needsOnline = true, onClose = { Nav.supportFor = null },
) { com.sevbify.app.Bridge.arr("support_links", t.artist, t.title, t.pageUrl, t.source) }

/** A podcast's own support links, from its feed (<podcast:funding>) and its website. */
@Composable
fun ShowSupportSheet(s: com.sevbify.app.Show) = SupportLinksSheet(
    key = s.key, title = "Support ${s.title}",
    subtitle = "Back the show directly, through its own links.",
    empty = "This show doesn't list a support link in its feed.",
    needsOnline = false, onClose = { Nav.supportShow = null },
) { com.sevbify.app.Bridge.arr("show_support_links", s.json.toString()) }

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun SupportLinksSheet(key: String, title: String, subtitle: String, empty: String, needsOnline: Boolean,
                              onClose: () -> Unit, load: suspend () -> org.json.JSONArray) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var links by remember(key) { mutableStateOf<org.json.JSONArray?>(null) }
    LaunchedEffect(key) {
        links = try { load() } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            org.json.JSONArray()
        }
    }
    androidx.compose.material3.ModalBottomSheet(onDismissRequest = onClose, containerColor = C.Elevated) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp, bottom = 12.dp))
            val l = links
            when {
                l == null -> Text("Looking for their own links…", style = MaterialTheme.typography.bodyMedium)
                l.length() == 0 -> Text(if (!needsOnline || com.sevbify.app.Library.settings.online) empty
                    else "Go online to find where to buy this artist's music.", style = MaterialTheme.typography.bodyMedium)
                else -> { for (i in 0 until l.length()) {
                    val o = l.getJSONObject(i)
                    val url = o.optString("url")
                    if (!url.startsWith("https://")) continue
                    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)
                        .clip(androidx.compose.foundation.shape.RoundedCornerShape(8.dp)).background(Color(0xFF2A2A2A))
                        .clickable {
                            onClose()
                            try { context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))) }
                            catch (_: Exception) {}
                        }.padding(14.dp)) {
                        Text(o.optString("label"), style = MaterialTheme.typography.bodyLarge)
                        Text("Opens " + o.optString("site"), style = MaterialTheme.typography.bodySmall)
                    }
                } }
            }
            Text("Enjoying this? Support the artists and podcasters you love: buy their music, go to their shows, or back their show directly.",
                 style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 14.dp))
        }
    }
}
