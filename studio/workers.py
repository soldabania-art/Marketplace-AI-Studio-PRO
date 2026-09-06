import traceback
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    started = Signal()
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    """Run a callable outside the UI thread.

    Callable receives keyword arguments progress(percent, text) and is_cancelled().
    """
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled

    def report(self, percent, text=''):
        self.signals.progress.emit(max(0, min(int(percent), 100)), str(text or ''))

    @Slot()
    def run(self):
        self.signals.started.emit()
        try:
            result = self.fn(*self.args, progress=self.report, is_cancelled=self.is_cancelled, **self.kwargs)
            if not self._cancelled:
                self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(f'{e}\n\n{traceback.format_exc()}')
        finally:
            self.signals.finished.emit()
