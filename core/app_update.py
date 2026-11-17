"""Installing a new Sevbify from inside the app ("Download, then restart"). No UI code here.

1. `download()` fetches this computer's file from Sevbify's own GitHub release (only that address is accepted)
   and checks it against GitHub's SHA-256 for it; a file that doesn't match is thrown away.
2. `unpack()` extracts it into Sevbify's data folder (entries that would land outside it are refused).
3. `restart_command()` writes a small script that waits for Sevbify to close, swaps the old app for the new
   one (the old one is kept until the new one is in place, and put back if the swap fails), and opens it again.
4. Roll-back: the old version is kept next to the app as "<folder>.sevbify-previous". After an update the script
   waits for the new version to say it started (`confirm_started()`, called once the window is up). If it
   doesn't within START_WAIT seconds, it tries once more; if it still doesn't, the previous version is put back
   and opened, and the next start says so (`take_rollback_note()`). Settings can also go back by hand
   (`rollback_command()`).
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
               "libvlc.dll", "libvlccore.dll", "plugins", "vlc", "readme.txt", "licenses",
               # what the release build puts next to the program (Windows: README, CHANGELOG; Linux: also the
               # menu entry, its installer and icon)
               "readme.md", "changelog.md", "sevbify.desktop", "install.sh", "sevbify.png"}
    return all(n.lower() in allowed for n in os.listdir(target))


def launch_detached(cmd):
    """Start the updater so it keeps running after Sevbify quits."""
    import subprocess
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # detached, new group, no window
        if len(cmd) == 3 and cmd[1] == "/c":
            # cmd.exe reads its own command line: the script's path always in quotes, so a user name with & (or
            # spaces) in it can't split the command.
            cmd = f'"{cmd[0]}" /c "{cmd[2]}"'
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


START_WAIT = 90          # seconds the new version gets to open its window before it's tried again / rolled back
PREVIOUS = ".sevbify-previous"


def previous_path(target):
    return target.rstrip("/\\") + PREVIOUS


def has_previous(target=None):
    target = target or install_target()
    return bool(target) and os.path.isdir(previous_path(target))


def _marker_paths(script_dir):
    return (os.path.join(script_dir, "start-pending"), os.path.join(script_dir, "start-ok"),
            os.path.join(script_dir, "rolled-back"))


def confirm_started(data_dir):
    """Called by the app once its window is up: tells a waiting updater script this version works."""
    pending, ok, _ = _marker_paths(os.path.join(data_dir, "update"))
    try:
        with open(pending, encoding="utf-8") as f:
            token = f.read().strip()
    except OSError:
        return False
    if not token or len(token) > 64:
        return False
    try:
        with open(ok, "w", encoding="utf-8") as f:
            f.write(token)
        os.remove(pending)
    except OSError:
        return False
    return True


def take_rollback_note(data_dir):
    """If the last update was rolled back, the message to show once (and forget); else ""."""
    _, _, note = _marker_paths(os.path.join(data_dir, "update"))
    if not os.path.exists(note):
        return ""
    try:
        os.remove(note)
    except OSError:
        pass
    return ("The new Sevbify didn't open, so your previous version was put back. Nothing in your library "
            "changed. The fix will come in a later update.")


def restart_command(new_app, target, pid, script_dir, platform=None, exe_name=None, reopen=True, rollback=False):
    """Write the swap-and-reopen script; returns the command that starts it (run it detached, then quit).
    reopen=False: just swap (an update downloaded earlier is put in place when you close Sevbify).
    rollback=True: new_app is the kept previous version and the current one becomes the kept one (Settings →
    Go back to the previous version); no start check then."""
    platform = platform or sys.platform
    os.makedirs(script_dir, exist_ok=True)
    # A fresh name Sevbify makes itself: a folder that already exists is never removed.
    old = target.rstrip("/\\") + ".sevbify-old-" + uuid.uuid4().hex[:8]
    failed = target.rstrip("/\\") + ".sevbify-failed-" + uuid.uuid4().hex[:8]
    prev = previous_path(target)
    pending, ok, note = _marker_paths(script_dir)
    check = bool(reopen) and not rollback
    token = uuid.uuid4().hex
    for path in (ok, note):
        try:
            os.remove(path)
        except OSError:
            pass
    if check:
        with open(pending, "w", encoding="utf-8") as f:
            f.write(token)
    if platform.startswith("win"):
        def c(p):                      # cmd expands %...% even inside quotes
            if any(ch in p for ch in '"\r\n'):
                raise UpdateError("Sevbify's folder has a name the updater can't use; update from the release page.")
            return p.replace("%", "%%")
        target_c, new_c, old_c, prev_c, failed_c = c(target), c(new_app), c(old), c(prev), c(failed)
        ok_c, note_c = c(ok), c(note)
        exe_base = c(exe_name or "Sevbify.exe")
        exe = target_c.rstrip("\\") + "\\" + exe_base
        script = os.path.join(script_dir, "sevbify-update.cmd")
        target, new_app, old, prev = target_c, new_c, old_c, prev_c
        start = f'start "" "{exe}"' if reopen else "rem not reopened"
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
            # Keep the version just replaced as the previous one (one copy; an older one is removed).
            f'if exist "{prev}" rmdir /s /q "{prev}"',
            f'move "{old}" "{prev}" >NUL',
            "goto start",
            ":copy",
            # The folder couldn't be renamed (something has it open): copy the new files over instead.
            f'robocopy "{new_app}" "{target}" /E /NFL /NDL /NJH /NJS >NUL',
            ":start",
        ]
        if check:
            lines += [
                "set tries=0",
                ":launch",
                start,
                "set waited=0",
                ":check",
                f'if exist "{ok_c}" findstr /x /c:"{token}" "{ok_c}" >NUL && goto done',
                "timeout /t 1 /nobreak >NUL",
                "set /a waited+=1",
                f"if %waited% LSS {START_WAIT} goto check",
                f'taskkill /F /IM "{exe_base}" >NUL 2>&1',
                "timeout /t 2 /nobreak >NUL",
                "set /a tries+=1",
                "if %tries% LSS 2 goto launch",
                # Twice without a window: put the previous version back.
                f'if not exist "{prev}" goto done',
                f'move "{target}" "{c(failed)}" >NUL',
                "if errorlevel 1 goto done",
                f'move "{prev}" "{target}" >NUL',
                "if errorlevel 1 (",
                f'  move "{c(failed)}" "{target}" >NUL',
                "  goto done",
                ")",
                f'rmdir /s /q "{c(failed)}"',
                f'echo rolled back> "{note_c}"',
                start,
                ":done",
            ]
        else:
            lines.append(start)
        lines.append('(goto) 2>nul & del "%~f0"')
        with open(script, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
        return [__import__("ntpath").join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "cmd.exe")
                if os.name == "nt" else "cmd.exe", "/c", script]
    script = os.path.join(script_dir, "sevbify-update.sh")
    if not reopen:
        start = ":"
    elif platform == "darwin":
        start = f"open {_q(target)}"
    else:
        start = f"( {_q(os.path.join(target, exe_name or 'Sevbify'))} >/dev/null 2>&1 & )"
    stop = f"pkill -f -- {_q(target.rstrip('/') + '/')} 2>/dev/null; sleep 2"
    body = f"""#!/bin/sh
