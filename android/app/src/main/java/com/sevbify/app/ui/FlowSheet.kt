package com.sevbify.app.ui

import androidx.compose.foundation.background
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Icon
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.Icons
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.border
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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
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

/** Sort by energy's three choices (the same as the computer's and iPhone's; the ordering is core/flow_order.py). */
private val ENERGY_CARDS = listOf(
    Triple("wind_down", "Energetic → Easing down → Calm", "The most energetic songs first, settling down to the calmest."),
    Triple("build", "Calm → Ramping up → Energetic", "Starts with the calmest songs and builds up to the most energetic."),
    Triple("mix", "Mixed energies throughout", "Calm, in-between and energetic songs spread all the way through."),
)
private val SHORT = mapOf("wind_down" to "Energetic to calm", "build" to "Calm to energetic", "mix" to "Mixed energies")

/** The line on each card: how the energy moves from the first song (left) to the last (right); y 0 = energetic. */
private val SHAPES = mapOf(
    "wind_down" to listOf(0f to .12f, .25f to .16f, .45f to .38f, .7f to .62f, 1f to .8f),
    "build" to listOf(0f to .8f, .25f to .76f, .45f to .55f, .7f to .3f, 1f to .12f),
    "mix" to listOf(0f to .5f, .09f to .2f, .18f to .7f, .27f to .3f, .36f to .82f, .45f to .15f, .55f to .6f,
                    .64f to .25f, .73f to .78f, .82f to .2f, .91f to .66f, 1f to .4f),
)

@Composable
private fun EnergyLine(mode: String, on: Boolean) {
    val colour = if (on) C.Green else Color.White
    androidx.compose.foundation.Canvas(Modifier.fillMaxWidth().height(56.dp)) {
        val pts = SHAPES.getValue(mode).map { (x, y) -> androidx.compose.ui.geometry.Offset(6f + x * (size.width - 12f), 6f + y * (size.height - 12f)) }
        val path = androidx.compose.ui.graphics.Path().apply {
            moveTo(pts[0].x, pts[0].y)
            if (mode == "mix") pts.drop(1).forEach { lineTo(it.x, it.y) }
            else pts.zipWithNext { a, b -> val m = (a.x + b.x) / 2; cubicTo(m, a.y, m, b.y, b.x, b.y) }
        }
        drawPath(path, colour, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 4.dp.toPx(),
            cap = androidx.compose.ui.graphics.StrokeCap.Round, join = androidx.compose.ui.graphics.StrokeJoin.Round))
    }
}

/** Playlist ••• → Sort by energy…: three big cards; a new playlist "<name> · Energetic to calm" (etc.) is made in that
 *  order. The original playlist isn't touched, and songs in the new one can be moved or removed as usual. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FlowSheet(pl: Playlist) {
    var mode by remember { mutableStateOf("wind_down") }
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
                    note = "Sorting by energy: ${minOf((k + 1) * 10, songs.size)} of ${songs.size} songs…"
                    val part = Bridge.arr("flow_features", JSONArray().also { a -> chunk.forEach { a.put(it.toJson()) } }.toString())
                    for (i in 0 until part.length()) feats.put(part.get(i))
                    progress = minOf(1f, (k + 1) * 10f / songs.size)
                }
                val all = JSONArray().also { a -> songs.forEach { a.put(it.toJson()) } }
                val res = Bridge.obj("flow_order", all.toString(), feats.toString(), mode, true, "calm")
                val order = res.getJSONArray("order")
                val ordered = (0 until order.length()).map { songs[order.getInt(it)] }
                val newPl = Library.newPlaylist("${pl.name} · ${SHORT[mode] ?: "Sorted"}", ordered)
                newPl.description = "“${pl.name}” sorted by energy: ${res.optString("mode_name")}. Drag songs to change it."
                Library.changed()
                working = false
                Nav.flowFor = null
                Nav.go(Screen.PlaylistPage(newPl.id))
                Nav.say("Made “${newPl.name}”. Your original playlist wasn't changed.")
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                working = false
                note = "Sorting by energy didn't work: ${e.message}"
            }
        }
    }

    ModalBottomSheet(onDismissRequest = close, containerColor = C.Elevated,
        sheetState = androidx.compose.material3.rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlaylistCover(pl, 48.dp)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(tr("Sort by energy"), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text("${pl.name} · ${pl.tracks.size} songs", style = MaterialTheme.typography.bodySmall, color = C.Sub)
                }
            }
            Spacer(Modifier.height(10.dp))
            Text(tr("Sorting by energy makes a copy of this playlist, with the songs arranged in the energy flow you " +
                    "choose. Your original playlist stays exactly as it is."),
                 style = MaterialTheme.typography.bodyMedium, color = C.Sub)
            ENERGY_CARDS.forEach { (key, name, text) ->
                val on = mode == key
                Box(Modifier.fillMaxWidth().padding(top = 12.dp).clip(RoundedCornerShape(12.dp))
                        .background(if (on) androidx.compose.ui.graphics.Brush.verticalGradient(listOf(Color(0xFF1F3A29), Color(0xFF232323)))
                                    else androidx.compose.ui.graphics.SolidColor(Color(0xFF2A2A2A)))
                        .border(2.dp, if (on) C.Green else Color.Transparent, RoundedCornerShape(12.dp))
                        .clickable(enabled = !working) { mode = key }.padding(16.dp)) {
                    Column {
                        EnergyLine(key, on)
                        Row { Text(tr("Start"), fontSize = 10.sp, color = Color(0xFF888888)); Spacer(Modifier.weight(1f))
                              Text(tr("End"), fontSize = 10.sp, color = Color(0xFF888888)) }
                        Text(tr(name), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold,
                             modifier = Modifier.padding(top = 6.dp))
                        Text(tr(text), style = MaterialTheme.typography.bodySmall, color = C.Sub)
                    }
                    if (on) Box(Modifier.align(Alignment.TopEnd).size(22.dp).clip(CircleShape).background(C.Green),
                                contentAlignment = Alignment.Center) {
                        Icon(Icons.Filled.Check, null, tint = Color.Black, modifier = Modifier.size(16.dp))
                    }
                }
            }
            if (working || note.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                if (working) LinearProgressIndicator(progress = { progress }, color = C.Green, modifier = Modifier.fillMaxWidth())
                Text(note, style = MaterialTheme.typography.bodySmall, color = C.Sub, modifier = Modifier.padding(top = 4.dp))
            }
            Button(onClick = { go() }, enabled = !working, modifier = Modifier.fillMaxWidth().padding(top = 16.dp).height(50.dp),
                   colors = ButtonDefaults.buttonColors(containerColor = C.Green, contentColor = Color.Black)) {
                Text(tr("Create sorted playlist"), fontWeight = FontWeight.ExtraBold)
            }
            TextButton(onClick = close, enabled = !working, modifier = Modifier.align(Alignment.CenterHorizontally).padding(bottom = 8.dp)) {
                Text(tr("Cancel"), color = C.Text, fontWeight = FontWeight.Bold)
            }
        }
    }
}
