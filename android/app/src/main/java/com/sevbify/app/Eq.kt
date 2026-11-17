package com.sevbify.app

import android.media.audiofx.Equalizer
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** The equaliser on Android, like the PC's: Android's own sound effect on Sevbify's player (nothing leaves the phone).
 *  Settings → Playback → Equaliser: on/off, the phone's presets (Rock, Pop, Classical, …) or Custom with a slider
 *  per band. Phones differ in how many bands they have (usually 5), so the bands are read from the phone. */
object Eq {
    data class Band(val label: String, val min: Int, val max: Int)       // millibels

    private var eq: Equalizer? = null
    var bands by mutableStateOf<List<Band>>(emptyList())
    var presets by mutableStateOf<List<String>>(emptyList())
    var available by mutableStateOf(false)

    /** Attach to the player's audio session (PlaybackService), then apply the saved settings. */
    fun attach(sessionId: Int) {
        release()
        try {
            val e = Equalizer(0, sessionId)
            eq = e
            val (lo, hi) = e.bandLevelRange.let { it[0].toInt() to it[1].toInt() }
            bands = (0 until e.numberOfBands).map { b ->
                val hz = e.getCenterFreq(b.toShort()) / 1000
                Band(if (hz >= 1000) "${"%.1f".format(hz / 1000.0).removeSuffix(".0")} kHz" else "$hz Hz", lo, hi)
            }
            presets = (0 until e.numberOfPresets).map { e.getPresetName(it.toShort()) }
            available = bands.isNotEmpty()
            apply()
        } catch (t: Throwable) {
            Log.w("Sevbify", "equaliser not available: ${t.message}")
            available = false
            eq = null
        }
    }

    fun release() {
        try { eq?.release() } catch (_: Throwable) {}
        eq = null
    }

    /** Use Library.settings (eqOn, eqPreset, eqBands). Unknown or out-of-range values are ignored. */
    fun apply() {
        val e = eq ?: return
        val s = Library.settings
        try {
            e.enabled = s.eqOn
            if (!s.eqOn) return
            val p = presets.indexOf(s.eqPreset)
            if (p >= 0) {
                e.usePreset(p.toShort())
            } else {
                bands.forEachIndexed { b, band ->
                    val v = s.eqBands.getOrNull(b) ?: 0
                    e.setBandLevel(b.toShort(), v.coerceIn(band.min, band.max).toShort())
                }
            }
        } catch (t: Throwable) {
            Log.w("Sevbify", "equaliser: ${t.message}")
        }
    }

    /** The current level of each band (after a preset is chosen, so Custom starts from it). */
    fun levels(): List<Int> {
        val e = eq ?: return Library.settings.eqBands
        return try { bands.indices.map { e.getBandLevel(it.toShort()).toInt() } } catch (_: Throwable) { Library.settings.eqBands }
    }
}
