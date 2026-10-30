package com.sevbify.app.ui

import com.sevbify.app.tr
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.sevbify.app.MusicServers
import kotlinx.coroutines.launch

/** Settings → Data-saving and offline → Music servers: your own Jellyfin or Nextcloud. */
@Composable
fun ServersSection() {
    val scope = rememberCoroutineScope()
    var adding by remember { mutableStateOf<String?>(null) }
    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text(tr("Music servers"), style = MaterialTheme.typography.bodyLarge)
        Text("Play music from your own Jellyfin or Nextcloud server. Sevbify talks only to the address you type. " +
             "Jellyfin keeps just a revocable sign-in token; for Nextcloud use an app password. The sign-in stays in " +
             "Sevbify's private storage on this phone.", style = MaterialTheme.typography.bodySmall)
        MusicServers.list.toList().forEach { srv ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(srv.optString("name"), style = MaterialTheme.typography.bodyMedium)
                    Text(srv.optString("url"), style = MaterialTheme.typography.bodySmall, maxLines = 1)
                }
                IconButton(onClick = {
                    scope.launch {
                        try { val pl = MusicServers.refresh(srv); Nav.say("${pl.name}: ${pl.tracks.size} songs") }
                        catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e; Nav.say("⚠ ${e.message}") }
                    }
                }) { Icon(Icons.Filled.Refresh, "Reload songs", tint = C.Sub) }
                IconButton(onClick = { MusicServers.remove(srv.optString("id")); Nav.say("Server removed from this phone") }) {
                    Icon(Icons.Filled.Close, "Remove", tint = C.Sub)
                }
            }
        }
        Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { adding = "jellyfin" }) { Text("Add Jellyfin", color = C.Text) }
            OutlinedButton(onClick = { adding = "webdav" }) { Text("Add Nextcloud", color = C.Text) }
        }
    }
    adding?.let { kind -> AddServerDialog(kind) { adding = null } }
}

@Composable
private fun AddServerDialog(kind: String, close: () -> Unit) {
    val scope = rememberCoroutineScope()
    var address by remember { mutableStateOf("") }
    var user by remember { mutableStateOf("") }
    var secret by remember { mutableStateOf("") }
    var folder by remember { mutableStateOf("Music") }
    var busy by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = { if (!busy) close() },
        title = { Text(if (kind == "jellyfin") "Add a Jellyfin server" else "Add a Nextcloud server") },
        text = {
            Column {
                OutlinedTextField(address, { address = it }, singleLine = true, label = { Text("Address") },
                                  placeholder = { Text("https://music.example.com") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(user, { user = it }, singleLine = true, label = { Text("User name") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(secret, { secret = it }, singleLine = true,
                                  label = { Text(if (kind == "jellyfin") "Password (used once)" else "App password") },
                                  visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
                if (kind == "webdav") {
                    OutlinedTextField(folder, { folder = it }, singleLine = true, label = { Text("Music folder") },
                                      modifier = Modifier.fillMaxWidth())
                    Text("Nextcloud → Settings → Security → Create new app password.", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy && address.isNotBlank() && user.isNotBlank() && secret.isNotEmpty(), onClick = {
                busy = true
                scope.launch {
                    try {
                        val pl = MusicServers.add(kind, address.trim(), user.trim(), secret, folder.trim())
                        Nav.say("Connected: “${pl.name}” has ${pl.tracks.size} songs")
                        close()
                    } catch (e: Exception) {
                        if (e is kotlinx.coroutines.CancellationException) throw e
                        Nav.say("⚠ Couldn't connect: ${e.message}")
                    } finally { busy = false; secret = "" }
                }
            }) { Text(if (busy) "Connecting…" else "Connect", color = C.Green) }
        },
        dismissButton = { TextButton(onClick = { if (!busy) close() }) { Text(tr("Cancel"), color = C.Text) } },
        containerColor = C.Elevated,
    )
}
