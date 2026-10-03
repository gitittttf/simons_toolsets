"""
Bruteforce Engine für QR-Code-Rekonstruktion
Intelligente Suche nach gültigen QR-Codes durch systematisches Ausprobieren
Maximale Performance durch Multiprocessing (nutzt alle CPU-Cores)
"""

import logging
import multiprocessing
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Callable, Optional, Dict

import numpy as np

from .qr_matrix import QRMatrix
from .validator import QRValidator, ValidationResult

logger = logging.getLogger(__name__)

# Unterhalb dieser Kandidatenzahl lohnt sich der Start eines Prozess-Pools nicht
PARALLEL_THRESHOLD = 1024
# Wie oft Worker Stop-Signal und Deadline prüfen (in Kandidaten)
CHECK_INTERVAL = 32


class CandidateSpace:
    """
    Bildet Kandidaten-Indizes [0, count) ohne Duplikate auf Belegungen der unbekannten Zellen ab.

    - Vollständige Suche (count == 2^n): Index = Belegung
    - Teilsuche: affine Bijektion v = (i * mult + offset) mod 2^n mit ungeradem mult,
      damit die Stichprobe über den ganzen Suchraum streut statt nur die letzten Bits zu variieren.

    Es wird nie eine Kandidatenliste im Speicher gehalten; Worker erzeugen ihre Belegungen selbst.
    """

    def __init__(self, num_unknown: int, count: int, seed: int):
        self.num_unknown = num_unknown
        self.total = 1 << num_unknown
        self.count = min(count, self.total)
        self._nbytes = max(1, (num_unknown + 7) // 8)
        if self.count >= self.total:
            self.mult, self.offset = 1, 0
        else:
            rng = random.Random(seed)
            self.mult = rng.getrandbits(num_unknown) | 1
            self.offset = rng.getrandbits(num_unknown)

    def bits(self, index: int) -> np.ndarray:
        """Belegung (0/1 je unbekannter Zelle) für einen Kandidaten-Index"""
        value = (index * self.mult + self.offset) & (self.total - 1)
        raw = np.frombuffer(value.to_bytes(self._nbytes, 'little'), dtype=np.uint8)
        return np.unpackbits(raw, bitorder='little')[:self.num_unknown]


class _CandidateTester:
    """Testet Kandidaten gegen eine feste Basis-Matrix (wird pro Prozess genau einmal gebaut)"""

    def __init__(self, base_grid: np.ndarray, unknown_cells: List[Tuple[int, int]],
                 space: CandidateSpace, validator: QRValidator):
        self.space = space
        self.validator = validator
        self.rows = np.array([r for r, _ in unknown_cells], dtype=np.intp)
        self.cols = np.array([c for _, c in unknown_cells], dtype=np.intp)
        self.matrix = QRMatrix(size=base_grid.shape[0])
        self.matrix.grid = base_grid.copy()

    def test(self, index: int) -> ValidationResult:
        # CellState.BLACK == 1, CellState.WHITE == 0 → Bits direkt übernehmen
        self.matrix.grid[self.rows, self.cols] = self.space.bits(index)
        result = self.validator.validate(self.matrix)
        if result.is_valid:
            # Kopie, da das Grid für den nächsten Kandidaten überschrieben wird
            result.matrix = self.matrix.grid.copy()
        return result


# Zustand pro Worker-Prozess (gesetzt durch _init_worker)
_worker_tester: Optional[_CandidateTester] = None
_worker_stop_event = None
_worker_deadline: float = 0.0


def _init_worker(base_grid, unknown_cells, space, validator_weights, debug_mode, stop_event, deadline):
    """Initializer: baut Validator (inkl. Wörterbücher) nur einmal pro Prozess"""
    global _worker_tester, _worker_stop_event, _worker_deadline
    validator = QRValidator(debug_mode=debug_mode)
    validator.WEIGHTS = validator_weights
    _worker_tester = _CandidateTester(base_grid, unknown_cells, space, validator)
    _worker_stop_event = stop_event
    _worker_deadline = deadline


def _worker_process(start: int, end: int) -> Tuple[int, List[ValidationResult]]:
    """
    Testet die Kandidaten-Indizes [start, end).
    Muss Top-Level sein, damit Pickle funktioniert.

    Returns:
        (Anzahl tatsächlich getesteter Kandidaten, gültige Ergebnisse)
    """
    results = []
    tested = 0
    for index in range(start, end):
        if tested % CHECK_INTERVAL == 0 and (_worker_stop_event.is_set() or time.time() > _worker_deadline):
            break
        result = _worker_tester.test(index)
        tested += 1
        if result.is_valid:
            results.append(result)
    return tested, results


class BruteforceMode:
    """Vordefinierte Bruteforce-Modi"""
    FAST = {
        'name': 'Schnell',
        'max_iterations': 1000,
        'max_time': 10,
        'parallel': True
    }

    ACCURATE = {
        'name': 'Akkurat',
        'max_iterations': 100000,
        'max_time': 300,
        'parallel': True
    }

    CUSTOM = {
        'name': 'Custom',
        'max_iterations': 10000,
        'max_time': 60,
        'parallel': True
    }


class BruteforceEngine:
    """
    High-Performance Bruteforce Engine
    Nutzt ProcessPoolExecutor für maximale CPU-Auslastung (Bypass GIL)
    """

    def __init__(self, matrix: QRMatrix, validator: QRValidator):
        self.matrix = matrix
        self.validator = validator
        self.unknown_cells = matrix.get_unknown_cells()

        self.stats = {
            'tested': 0,
            'valid': 0,
            'start_time': None,
            'end_time': None,
            'mode': None
        }

        self.progress_callback: Optional[Callable] = None
        self.result_callback: Optional[Callable] = None
        self._should_stop = False
        self._stop_event = None
        # Beste Lösung je dekodiertem Text (pyzbar korrigiert intern Fehler,
        # daher liefern viele Kandidaten denselben Inhalt)
        self._results_by_data: Dict[str, ValidationResult] = {}

    def stop(self):
        self._should_stop = True
        stop_event = self._stop_event  # lokal: der Bruteforce-Thread setzt das Attribut am Ende zurück
        if stop_event is not None:
            stop_event.set()

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def set_result_callback(self, callback):
        self.result_callback = callback

    def run(self, mode='fast', max_iterations=None, max_time=None, parallel=True,
            seed: Optional[int] = None) -> List[ValidationResult]:
        """
        Startet die Suche.

        Args:
            mode: 'fast', 'accurate' oder 'custom' (liefert die Standardwerte)
            max_iterations / max_time: überschreiben die Standardwerte des Modus, falls gesetzt
            seed: Seed für die Stichprobe bei Teilsuche (reproduzierbare Läufe)

        Returns:
            Gültige Ergebnisse, ein Eintrag pro dekodiertem Inhalt, nach Confidence sortiert
        """
        self._should_stop = False
        self._results_by_data = {}
        self.stats = {
            'tested': 0,
            'valid': 0,
            'start_time': time.time(),
            'end_time': None,
            'mode': mode
        }

        if mode == 'fast':
            config = BruteforceMode.FAST.copy()
        elif mode == 'accurate':
            config = BruteforceMode.ACCURATE.copy()
        else:
            config = BruteforceMode.CUSTOM.copy()
        if max_iterations is not None:
            config['max_iterations'] = max_iterations
        if max_time is not None:
            config['max_time'] = max_time

        num_unknown = len(self.unknown_cells)
        if seed is None:
            seed = random.randrange(1 << 32)
        space = CandidateSpace(num_unknown, config['max_iterations'], seed)
        deadline = self.stats['start_time'] + config['max_time']

        cpu_count = os.cpu_count() or 4
        logger.info("Bruteforce (%s): %d unbekannte Zellen, %s von 2^%d Kandidaten, %d CPU-Kerne",
                    config['name'], num_unknown, f"{space.count:,}", num_unknown, cpu_count)

        if parallel and space.count > PARALLEL_THRESHOLD:
            self._run_multiprocess(space, deadline, cpu_count)
        else:
            self._run_sequential(space, deadline)

        self.stats['end_time'] = time.time()
        elapsed = self.stats['end_time'] - self.stats['start_time']
        logger.info("Fertig: %s Tests in %.2fs (%.0f Tests/s), %d eindeutige Ergebnisse",
                    f"{self.stats['tested']:,}", elapsed,
                    self.stats['tested'] / elapsed if elapsed > 0 else 0, self.stats['valid'])

        results = list(self._results_by_data.values())
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _collect(self, result: ValidationResult):
        """Übernimmt ein gültiges Ergebnis; pro dekodiertem Inhalt bleibt das beste"""
        key = result.decoded_data
        existing = self._results_by_data.get(key)
        if existing is None:
            self._results_by_data[key] = result
            self.stats['valid'] += 1
            if self.result_callback:
                self.result_callback(result)
        elif result.confidence > existing.confidence:
            self._results_by_data[key] = result

    def _report_progress(self, total):
        if self.progress_callback:
            self.progress_callback(self.stats['tested'], self.stats['valid'], total)

    def _run_sequential(self, space: CandidateSpace, deadline: float):
        # Für kleine Aufgaben: kein Prozess-Overhead, eigener Validator wird wiederverwendet
        tester = _CandidateTester(self.matrix.grid, self.unknown_cells, space, self.validator)

        for index in range(space.count):
            if self._should_stop or time.time() > deadline:
                break
            result = tester.test(index)
            self.stats['tested'] += 1
            if result.is_valid:
                self._collect(result)
            if index % 100 == 0:
                self._report_progress(space.count)

        self._report_progress(space.count)

    def _run_multiprocess(self, space: CandidateSpace, deadline: float, workers: int):
        # Batches, damit der IPC-Overhead klein bleibt, aber Fortschritt regelmäßig kommt
        chunk_size = max(50, min(2000, space.count // (workers * 8)))
        ranges = [(start, min(start + chunk_size, space.count))
                  for start in range(0, space.count, chunk_size)]

        ctx = multiprocessing.get_context()
        self._stop_event = ctx.Event()
        if self._should_stop:
            self._stop_event.set()

        logger.info("Verteile %s Kandidaten auf %d Worker in %d Batches",
                    f"{space.count:,}", workers, len(ranges))

        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=ctx,
                initializer=_init_worker,
                initargs=(self.matrix.grid, self.unknown_cells, space, self.validator.WEIGHTS,
                          self.validator.debug_mode, self._stop_event, deadline),
            ) as executor:
                futures = [executor.submit(_worker_process, start, end) for start, end in ranges]

                pending_cancelled = False
                for future in as_completed(futures):
                    if not pending_cancelled and (self._should_stop or time.time() > deadline):
                        # Noch nicht gestartete Batches verwerfen; laufende beenden sich
                        # selbst über Stop-Event bzw. Deadline
                        for f in futures:
                            f.cancel()
                        pending_cancelled = True
                    if future.cancelled():
                        continue
                    try:
                        tested, chunk_results = future.result()
                    except Exception:
                        logger.exception("Worker-Fehler")
                        continue

                    self.stats['tested'] += tested
                    for res in chunk_results:
                        self._collect(res)
                    self._report_progress(space.count)
        finally:
            self._stop_event = None

    def get_stats(self) -> Dict:
        """Gibt aktuelle Statistiken zurück"""
        stats = self.stats.copy()
        if stats['start_time'] and not stats['end_time']:
            stats['elapsed'] = time.time() - stats['start_time']
        elif stats['end_time']:
            stats['elapsed'] = stats['end_time'] - stats['start_time']
        return stats
