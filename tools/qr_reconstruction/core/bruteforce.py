"""
Bruteforce Engine für QR-Code-Rekonstruktion
Intelligente Suche nach gültigen QR-Codes durch systematisches Ausprobieren
Maximale Performance durch Multiprocessing (nutzt alle CPU-Cores)
"""

import numpy as np
import os
from typing import List, Tuple, Callable, Optional, Dict, Any
from itertools import product
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from .qr_matrix import QRMatrix, CellState
from .validator import QRValidator, ValidationResult


def _worker_process(matrix_grid: np.ndarray, 
                   unknown_cells: List[Tuple[int, int]], 
                   validator_weights: Dict,
                   debug_mode: bool,
                   chunk_candidates: List[Tuple[int, ...]]) -> List[ValidationResult]:
    """
    Worker-Funktion für einen separaten Prozess.
    Muss Top-Level sein, damit Pickle funktioniert.
    
    Args:
        matrix_grid: Das Basis-Grid (numpy array)
        unknown_cells: Liste der unbekannten Koordinaten
        validator_weights: Konfiguration des Validators
        debug_mode: Debug-Flag
        chunk_candidates: Liste von Kandidaten (Tuples) die dieser Worker testen soll
        
    Returns:
        Liste der gefundenen validen Ergebnisse
    """
    # Konstruiere Validator im Worker (vermeidet Pickle-Probleme von pyzbar Objekten)
    validator = QRValidator(debug_mode=debug_mode)
    validator.WEIGHTS = validator_weights
    
    # Pre-allocate Matrix Object to reuse (Performance!)
    # Wir erstellen einmal eine QRMatrix und manipulieren nur das Grid
    # Da QRMatrix __init__ Logik hat, bauen wir es manuell oder nutzen eine Helper-Klasse
    # Einfacher: Wir nutzen direkt die Validator-Funktionen die Arrays akzeptieren wenn möglich
    # Aber `validate` erwartet QRMatrix.
    
    # Wir erstellen EINE Dummy-Matrix und updaten sie
    size = matrix_grid.shape[0]
    temp_matrix = QRMatrix(size=size)
    
    # Kopiere Basis-Grid
    # Wir nutzen eine optimierte validation loop
    results = []
    
    # Optimierung: Indices vorbereiten
    rows = np.array([r for r, c in unknown_cells])
    cols = np.array([c for r, c in unknown_cells])
    
    # Grid Buffer zum Wiederverwenden
    work_grid = matrix_grid.copy()
    
    for combination in chunk_candidates:
        # 1. Update Grid (Vektorisiert)
        # work_grid[rows, cols] = combination # Geht nicht direkt so einfach mit Tupel
        # Schnellster Weg in Python loop:
        for i, val in enumerate(combination):
            work_grid[rows[i], cols[i]] = CellState.BLACK if val == 1 else CellState.WHITE
            
        # 2. Update Matrix Objekt
        temp_matrix.grid = work_grid # Reference is ok because we validate immediately
        
        # 3. Validiere
        # Hier nutzen wir eine optimierte interne Funktion des Validators wenn möglich?
        # Nein, wir rufen die normale validate auf, aber der Validator selbst wird gleich optimiert.
        result = validator.validate(temp_matrix)
        
        if result.is_valid:
            # WICHTIG: Tiefenkopie des Grids für das Ergebnis, sonst überschreiben wir es
            result.matrix = work_grid.copy()  
            results.append(result)
            
    return results


