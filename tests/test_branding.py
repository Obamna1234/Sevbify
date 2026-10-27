"""Logo/icon files, Windows shortcuts (with a pretend PowerShell) and the VLC trimming used by the build."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
BRANDING = ROOT / "assets" / "branding"


def test_logo_and_icons_exist_for_every_platform():
    from PIL import Image
    assert Image.open(BRANDING / "sevbify_logo_1024.png").size == (1024, 1024)
    assert Image.open(BRANDING / "sevbify_icon_512.png").size == (512, 512)
    assert Image.open(BRANDING / "sevbify_256.png").size == (256, 256)
    ico = Image.open(BRANDING / "sevbify.ico")
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(ico.info["sizes"])
    assert Image.open(BRANDING / "sevbify.icns").size == (1024, 1024)
    assert "Icon=sevbify" in (ROOT / "packaging" / "sevbify.desktop").read_text(encoding="utf-8")


def test_shortcut_script_points_at_the_exe_and_its_logo():
    from core import shortcuts
    script = shortcuts.powershell_script(r"C:\Apps\Sevbify\Sevbify.exe", [r"C:\Users\Me\Desktop\Sevbify.lnk",
                                                                        r"C:\Users\O'Neil\Start\Sevbify.lnk"])
    assert "$l.TargetPath = 'C:\\Apps\\Sevbify\\Sevbify.exe'" in script
    assert "$l.IconLocation = 'C:\\Apps\\Sevbify\\Sevbify.exe,0'" in script
    assert "'C:\\Users\\O''Neil\\Start\\Sevbify.lnk'" in script        # quotes in names are escaped
    assert script.count("$l.Save()") == 2


def test_create_shortcuts_reports_success_and_failure(tmp_path, monkeypatch):
    from core import shortcuts
    paths = [str(tmp_path / "Desktop" / "Sevbify.lnk"), str(tmp_path / "Start" / "Sevbify.lnk")]
    monkeypatch.setattr(shortcuts, "shortcut_paths", lambda: paths)
    calls = []
    ok, msg = shortcuts.create_windows_shortcuts(
        r"C:\Apps\Sevbify.exe", run=lambda cmd, **k: calls.append(cmd) or SimpleNamespace(returncode=0, stderr=""))
    assert ok and "Desktop and Start menu" in msg
    assert calls[0][0] == "powershell" and (tmp_path / "Desktop").is_dir()
    ok, msg = shortcuts.create_windows_shortcuts(
        r"C:\Apps\Sevbify.exe", run=lambda cmd, **k: SimpleNamespace(returncode=1, stderr="Access denied"))
    assert not ok and "Access denied" in msg


def test_shortcut_button_only_in_the_packaged_windows_app(qapp, monkeypatch):
    from core import shortcuts
    from core.storage import UserData
    from ui.settings_dialog import SettingsDialog
    from PyQt6.QtWidgets import QPushButton

    def buttons():
        dialog = SettingsDialog(UserData())
        texts = [b.text() for b in dialog.findChildren(QPushButton)]
        dialog.deleteLater()
        return texts

    monkeypatch.setattr(shortcuts, "can_create", lambda: False)
    assert "Add to Desktop and Start menu" not in buttons()
    monkeypatch.setattr(shortcuts, "can_create", lambda: True)
    assert "Add to Desktop and Start menu" in buttons()


def test_vlc_trim_keeps_audio_and_removes_video(tmp_path):
    vlc = tmp_path / "vlc"
    for rel in ("libvlc.dll", "plugins/plugins.dat", "plugins/gui/libqt_plugin.dll",
                "plugins/video_output/libdirect3d11_plugin.dll", "plugins/visualization/libgoom_plugin.dll",
                "plugins/codec/libx264_plugin.dll", "plugins/codec/libdav1d_plugin.dll",
                "plugins/codec/libmpg123_plugin.dll", "plugins/codec/libflac_plugin.dll",
                "plugins/codec/libavcodec_plugin.dll", "plugins/codec/libvorbis_plugin.dll",
                "plugins/access/libhttps_plugin.dll", "plugins/audio_filter/libequalizer_plugin.dll",
                "plugins/audio_output/libmmdevice_plugin.dll", "plugins/misc/libgnutls_plugin.dll",
                "plugins/demux/libes_plugin.dll"):
        p = vlc / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 100)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "trim_vlc.py"), str(vlc)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    left = {str(p.relative_to(vlc)).replace(os.sep, "/") for p in vlc.rglob("*") if p.is_file()}
    assert left == {"libvlc.dll", "plugins/codec/libmpg123_plugin.dll", "plugins/codec/libflac_plugin.dll",
                    "plugins/codec/libavcodec_plugin.dll", "plugins/codec/libvorbis_plugin.dll",
                    "plugins/access/libhttps_plugin.dll", "plugins/audio_filter/libequalizer_plugin.dll",
                    "plugins/audio_output/libmmdevice_plugin.dll", "plugins/misc/libgnutls_plugin.dll",
                    "plugins/demux/libes_plugin.dll"}
