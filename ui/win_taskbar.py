"""Windows: buttons in the taskbar preview (hover over Sevbify in the taskbar), like Spotify's:
Like / Previous / Play-Pause / Next.

Uses Windows' own ITaskbarList3 "thumbnail toolbar" through ctypes (no extra library). Everything is guarded:
on other systems, or if Windows refuses, nothing happens and Sevbify works as before.

How it works: Windows sends a "TaskbarButtonCreated" message to the window once its taskbar button exists; then
the buttons are added. A click arrives as WM_COMMAND with THBN_CLICKED and the button's id, which the main
window's nativeEvent passes to `handle()`.
"""
import sys

IDS = {"like": 1, "previous": 2, "play": 3, "next": 4}
WM_COMMAND = 0x0111
THBN_CLICKED = 0x1800
THB_ICON, THB_TOOLTIP, THB_FLAGS = 0x2, 0x4, 0x8
THBF_ENABLED = 0x0

_ok = sys.platform == "win32"
if _ok:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

        def __init__(self, text):
            super().__init__()
            import uuid
            u = uuid.UUID(text)
            self.Data1, self.Data2, self.Data3 = u.fields[0], u.fields[1], u.fields[2]
            for i, b in enumerate(u.bytes[8:]):
                self.Data4[i] = b

    class THUMBBUTTON(ctypes.Structure):
        _fields_ = [("dwMask", wintypes.DWORD), ("iId", wintypes.UINT), ("iBitmap", wintypes.UINT),
                    ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 260), ("dwFlags", wintypes.DWORD)]

    CLSID_TaskbarList = GUID("56FDF344-FD6D-11d0-958A-006097C9A090")
    IID_ITaskbarList3 = GUID("EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF")


def _icon_handle(qicon, size=16):
    """A Windows icon handle from a Qt icon (PNG bytes → CreateIconFromResourceEx)."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    pm = qicon.pixmap(size, size)
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.toImage().save(buf, "PNG")
    buf.close()
    raw = bytes(data)
    user32 = ctypes.windll.user32
    user32.CreateIconFromResourceEx.restype = wintypes.HICON
    user32.CreateIconFromResourceEx.argtypes = [ctypes.c_char_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
                                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
    return user32.CreateIconFromResourceEx(raw, len(raw), True, 0x00030000, size, size, 0)


class ThumbBar:
    """The four buttons. `actions`: {"like", "previous", "play", "next"} -> callables."""

    def __init__(self, hwnd, actions):
        self.hwnd, self.actions = int(hwnd), actions
        self.added = False
        self._tb = None
        self._icons = {}
        self.created_msg = 0
        if not _ok:
            return
        try:
            self.created_msg = ctypes.windll.user32.RegisterWindowMessageW("TaskbarButtonCreated")
            ctypes.windll.ole32.CoInitialize(None)
            ptr = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(ctypes.byref(CLSID_TaskbarList), None, 1,
                                                      ctypes.byref(IID_ITaskbarList3), ctypes.byref(ptr))
            if hr != 0 or not ptr.value:
                return
            self._tb = ptr
            self._call(3)                                         # HrInit
        except Exception:
            self._tb = None

    def _call(self, index, *args, argtypes=()):
        vtbl = ctypes.cast(ctypes.cast(self._tb, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
        return proto(vtbl[index])(self._tb, *args)

    def _buttons(self, liked, playing):
        from . import icons
        spec = [("like", icons.heart("#1ed760" if liked else "#ffffff", 16, filled=liked),
                 "Remove from Liked Songs" if liked else "Add to Liked Songs"),
                ("previous", icons.skip("previous", "#ffffff", 16), "Previous"),
                ("play", icons.pause("#ffffff", 16) if playing else icons.play("#ffffff", 16),
                 "Pause" if playing else "Play"),
                ("next", icons.skip("next", "#ffffff", 16), "Next")]
        arr = (THUMBBUTTON * len(spec))()
        for i, (key, icon, tip) in enumerate(spec):
            old = self._icons.get(key)
            h = _icon_handle(icon)
            self._icons[key] = h
            if old:
                ctypes.windll.user32.DestroyIcon(old)
            arr[i].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            arr[i].iId = IDS[key]
            arr[i].hIcon = h
            arr[i].szTip = tip
            arr[i].dwFlags = THBF_ENABLED
        return arr

    def add(self, liked=False, playing=False):
        """Called when Windows says the taskbar button exists."""
        if self._tb is None or self.added:
            return False
        try:
            arr = self._buttons(liked, playing)
            hr = self._call(15, wintypes.HWND(self.hwnd), wintypes.UINT(len(arr)), arr,
                            argtypes=(wintypes.HWND, wintypes.UINT, ctypes.POINTER(THUMBBUTTON)))
            self.added = hr == 0
        except Exception:
            self.added = False
        return self.added

    def update(self, liked=False, playing=False):
        if self._tb is None or not self.added:
            return
        try:
            arr = self._buttons(liked, playing)
            self._call(16, wintypes.HWND(self.hwnd), wintypes.UINT(len(arr)), arr,
                       argtypes=(wintypes.HWND, wintypes.UINT, ctypes.POINTER(THUMBBUTTON)))
        except Exception:
            pass

    def handle(self, message_id, wparam):
        """From the window's nativeEvent: True when it was one of our buttons (or the 'button created' note)."""
        if self.created_msg and message_id == self.created_msg:
            self.added = False
            return "created"
        if message_id == WM_COMMAND and (wparam >> 16) & 0xFFFF == THBN_CLICKED:
            key = next((k for k, v in IDS.items() if v == wparam & 0xFFFF), None)
            if key and key in self.actions:
                self.actions[key]()
                return "clicked"
        return None