# Sevbify updater: wait for Sevbify to close, swap in the new version, open it again (and, after an update,
# put the previous version back if the new one doesn't open).
while kill -0 {int(pid)} 2>/dev/null; do sleep 0.5; done
if mv {_q(target)} {_q(old)}; then
  if mv {_q(new_app)} {_q(target)}; then
    rm -rf {_q(prev)}
    mv {_q(old)} {_q(prev)} || rm -rf {_q(old)}
  else
    mv {_q(old)} {_q(target)}
  fi
fi
"""
    if check:
        body += f"""started() {{ [ -f {_q(ok)} ] && [ "$(cat {_q(ok)})" = "{token}" ]; }}
try_start() {{
  {start}
  i=0
  while [ $i -lt {START_WAIT} ]; do started && return 0; sleep 1; i=$((i+1)); done
  {stop}
  return 1
}}
if ! try_start && ! try_start && [ -d {_q(prev)} ]; then
  if mv {_q(target)} {_q(failed)}; then
    if mv {_q(prev)} {_q(target)}; then
      rm -rf {_q(failed)}
      echo "rolled back" > {_q(note)}
      {start}
    else
      mv {_q(failed)} {_q(target)}
    fi
  fi
fi
"""
    else:
        body += f"{start}\n"
    body += 'rm -f "$0"\n'
    with open(script, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.chmod(script, 0o755)
    return ["/bin/sh", script]


def rollback_command(pid, script_dir, target=None, platform=None, exe_name=None):
    """Settings → Go back to the previous version: swap the kept previous version in (the current one is kept
    in its place, so you can go forward again the same way) and reopen."""
    target = target or install_target()
    if not has_previous(target):
        raise UpdateError("There's no previous version on this computer.")
    staged = os.path.join(script_dir, "back-" + uuid.uuid4().hex[:8])
    os.makedirs(script_dir, exist_ok=True)
    os.rename(previous_path(target), staged)                     # same drive: a quick rename
    return restart_command(staged, target, pid, script_dir, platform, exe_name, reopen=True, rollback=True)
