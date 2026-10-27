"""Run slow work (network, downloads) off the UI thread.

    run_async(owner, fn, *args, on_done=callback, on_error=callback)

The callbacks are always called on the UI thread. If `owner` (a QObject) is
deleted before the work finishes, the callbacks are skipped.
"""
import traceback

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

try:
    from PyQt6 import sip as _sip
except ImportError:  # pragma: no cover
    _sip = None

_pool = QThreadPool()
_pool.setMaxThreadCount(4)
_alive = set()


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(object)


class _Task(QRunnable):
    def __init__(self, fn, args, kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # reported to on_error
            e.__traceback_text__ = traceback.format_exc()
            self.signals.failed.emit(e)
        else:
            self.signals.done.emit(result)


def _owner_alive(owner):
    if owner is None or _sip is None:
        return True
    try:
        return not _sip.isdeleted(owner)
    except TypeError:
        return True


def run_async(owner, fn, *args, on_done=None, on_error=None, **kwargs):
    task = _Task(fn, args, kwargs)
    signals = task.signals
    _alive.add(signals)

    def finish(cb, value):
        _alive.discard(signals)
        if cb is not None and _owner_alive(owner):
            cb(value)

    signals.done.connect(lambda r: finish(on_done, r))
    signals.failed.connect(lambda e: finish(on_error, e))
    _pool.start(task)
    return task


def wait_for_all(msecs=5000):
    """Used on shutdown and in tests."""
    return _pool.waitForDone(msecs)
