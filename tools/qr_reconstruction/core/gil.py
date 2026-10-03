"""
Hilfsmittel für rechenintensive Schleifen in einem Thread neben der Tk-UI

Ein reiner Python-Rechen-Thread hält den GIL bis zum Switch-Intervall (5 ms). Die UI gibt den GIL bei
jedem Tk-Aufruf ab und muss ihn danach zurückbekommen - bei hunderten Aufrufen pro Redraw friert sie
dann sekundenlang ein ("Convoy-Effekt"). Regelmäßiges time.sleep(0) gibt den GIL sofort weiter.
"""

import time


class GilYielder:
    """Gibt den GIL höchstens alle `interval` Sekunden frei (sleep(0) ist ein Syscall, also nicht pro Iteration)"""

    def __init__(self, interval: float = 0.001):
        self.interval = interval
        self._last = time.perf_counter()

    def __call__(self):
        now = time.perf_counter()
        if now - self._last >= self.interval:
            time.sleep(0)
            self._last = time.perf_counter()
