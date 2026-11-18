package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sevbify.app.Bridge
import com.sevbify.app.Library
import com.sevbify.app.Playlist
import com.sevbify.app.SevbifyApp
import com.sevbify.app.tr
import kotlinx.coroutines.launch
import org.json.JSONArray

/** The ways Flow can order a playlist (the same as the computer's; the ordering is core/flow_order.py). */
private val FLOW_MODES = listOf(
    Triple("wind_down", "Energy to calm", "Big, exciting songs first, then the middle ones, ending calm. (Default)"),
    Triple("build", "Calm to energy", "Starts calm and builds up to the big, exciting songs: good for workouts or getting ready."),
    Triple("waves", "Waves", "Builds up, eases off, builds up again: hot, cold, hot, cold."),
    Triple("smooth", "Smooth", "Every song leads gently into the next; genres blend instead of jumping."),
    Triple("mix", "Mix it up", "A bit of everything: calm, energetic and in-between songs spread through, shuffled."),
    Triple("genre", "Grouped by genre", "All the synthwave together, then the rock and so on, each smooth inside."),
)

/** Playlist ••• → Flow this playlist…: choose how the songs should flow; a new playlist "<name> · Flow" is made in
 *  that order. The original playlist isn't touched, and songs in the new one can be moved or removed as usual. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FlowSheet(pl: Playlist) {
    var mode by remember { mutableStateOf("wind_down") }
    var apart by remember { mutableStateOf(true) }
    var energetic by remember { mutableStateOf(false) }
    var working by remember { mutableStateOf(false) }
    var progress by remember { mutableFloatStateOf(0f) }
    var note by remember { mutableStateOf("") }
    val close = { if (!working) Nav.flowFor = null }

    fun go() {
        working = true
        val songs = pl.tracks.toList()
        SevbifyApp.instance.scope.launch {
            try {
                val feats = JSONArray()
                songs.chunked(10).forEachIndexed { k, chunk ->
                    note = "Listening to ${minOf((k + 1) * 10, songs.size)} of ${songs.size} songs…"
                    val part = Bridge.arr("flow_features", JSONArray().also { a -> chunk.forEach { a.put(it.toJson()) } }.toString())
                    for (i in 0 until part.length()) feats.put(part.get(i))
                    progress = minOf(1f, (k + 1) * 10f / songs.size)
                }
                val all = JSONArray().also { a -> songs.forEach { a.put(it.toJson()) } }
                val res = Bridge.obj("flow_order", all.toString(), feats.toString(), mode, apart, if (energetic) "energetic" else "calm")
                val order = res.getJSONArray("order")
                val ordered = (0 until order.length()).map { songs[order.getInt(it)] }
                val newPl = Library.newPlaylist("${pl.name} · Flow", ordered)
                newPl.description = "${res.optString("mode_name")} order of “${pl.name}”: ${res.optString("summary")}. " +
                    "Drag songs to change it."
                Library.changed()
                working = false
                Nav.flowFor = null
                Nav.go(Screen.PlaylistPage(newPl.id))
                Nav.say("Made “${newPl.name}”. Your original playlist wasn't changed.")
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                working = false
                note = "Flow didn't work: ${e.message}"
            }
        }
    }

    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 20.dp)) {
            Text(tr("Flow this playlist"), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text("Puts the ${pl.tracks.size} songs of “${pl.name}” in an order that's nice to listen to, using each " +
                 "song's tempo, loudness and style (synthwave, chillwave, soft rock, metal…). It makes a new playlist, " +
                 "“${pl.name} · Flow”: yours stays exactly as it is, and you can move songs around in the new one.",
                 style = MaterialTheme.typography.bodyMedium, color = C.Sub)
            Spacer(Modifier.height(12.dp))
            FLOW_MODES.forEach { (key, name, text) ->
                val on = mode == key
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp).clip(RoundedCornerShape(8.dp))
                        .background(if (on) Color(0xFF2A2A2A) else Color(0xFF1F1F1F))
                        .clickable(enabled = !working) { mode = key }.padding(horizontal = 6.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = on, onClick = { mode = key }, enabled = !working,
                                colors = RadioButtonDefaults.colors(selectedColor = C.Green))
                    Column {
                        Text(tr(name), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Text(tr(text), style = MaterialTheme.typography.bodySmall, color = C.Sub)
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(tr("Don't play the same artist twice in a row"), modifier = Modifier.weight(1f))
                Switch(apart, { apart = it }, enabled = !working,
                       colors = SwitchDefaults.colors(checkedTrackColor = C.Green))
            }
            Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(tr("Start with"))
                listOf(false to "a calm song", true to "an energetic song").forEach { (e, label) ->
                    FilterChip(selected = energetic == e, onClick = { energetic = e }, enabled = !working,
                               label = { Text(tr(label)) },
                               colors = FilterChipDefaults.filterChipColors(selectedContainerColor = C.Green,
                                                                            selectedLabelColor = Color.Black))
                }
            }
            if (working || note.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                if (working) LinearProgressIndicator(progress = { progress }, color = C.Green, modifier = Modifier.fillMaxWidth())
                Text(note, style = MaterialTheme.typography.bodySmall, color = C.Sub, modifier = Modifier.padding(top = 4.dp))
            }
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = close, enabled = !working) { Text(tr("Cancel"), color = C.Text) }
                Spacer(Modifier.width(8.dp))
                Button(onClick = { go() }, enabled = !working,
                       colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) {
                    Text(tr("Make Flow playlist"), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}
