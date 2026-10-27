"""Windows shortcuts for the ready-made app (it comes as a zip, without an installer).

`create_windows_shortcuts()` puts "Sevbify" on the Desktop and in the Start menu, pointing at Sevbify.exe
and showing its logo. Uses Windows' own shortcut maker (WScript.Shell through PowerShell); no UI code here.
"""
import os
import subprocess
import sys

NAME = "Sevbify"


def can_create():
    """Shortcuts are only made for the packaged Windows app (Sevbify.exe)."""
    return os.name == "nt" and getattr(sys, "frozen", False)


def shortcut_paths():
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
    return [
        os.path.join(home, "Desktop", NAME + ".lnk"),
        os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", NAME + ".lnk"),
    ]


def powershell_script(target, paths):
    """The PowerShell commands that create each shortcut (single quotes doubled for safety)."""
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    lines = ["$s = New-Object -ComObject WScript.Shell"]
    for p in paths:
        lines += [
            f"$l = $s.CreateShortcut({q(p)})",
            f"$l.TargetPath = {q(target)}",
            f"$l.WorkingDirectory = {q(os.path.dirname(target))}",
            f"$l.IconLocation = {q(target + ',0')}",
            f"$l.Description = {q('Sevbify music player')}",
            "$l.Save()",
        ]
    return "; ".join(lines)


def create_windows_shortcuts(target=None, run=subprocess.run):
    """Create the Desktop and Start-menu shortcuts. Returns (ok, message)."""
    target = target or sys.executable
    paths = shortcut_paths()
    for p in paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        r = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 powershell_script(target, paths)],
                capture_output=True, text=True, timeout=30, creationflags=0x08000000 if os.name == "nt" else 0)
    except Exception as e:
        return False, f"Couldn't create shortcuts: {e}"
    if getattr(r, "returncode", 1) != 0:
        return False, "Couldn't create shortcuts: " + (getattr(r, "stderr", "") or "").strip()[:300]
    return True, "Added Sevbify to your Desktop and Start menu."
