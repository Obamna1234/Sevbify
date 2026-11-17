package com.sevbify.app

import android.media.audiofx.DynamicsProcessing
import android.media.audiofx.Equalizer
import android.os.Build
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.audio.BaseAudioProcessor
import androidx.media3.common.util.UnstableApi
import java.nio.ByteBuffer
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
    private var dyn: DynamicsProcessing? = null
    private var session = 0
    var bands by mutableStateOf<List<Band>>(emptyList())
    var presets by mutableStateOf<List<String>>(emptyList())
    var available by mutableStateOf(false)

    /** Attach to the player's audio session (PlaybackService), then apply the saved settings. */
    fun attach(sessionId: Int) {
        release()
        session = sessionId
        applyLevel()
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
        try { dyn?.release() } catch (_: Throwable) {}
        dyn = null
    }

    /** Volume levelling: Android's own dynamics processor (a gentle compressor with make-up gain, then a limiter),
     *  so quiet and loud songs end up close. Android 9 and later; on older phones the switch says so. */
    val levelAvailable get() = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P

    fun applyLevel() {
        if (!levelAvailable || session == 0) return
        try {
            if (!Library.settings.levelOn) { dyn?.enabled = false; return }
            val d = dyn ?: run {
                val cfg = DynamicsProcessing.Config.Builder(DynamicsProcessing.VARIANT_FAVOR_FREQUENCY_RESOLUTION, 2,
                    false, 0, true, 1, false, 0, true).build()
                DynamicsProcessing(0, session, cfg).also { dyn = it }
            }
            for (ch in 0 until 2) {
                val band = d.getMbcBandByChannelIndex(ch, 0)
                band.isEnabled = true
                band.cutoffFrequency = 20000f
                band.attackTime = 20f; band.releaseTime = 400f
                band.ratio = 3f; band.threshold = -26f; band.kneeWidth = 6f
                band.noiseGateThreshold = -70f; band.expanderRatio = 1f
                band.preGain = 0f; band.postGain = 7f
                d.setMbcBandByChannelIndex(ch, 0, band)
                d.setLimiterByChannelIndex(ch, DynamicsProcessing.Limiter(true, true, 0, 1f, 60f, 10f, -1f, 0f))
            }
            d.enabled = true
        } catch (t: Throwable) {
            Log.w("Sevbify", "volume levelling not available: ${t.message}")
        }
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

/** Mono audio: both ears get the same sound (the two channels averaged). Read when a song starts, so turning it on
 *  or off takes effect from the next song. Anything that isn't plain 16-bit stereo passes through untouched. */
@androidx.annotation.OptIn(markerClass = [UnstableApi::class])
@UnstableApi
class MonoAudio : BaseAudioProcessor() {
    override fun onConfigure(inputAudioFormat: AudioProcessor.AudioFormat): AudioProcessor.AudioFormat {
        val ok = Library.settings.monoOn && inputAudioFormat.channelCount == 2 &&
            inputAudioFormat.encoding == androidx.media3.common.C.ENCODING_PCM_16BIT
        return if (ok) inputAudioFormat else AudioProcessor.AudioFormat.NOT_SET
    }

    override fun queueInput(inputBuffer: ByteBuffer) {
        val size = inputBuffer.remaining() / 4 * 4
        val out = replaceOutputBuffer(size)
        var left = size
        while (left >= 4) {
            val l = inputBuffer.short.toInt(); val r = inputBuffer.short.toInt()
            val m = ((l + r) / 2).toShort()
            out.putShort(m); out.putShort(m)
            left -= 4
        }
        inputBuffer.position(inputBuffer.limit())
        out.flip()
    }
}
