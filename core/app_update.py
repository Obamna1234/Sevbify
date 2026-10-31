"""Installing a new Sevbify from inside the app ("Download, then restart"). No UI code here.

1. `download()` fetches this computer's file from Sevbify's own GitHub release (only that address is accepted)
   and checks it against GitHub's SHA-256 for it; a file that doesn't match is thrown away.
2. `unpack()` extracts it into Sevbify's data folder (entries that would land outside it are refused).
3. `restart_command()` writes a small script that waits for Sevbify to close, swaps the old app for the new
   one (the old one is kept until the new one is in place, and put back if the swap fails), and opens it again.
Your playlists, settings and music live elsewhere (the data folder and your music folders), so they're untouched.
Only works for the packaged app; running from source just opens the release page instead.
"""
import hashlib
import os
import shutil
import stat
import sys
import tarfile
import uuid
import zipfile

ALLOWED_PREFIX = "https://github.com/Obamna1234/Sevbify/releases/download/"


class UpdateError(Exception):
    pass


def can_install():
    """True for the packaged app (PyInstaller), where the files can be swapped."""
    return bool(getattr(sys, "frozen", False))


def install_target(executable=None, platform=None):
    """What gets replaced: the Sevbify.app bundle on a Mac, else the folder the program is in."""
    exe = os.path.abspath(executable or sys.executable)
    platform = platform or sys.platform
    if platform == "darwin":
        app = exe
        while app and not app.endswith(".app"):
            parent = os.path.dirname(app)
            if parent == app:
                break
            app = parent
        if app.endswith(".app"):
            return app
    return os.path.dirname(exe)


def looks_like_sevbify(target, platform=None, exe_name=None):
    """Only a folder that is clearly a Sevbify install is ever replaced (never, say, the Desktop or a music folder
    that someone put Sevbify.exe into): the app bundle on a Mac; elsewhere the program plus its _internal folder,
    and nothing that isn't part of a Sevbify release."""
    platform = platform or sys.platform
    if not target or not os.path.isdir(target):
        return False
    if platform == "darwin":
        return target.endswith(".app") and os.path.isfile(os.path.join(target, "Contents", "MacOS", "Sevbify"))
    exe = exe_name or ("Sevbify.exe" if platform.startswith("win") else "Sevbify")
    if not os.path.isfile(os.path.join(target, exe)) or not os.path.isdir(os.path.join(target, "_internal")):
        return False
    allowed = {exe.lower(), "_internal", "sevbify.exe", "sevbify", "deno", "deno.exe", "ffmpeg", "ffmpeg.exe",
               "libvlc.dll", "libvlccore.dll", "plugins", "vlc", "readme.txt", "licenses"}
    return all(n.lower() in allowed for n in os.listdir(target))


def launch_detached(cmd):
    """Start the updater so it keeps running after Sevbify quits."""
    import subprocess
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # detached, new group, no window
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def prepare(url, data_dir, sha256="", size=0):
    """Download and unpack an update into the data folder. Returns the new app's path."""
    folder = os.path.join(data_dir, "update")
    archive = download(url, folder, sha256, size)
    try:
        return unpack(archive, os.path.join(folder, "new"))
    finally:
        try:
            os.remove(archive)
        except OSError:
            pass


def _fetch(url, timeout=60):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Sevbify-updater"})
    return urllib.request.urlopen(req, timeout=timeout)


def download(url, dest_dir, sha256="", size=0, progress=None, opener=None):
    """Download the release file into dest_dir and check it. Returns its path."""
    if not url.startswith(ALLOWED_PREFIX):
        raise UpdateError("That isn't Sevbify's release page, so it wasn't downloaded.")
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(url.split("?", 1)[0]) or "Sevbify-update"
    path = os.path.join(dest_dir, name)
    part = path + ".part"
    h = hashlib.sha256()
    got = 0
    limit = max(size * 2, 600 * 1024 * 1024) if size else 600 * 1024 * 1024
    try:
        with (opener or _fetch)(url) as r, open(part, "wb") as f:
            total = size or int(getattr(r, "headers", {}).get("Content-Length") or 0)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                if got > limit:
                    raise UpdateError("The download was far bigger than expected, so it was stopped.")
                h.update(chunk)
                f.write(chunk)
                if progress and total:
                    progress(min(got / total, 1.0))
        if size and got != size:
            raise UpdateError("The download didn't finish (wrong size). Try again.")
        if sha256 and h.hexdigest() != sha256.lower():
            raise UpdateError("The download didn't match GitHub's checksum, so it was thrown away.")
        os.replace(part, path)
        return path
    except Exception:
        try:
            os.remove(part)
        except OSError:
            pass
        raise


def _inside(root, target):
    root = os.path.realpath(root)
    target = os.path.realpath(target)
    return target == root or target.startswith(root + os.sep)


