"""Remove the parts of VLC that Sevbify never uses before VLC is bundled into the Windows app.

Usage:  python tools/trim_vlc.py <folder with libvlc.dll and plugins>

Sevbify uses VLC only to play audio (local files and web streams such as 30-second previews). Its own
window, video, subtitles, visualisations, streaming-out/casting, device discovery and remote control are
never used, so their plugins are removed. Every audio decoder, file and network access (including https),
audio filters (equaliser, speed) and audio output are kept. The build's smoke test then plays WAV, MP3,
FLAC, OGG, Opus and M4A files and a web stream with the trimmed copy.

To bring something back (for example visualisations), delete its line below; the next build includes it.
"""
import fnmatch
import os
import shutil
import sys

# Whole plugin folders Sevbify doesn't use.
REMOVE_FOLDERS = {
    "gui": "VLC's own window and skins",
    "lua": "VLC's Lua scripts (playlist parsers, extensions)",
    "video_output": "showing video",
    "video_filter": "video effects",
    "video_chroma": "video colour conversion",
    "video_splitter": "video walls",
    "d3d9": "Direct3D 9 video",
    "d3d11": "Direct3D 11 video",
    "spu": "subtitle/overlay drawing",
    "text_renderer": "drawing subtitles and text on video",
    "visualization": "music visualisations (spectrum, Goom, projectM)",
    "stream_out": "streaming out, casting (Chromecast), converting",
    "access_output": "writing streams to files/network",
    "mux": "packing audio/video into files (converting/recording)",
    "services_discovery": "finding network devices (UPnP/DLNA, SAP), casting targets",
    "control": "remote control, hotkeys, VLC's web interface",
    "keystore": "saving passwords for network shares",
}

# Video-only decoders/encoders inside plugins/codec (audio codecs are all kept).
REMOVE_CODECS = [
    "libx264*", "libx265*", "libx26410b*", "libaom*", "libdav1d*", "librav1e*", "libvpx*", "libtheora*",
    "libdaala*", "libschroedinger*", "libqsv*", "libd3d11va*", "libdxva2*", "libmft*", "librawvideo*",
    "libjpeg*", "libpng*", "libsvgdec*", "libxwd*", "libcdg*", "libkate*", "libzvbi*", "libtelx*",
    "libsvcdsub*", "libcvdsub*", "libdvbsub*", "libscte18*", "libscte27*", "libsubsdec*", "libsubsusf*",
    "libsubstx3g*", "libttml*", "libwebvtt*", "libcc_*", "libtextst*", "liboggspots*", "libvideotoolbox*",
    "libbpg*", "libimage*",
]


def size_of(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def trim(folder):
    plugins = os.path.join(folder, "plugins")
    before = size_of(folder)
    removed = []
    for name, why in REMOVE_FOLDERS.items():
        p = os.path.join(plugins, name)
        if os.path.isdir(p):
            removed.append(f"{name}/ ({size_of(p) // 1048576} MB) - {why}")
            shutil.rmtree(p)
    codec = os.path.join(plugins, "codec")
    if os.path.isdir(codec):
        for f in sorted(os.listdir(codec)):
            if any(fnmatch.fnmatch(f.lower(), pat) for pat in REMOVE_CODECS):
                removed.append(f"codec/{f} ({os.path.getsize(os.path.join(codec, f)) // 1024} KB)")
                os.remove(os.path.join(codec, f))
    # plugins.dat is VLC's plugin cache; it would list removed plugins, so let VLC rebuild it.
    cache = os.path.join(plugins, "plugins.dat")
    if os.path.isfile(cache):
        os.remove(cache)
    after = size_of(folder)
    return before, after, removed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    before, after, removed = trim(sys.argv[1])
    print("\n".join("removed " + r for r in removed))
    print(f"VLC folder: {before // 1048576} MB -> {after // 1048576} MB")
    print(f"::notice title=VLC trimmed::{before // 1048576} MB -> {after // 1048576} MB "
          f"({len(removed)} parts removed)")
