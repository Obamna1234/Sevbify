package com.sevbify.app.ui

import com.sevbify.app.tr
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.sevbify.app.CarHelp
import com.sevbify.app.Library
import com.sevbify.app.PlaybackService

private const val AUTO_STEPS =
    "Android Auto only shows apps from the Play Store until you allow others. One time:\n" +
    "1. Open Android Auto's settings (button below; or Settings → Connected devices → Connection preferences → Android Auto).\n" +
    "2. Scroll to the bottom and tap \"Version\" about 10 times, then allow developer settings.\n" +
    "3. Tap ⋮ (top right) → Developer settings → tick \"Unknown sources\".\n" +
    "4. Unplug the phone from the car (or turn the car off and on) and connect again.\n" +
    "Sevbify can't switch this on for you: Android doesn't let apps change it."

/** Settings → Car. */
@Composable
fun CarSettings() {
    val context = LocalContext.current
    val installed = CarHelp.androidAutoInstalled(context)
    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text("Bluetooth (any car)", style = MaterialTheme.typography.titleSmall)
        Text("Works already: music plays through the car, the song's name shows on its screen, and the steering-wheel " +
             "and car buttons play, pause and skip.", style = MaterialTheme.typography.bodySmall,
             modifier = Modifier.padding(bottom = 12.dp))
        Text("Android Auto", style = MaterialTheme.typography.titleSmall)
        Text(when {
            !installed -> "Android Auto isn't on this phone. With it, your playlists, Recently played and Your Songs appear on the car's screen."
            PlaybackService.carConnected -> "Android Auto is connected to Sevbify: your music is on the car's screen."
            else -> "Your playlists, Recently played and Your Songs appear on the car's screen once Android Auto lists Sevbify."
        }, style = MaterialTheme.typography.bodySmall)
        if (installed && !PlaybackService.carConnected) {
            Text(AUTO_STEPS, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
            OutlinedButton(onClick = { CarHelp.openAndroidAuto(context) }, modifier = Modifier.padding(top = 8.dp)) {
                Text("Open Android Auto settings", color = C.Text)
            }
        }
        Text("Apple CarPlay is for iPhones; on an iPhone, Sevbify plays through CarPlay with the controls on its Now " +
             "Playing screen.", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
    }
}

/** Shown once when Android Auto is on the phone, and again (at most daily) when in a car without it working. */
@Composable
fun CarTipDialog() {
    val context = LocalContext.current
    fun done() { Nav.carTip = false; Library.settings.carTipShown = true; Library.changed() }
    AlertDialog(
        onDismissRequest = { done() },
        title = { Text("Sevbify on Android Auto") },
        text = { Text(AUTO_STEPS, style = MaterialTheme.typography.bodySmall) },
        confirmButton = { TextButton(onClick = { done(); CarHelp.openAndroidAuto(context) }) { Text("Open Android Auto settings", color = C.Green) } },
        dismissButton = { TextButton(onClick = { done() }) { Text(tr("Later"), color = C.Text) } },
        containerColor = C.Elevated,
    )
}
