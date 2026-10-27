"""Settings that must be applied before the window exists (zoom, graphics, proxy), and starting Sevbify when
you log in to Windows. No UI code."""
import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Sevbify"


def apply_env(user_data, environ=None):
    """Set environment variables Qt / Python read at start-up. Returns what was set (for tests)."""
    env = os.environ if environ is None else environ
    changed = {}
    if user_data.zoom != 100:
        changed["QT_SCALE_FACTOR"] = f"{user_data.zoom / 100:.2f}"
    if not user_data.hw_accel:
        changed["QT_OPENGL"] = "software"
        changed["QT_QUICK_BACKEND"] = "software"
    if user_data.proxy_mode == "none":
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            env.pop(k, None)
        changed["NO_PROXY"] = "*"
    elif user_data.proxy_mode == "http" and user_data.proxy_url.strip():
        url = user_data.proxy_url.strip()
        if "://" not in url:
            url = "http://" + url
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            changed[k] = url
    env.update(changed)
    return changed


def can_start_at_login():
    return os.name == "nt" and getattr(sys, "frozen", False)


def run_command(mode, exe=None):
    exe = exe or sys.executable
    return f'"{exe}"' + (" --minimized" if mode == "minimized" else "")


def set_start_at_login(mode, exe=None, winreg_module=None):
    """mode: "no", "yes" or "minimized". Writes or removes Sevbify in the user's Run key (no admin needed).
    Returns True when it worked."""
    if winreg_module is None:
        if not can_start_at_login():
            return False
        import winreg as winreg_module
    w = winreg_module
    try:
        key = w.OpenKey(w.HKEY_CURRENT_USER, RUN_KEY, 0, w.KEY_SET_VALUE)
        try:
            if mode in ("yes", "minimized"):
                w.SetValueEx(key, RUN_NAME, 0, w.REG_SZ, run_command(mode, exe))
            else:
                try:
                    w.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        finally:
            w.CloseKey(key)
        return True
    except OSError:
        return False


def restart_command():
    """How to start this same Sevbify again (packaged exe or python app.py)."""
    if getattr(sys, "frozen", False):
        return sys.executable, [a for a in sys.argv[1:] if a != "--minimized"]
    return sys.executable, [os.path.abspath(sys.argv[0])] + [a for a in sys.argv[1:] if a != "--minimized"]
