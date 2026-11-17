"""Equaliser and fade helpers for VLC playback (no UI code)."""
# The 10 bands VLC's equaliser really uses (libvlc_audio_equalizer_get_band_frequency). The labels used to be an
# older VLC band list (60 Hz, 170 Hz, ...), so a dot labelled "1 kHz" moved the 500 Hz band and seemed to do nothing.
BAND_LABELS = ("31 Hz", "62 Hz", "125 Hz", "250 Hz", "500 Hz", "1 kHz", "2 kHz", "4 kHz", "8 kHz", "16 kHz")


def band_labels(vlc):
    """Labels for the bands this VLC uses (its own frequencies), or the usual ones."""
    try:
        out = []
        for i in range(vlc.libvlc_audio_equalizer_get_band_count()):
            f = float(vlc.libvlc_audio_equalizer_get_band_frequency(i))
            out.append(f"{f / 1000:g} kHz" if f >= 1000 else f"{int(round(f))} Hz")
        return tuple(out) if len(out) == 10 else BAND_LABELS
    except Exception:
        return BAND_LABELS


def presets(vlc):
    """VLC's built-in equaliser presets as {name: [10 band values]} (Flat, Rock, Pop, Classical, ...)."""
    out = {}
    try:
        for i in range(vlc.libvlc_audio_equalizer_get_preset_count()):
            name = vlc.libvlc_audio_equalizer_get_preset_name(i)
            name = name.decode() if isinstance(name, bytes) else str(name)
            eq = vlc.libvlc_audio_equalizer_new_from_preset(i)
            out[name] = [round(vlc.libvlc_audio_equalizer_get_amp_at_index(eq, b), 1) for b in range(10)]
            vlc.libvlc_audio_equalizer_release(eq)
    except Exception:
        pass
    return out or {"Flat": [0.0] * 10}


def make_equalizer(vlc, bands, preamp=None):
    """A VLC equaliser with these 10 band values (dB). The pre-amp is lowered a little when bands are boosted,
    so loud settings don't distort."""
    eq = vlc.AudioEqualizer()
    for i, value in enumerate(list(bands)[:10]):
        eq.set_amp_at_index(float(value), i)
    if preamp is None:
        preamp = 12.0 - max([0.0] + [float(v) for v in bands]) * 0.5
    eq.set_preamp(float(preamp))
    return eq


def fade_factor(time_ms, length_ms, fade_ms):
    """Volume multiplier (0..1) for a short fade in at the start and fade out at the end of a song."""
    if fade_ms <= 0 or length_ms <= 0 or time_ms < 0 or length_ms < fade_ms * 3:
        return 1.0
    if time_ms < fade_ms:
        return max(0.0, time_ms / fade_ms)
    remaining = length_ms - time_ms
    if remaining < fade_ms:
        return max(0.0, remaining / fade_ms)
    return 1.0
