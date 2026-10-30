package com.sevbify.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.sevbify.app.Library
import com.sevbify.app.Updater
import kotlinx.coroutines.launch
import org.json.JSONObject

/** "Sevbify X is available": Download (then Android's installer opens) or Later. */
@Composable
fun UpdateDialog(r: JSONObject) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val busy = Updater.progress >= 0f
    val ready = Updater.status == "ready"
    AlertDialog(
        onDismissRequest = { if (!busy) Updater.offer = null },
        title = { Text("Update Sevbify") },
        text = {
            Column {
                Text("Sevbify ${r.optString("latest")} is available (you have ${Library.coreVersion}). It installs over " +
                     "this one: your playlists, downloads and settings stay.")
                if (busy) LinearProgressIndicator(progress = { Updater.progress }, color = C.Green,
                                                  modifier = Modifier.fillMaxWidth().padding(top = 16.dp))
                if (Updater.status.isNotEmpty() && !ready) Text(Updater.status, color = C.Sub, modifier = Modifier.padding(top = 8.dp))
            }
        },
        confirmButton = {
            TextButton(enabled = !busy, onClick = {
                if (ready) Updater.install(context)
                else scope.launch { Updater.download(context.applicationContext, r) }
            }) { Text(if (ready) "Install" else if (busy) "Downloading…" else "Download", color = C.Green) }
        },
        dismissButton = {
            TextButton(enabled = !busy, onClick = { Updater.offer = null }) { Text("Later", color = C.Text) }
        },
        containerColor = C.Elevated,
    )
}