class BruteforceMode:
    """Vordefinierte Bruteforce-Modi"""
    FAST = {
        'name': 'Schnell',
        'max_iterations': 1000,
        'max_time': 10,
        'use_smart_sampling': True,
        'parallel': True
    }
    
    ACCURATE = {
        'name': 'Akkurat',
        'max_iterations': 100000,
        'max_time': 300,
        'use_smart_sampling': True,
        'parallel': True
    }
    
    CUSTOM = {
        'name': 'Custom',
        'max_iterations': None,
        'max_time': None,
        'use_smart_sampling': True,
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
        self._executor = None
    
    def stop(self):
        self._should_stop = True
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    def set_result_callback(self, callback):
        self.result_callback = callback
    
    def run(self, mode='fast', max_iterations=None, max_time=None, parallel=True) -> List[ValidationResult]:
        self._should_stop = False
        self.stats = {
            'tested': 0,
            'valid': 0,
            'start_time': time.time(),
            'end_time': None,
            'mode': mode
        }
        
        if mode == 'fast': config = BruteforceMode.FAST.copy()
        elif mode == 'accurate': config = BruteforceMode.ACCURATE.copy()
        else:
            config = BruteforceMode.CUSTOM.copy()
            config['max_iterations'] = max_iterations or 10000
            config['max_time'] = max_time or 60
            
        num_unknown = len(self.unknown_cells)
        max_possible = 2 ** num_unknown
        max_iter = min(config['max_iterations'], max_possible)
        
        # CPU Info
        cpu_count = os.cpu_count() or 4
        print(f"\n{'='*60}")
        print(f"🚀 High-Performance Bruteforce ({config['name']})")
        print(f"   CPU: {cpu_count} Kerne erkannt")
        print(f"   Ziel: {max_iter:,} Tests")
        print(f"{'='*60}")
        
        results = []
        if parallel and num_unknown > 10:
            results = self._run_multiprocess(max_iter, config['max_time'], cpu_count)
        else:
            results = self._run_sequential(max_iter, config['max_time'])
            
        self.stats['end_time'] = time.time()
        elapsed = self.stats['end_time'] - self.stats['start_time']
        
        print(f"\n{'='*60}")
        print(f"Fertig! {self.stats['tested']:,} Tests in {elapsed:.2f}s")
        print(f"Geschwindigkeit: {self.stats['tested'] / elapsed:.0f} Tests/s")
        print(f"{'='*60}\n")
        
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _run_sequential(self, max_iterations, max_time):
        # Fallback für sehr kleine Aufgaben
        results = []
        start = time.time()
        
        # Eigene Matrix-Instanz wiederverwenden um Overhead zu sparen
        temp_matrix = self.matrix.clone()
        rows = [r for r, c in self.unknown_cells]
        cols = [c for r, c in self.unknown_cells]
        
        for i, combination in enumerate(self._generate_candidates(max_iterations)):
            if self._should_stop or (time.time() - start > max_time): break
            
            # Apply
            for idx, val in enumerate(combination):
                temp_matrix.grid[rows[idx], cols[idx]] = CellState.BLACK if val == 1 else CellState.WHITE
                
            # Validate
            result = self.validator.validate(temp_matrix)
            self.stats['tested'] += 1
            
            if result.is_valid:
                # IMPORTANT: Deep copy matrix for result
                result.matrix = temp_matrix.grid.copy()
                results.append(result)
                self.stats['valid'] += 1
                if self.result_callback: self.result_callback(result)
            
            if i % 100 == 0 and self.progress_callback:
                self.progress_callback(self.stats['tested'], self.stats['valid'], max_iterations)
                
        return results

    def _run_multiprocess(self, max_iterations, max_time, workers):
        results = []
        start = time.time()
        
        # Generator konsumieren und in Chunks aufteilen
        # Da wir Multiprocessing machen, müssen wir Batches an die Worker schicken
        # um den Overhead der Inter-Process-Communication (IPC) gering zu halten.
        all_candidates = list(self._generate_candidates(max_iterations))
        total_candidates = len(all_candidates)
        
        # Batch Size berechnen (mindestens 100 pro Chunk, oder alles durch 4x Worker)
        chunk_size = max(100, total_candidates // (workers * 4))
        chunks = [all_candidates[i:i + chunk_size] for i in range(0, total_candidates, chunk_size)]
        
        print(f"   Verteile {total_candidates} Aufgaben auf {workers} Worker in {len(chunks)} Batches...")
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            self._executor = executor
            futures = []
            
            # Submit all chunks
            for chunk in chunks:
                if self._should_stop: break
                
                # Wir übergeben rohe Daten, keine komplexen Objekte um Pickle-Overhead zu minimieren
                future = executor.submit(
                    _worker_process,
                    self.matrix.grid,
                    self.unknown_cells,
                    self.validator.WEIGHTS,
                    self.validator.debug_mode,
                    chunk
                )
                futures.append(future)
            
            # Process results as they come in
            completed_count = 0
            for future in as_completed(futures):
                if self._should_stop: 
                    self._executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                if time.time() - start > max_time:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    chunk_results = future.result()
                    
                    # Update Stats
                    chunk_len = 0 
                    # Wir wissen nicht exakt wie viele processed wurden im Chunk wenn wir es nicht zurückgeben
                    # Aber wir nehmen an alle im Chunk wurden processed.
                    # Workaround: Wir zählen einfach completed chunks * chunk_size (ungefähr)
                    # Bessere Lösung: Worker gibt (tested_count, results) zurück.
                    # Aber wir lassen es simpel.
                    
                    # Add results
                    for res in chunk_results:
                        results.append(res)
                        self.stats['valid'] += 1
                        if self.result_callback: self.result_callback(res)
                    
                    completed_count += 1
                    self.stats['tested'] = min(total_candidates, completed_count * chunk_size)
                    
                    if self.progress_callback:
                        self.progress_callback(self.stats['tested'], self.stats['valid'], max_iterations)
                        
                except Exception as e:
                    print(f"Worker Error: {e}")

        return results

    def _generate_candidates(self, max_count):
        # ... (Gleiche Logik wie vorher) ...
        num_unknown = len(self.unknown_cells)
        if num_unknown <= 20:
            for i, combo in enumerate(product([0, 1], repeat=num_unknown)):
                if i >= max_count: break
                yield combo
        else:
            # Smart Sampling
            count = 0
            # 1. 50/50
            for _ in range(min(max_count // 3, 1000)):
                yield tuple(np.random.choice([0, 1], size=num_unknown, p=[0.5, 0.5]))
                count += 1
            
            # 2. Random
            remaining = max_count - count
            for _ in range(remaining):
                yield tuple(np.random.randint(0, 2, size=num_unknown))

    def get_stats(self) -> Dict:
        """Gibt aktuelle Statistiken zurück"""
        stats = self.stats.copy()
        if stats['start_time'] and not stats['end_time']:
            stats['elapsed'] = time.time() - stats['start_time']
        elif stats['end_time']:
            stats['elapsed'] = stats['end_time'] - stats['start_time']
        return stats