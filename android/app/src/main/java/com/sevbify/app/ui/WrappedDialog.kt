package com.sevbify.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sevbify.app.Bridge
import com.sevbify.app.Library

/** Your listening stats ("Wrapped"), worked out on this phone from what you've played (core/wrapped.py). */
@Composable
fun WrappedDialog(onClose: () -> Unit) {
    var period by remember { mutableStateOf("This year") }
    var st by remember { mutableStateOf<org.json.JSONObject?>(null) }
    LaunchedEffect(period) {
        st = try { Bridge.obj("wrapped", Library.listensJson(), period) } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            org.json.JSONObject()
        }
    }
    AlertDialog(onDismissRequest = onClose, containerColor = C.Elevated,
        title = { Text("Your Wrapped") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                androidx.compose.foundation.layout.Row(Modifier.padding(bottom = 8.dp)) {
                    listOf("4 weeks", "6 months", "This year", "All time").forEach { p -> Chip(p, period == p) { period = p } }
                }
                val s = st
                if (s == null) Text("Working it out…")
                else if (s.optInt("plays") == 0) Text("Nothing played in this period yet.")
                else {
                    Text("%,d".format(s.optInt("minutes")), fontSize = 40.sp, style = MaterialTheme.typography.headlineLarge)
                    Text("minutes · ${s.optInt("plays")} plays · ${s.optInt("artists")} artists" +
                         (s.optString("time_of_day").takeIf { it.isNotEmpty() && it != "null" }?.let { " · mostly in the $it" } ?: ""),
                         color = C.Sub)
                    Text("Top artists", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
                    val a = s.optJSONArray("top_artists")
                    for (i in 0 until (a?.length() ?: 0)) a!!.getJSONObject(i).let {
                        Text("${i + 1}. ${it.optString("artist")}  ·  ${it.optInt("plays")} plays") }
                    Text("Top songs", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
                    val t = s.optJSONArray("top_songs")
                    for (i in 0 until (t?.length() ?: 0)) t!!.getJSONObject(i).let {
                        Text("${i + 1}. ${it.optString("title")} · ${it.optString("artist")}") }
                }
                Text("Worked out on this phone from what you've played; nothing is sent anywhere.", color = C.Sub,
                     style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
            }
        },
        confirmButton = { TextButton(onClick = onClose) { Text("Close", color = C.Green) } })
}