def unpack(archive, dest_dir):
    """Extract the downloaded .zip / .tar.gz into dest_dir (emptied first). Returns the new app's path:
    the Sevbify.app bundle or the Sevbify folder."""
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)
    os.makedirs(dest_dir)
    if archive.lower().endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if not _inside(dest_dir, os.path.join(dest_dir, info.filename)):
                    raise UpdateError("The update contains a file outside its folder, so it wasn't used.")
            if sys.platform == "darwin" and shutil.which("ditto"):
                # A Mac app has links inside it (frameworks) that only ditto restores properly.
                import subprocess
                subprocess.run(["/usr/bin/ditto", "-x", "-k", archive, dest_dir], check=True, timeout=600)
                return _found_app(dest_dir)
            for info in z.infolist():
                out = os.path.join(dest_dir, info.filename)
                if not _inside(dest_dir, out):
                    raise UpdateError("The update contains a file outside its folder, so it wasn't used.")
                z.extract(info, dest_dir)
                mode = (info.external_attr >> 16) & 0o777
                if mode and not info.is_dir():
                    os.chmod(out, mode)                    # keep the program runnable on Mac / Linux
                elif mode & stat.S_IXUSR and info.is_dir():
                    os.chmod(out, mode)
    else:
        with tarfile.open(archive, "r:*") as t:
            for m in t.getmembers():
                if m.issym() or m.islnk():
                    link = os.path.join(dest_dir, os.path.dirname(m.name), m.linkname)
                    if os.path.isabs(m.linkname) or not _inside(dest_dir, link):
                        raise UpdateError("The update contains a link outside its folder, so it wasn't used.")
                if not _inside(dest_dir, os.path.join(dest_dir, m.name)) or m.isdev():
                    raise UpdateError("The update contains a file outside its folder, so it wasn't used.")
            try:
                t.extractall(dest_dir, filter="tar")         # also refuses odd entries (newer Pythons)
            except TypeError:
                t.extractall(dest_dir)
    return _found_app(dest_dir)


def _found_app(dest_dir):
    found = [n for n in os.listdir(dest_dir) if not n.startswith(".") and n != "__MACOSX"]
    for n in found:
        if n.endswith(".app"):
            return os.path.join(dest_dir, n)
    if len(found) == 1 and os.path.isdir(os.path.join(dest_dir, found[0])):
        return os.path.join(dest_dir, found[0])
    raise UpdateError("The update didn't contain Sevbify.")


def _q(path):
    return "'" + path.replace("'", "'\\''") + "'"


def restart_command(new_app, target, pid, script_dir, platform=None, exe_name=None, reopen=True):
    """Write the swap-and-reopen script; returns the command that starts it (run it detached, then quit).
    reopen=False: just swap (an update downloaded earlier is put in place when you close Sevbify)."""
    platform = platform or sys.platform
    os.makedirs(script_dir, exist_ok=True)
    # A fresh name Sevbify makes itself: a folder that already exists is never removed.
    old = target.rstrip("/\\") + ".sevbify-old-" + uuid.uuid4().hex[:8]
    if platform.startswith("win"):
        def c(p):                      # cmd expands %...% even inside quotes
            if any(ch in p for ch in '"\r\n'):
                raise UpdateError("Sevbify's folder has a name the updater can't use; update from the release page.")
            return p.replace("%", "%%")
        target_c, new_c, old_c = c(target), c(new_app), c(old)
        exe = target_c.rstrip("\\") + "\\" + c(exe_name or "Sevbify.exe")
        script = os.path.join(script_dir, "sevbify-update.cmd")
        target, new_app, old = target_c, new_c, old_c
        lines = [
            "@echo off",
            "chcp 65001 >NUL",            # the paths below are UTF-8 (names like José or Мария)
            "setlocal",
            f':wait',
            f'tasklist /FI "PID eq {int(pid)}" 2>NUL | find "{int(pid)}" >NUL',
            "if not errorlevel 1 ( timeout /t 1 /nobreak >NUL & goto wait )",
            f'move "{target}" "{old}" >NUL',
            "if errorlevel 1 goto copy",
            f'move "{new_app}" "{target}" >NUL',
            "if errorlevel 1 (",
            f'  move "{old}" "{target}" >NUL',
            "  goto copy",
            ")",
            f'rmdir /s /q "{old}"',
            "goto start",
            ":copy",
            # The folder couldn't be renamed (something has it open): copy the new files over instead.
            f'robocopy "{new_app}" "{target}" /E /NFL /NDL /NJH /NJS >NUL',
            ":start",
            f'start "" "{exe}"' if reopen else "rem not reopened",
            '(goto) 2>nul & del "%~f0"',
        ]
        with open(script, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
        return [__import__("ntpath").join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "cmd.exe")
                if os.name == "nt" else "cmd.exe", "/c", script]
    script = os.path.join(script_dir, "sevbify-update.sh")
    if not reopen:
        reopen = ":"
    elif platform == "darwin":
        reopen = f"open {_q(target)}"
    else:
        reopen = f"( {_q(os.path.join(target, exe_name or 'Sevbify'))} >/dev/null 2>&1 & )"
    body = f"""#!/bin/sh
# Sevbify updater: wait for Sevbify to close, swap in the new version, open it again.
while kill -0 {int(pid)} 2>/dev/null; do sleep 0.5; done
if mv {_q(target)} {_q(old)}; then
  if mv {_q(new_app)} {_q(target)}; then
    rm -rf {_q(old)}
  else
    mv {_q(old)} {_q(target)}
  fi
fi
{reopen}
rm -f "$0"
"""
    with open(script, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.chmod(script, 0o755)
    return ["/bin/sh", script]
