"""
Bruteforce Engine für QR-Code-Rekonstruktion
Intelligente Suche nach gültigen QR-Codes durch systematisches Ausprobieren
"""

import numpy as np
from typing import List, Tuple, Callable, Optional, Dict
from itertools import product
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .qr_matrix import QRMatrix, CellState
from .validator import QRValidator, ValidationResult


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
    Hauptklasse für die Bruteforce-Rekonstruktion
    Unterstützt parallele Verarbeitung und intelligentes Sampling
    """
    
    def __init__(self, matrix: QRMatrix, validator: QRValidator):
        """
        Initialisiert die Bruteforce-Engine
        
        Args:
            matrix: QRMatrix mit bekannten und unbekannten Bereichen
            validator: QRValidator für die Validierung von Kandidaten
        """
        self.matrix = matrix
        self.validator = validator
        self.unknown_cells = matrix.get_unknown_cells()
        
        # Statistiken
        self.stats = {
            'tested': 0,
            'valid': 0,
            'start_time': None,
            'end_time': None,
            'mode': None
        }
        
        # Callbacks
        self.progress_callback: Optional[Callable] = None
        self.result_callback: Optional[Callable] = None
        
        # Stopp-Flag
        self._should_stop = False
    
    def stop(self):
        """Stoppt den laufenden Bruteforce-Prozess"""
        self._should_stop = True
    
    def set_progress_callback(self, callback: Callable[[int, int, int], None]):
        """
        Setzt Callback für Fortschritts-Updates
        
        Args:
            callback: Funktion(tested, valid, total)
        """
        self.progress_callback = callback
    
    def set_result_callback(self, callback: Callable[[ValidationResult], None]):
        """
        Setzt Callback für neue Ergebnisse
        
        Args:
            callback: Funktion(result)
        """
        self.result_callback = callback
    
    def run(self, 
            mode: str = 'fast',
            max_iterations: Optional[int] = None,
            max_time: Optional[float] = None,
            parallel: bool = True) -> List[ValidationResult]:
        """
        Startet die Bruteforce-Suche
        
        Args:
            mode: 'fast', 'accurate', oder 'custom'
            max_iterations: Maximale Anzahl Iterationen (nur bei custom)
            max_time: Maximale Zeit in Sekunden (nur bei custom)
            parallel: Parallelverarbeitung nutzen?
            
        Returns:
            Liste sortierter ValidationResult-Objekte
        """
        # Reset
        self._should_stop = False
        self.stats = {
            'tested': 0,
            'valid': 0,
            'start_time': time.time(),
            'end_time': None,
            'mode': mode
        }
        
        # Lade Mode-Config
        if mode == 'fast':
            config = BruteforceMode.FAST.copy()
        elif mode == 'accurate':
            config = BruteforceMode.ACCURATE.copy()
        else:  # custom
            config = BruteforceMode.CUSTOM.copy()
            config['max_iterations'] = max_iterations or 10000
            config['max_time'] = max_time or 60
        
        # Validierung
        num_unknown = len(self.unknown_cells)
        max_possible = 2 ** num_unknown
        
        if num_unknown > 25:
            print(f"⚠️ WARNUNG: {num_unknown} unbekannte Zellen = {max_possible:,} Kombinationen!")
            print("   Das könnte sehr lange dauern. Empfehlung: Mehr Zellen sperren.")
        
        # Berechne tatsächliche Iterations-Anzahl
        max_iter = min(config['max_iterations'], max_possible)
        
        print(f"\n{'='*60}")
        print(f"Starte Bruteforce ({config['name']}-Modus)")
        print(f"{'='*60}")
        print(f"Unbekannte Zellen: {num_unknown}")
        print(f"Max. Kombinationen: {max_possible:,}")
        print(f"Zu testende: {max_iter:,}")
        print(f"Max. Zeit: {config['max_time']}s")
        print(f"Parallel: {parallel}")
        print(f"{'='*60}\n")
        
        # Starte Suche
        results = []
        
        if parallel and num_unknown > 10:
            results = self._run_parallel(max_iter, config['max_time'])
        else:
            results = self._run_sequential(max_iter, config['max_time'])
        
        # Finale Statistiken
        self.stats['end_time'] = time.time()
        elapsed = self.stats['end_time'] - self.stats['start_time']
        
        print(f"\n{'='*60}")
        print(f"Bruteforce abgeschlossen!")
        print(f"{'='*60}")
        print(f"Getestet: {self.stats['tested']:,}")
        print(f"Gültig: {self.stats['valid']}")
        print(f"Zeit: {elapsed:.2f}s")
        print(f"Geschwindigkeit: {self.stats['tested'] / elapsed:.0f} Tests/s")
        print(f"{'='*60}\n")
        
        # Sortiere nach Confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
    
    def _run_sequential(self, max_iterations: int, max_time: float) -> List[ValidationResult]:
        """Sequentielle Verarbeitung (Single-Thread)"""
        results = []
        start = time.time()
        
        for i, combination in enumerate(self._generate_candidates(max_iterations)):
            if self._should_stop:
                break
            
            if time.time() - start > max_time:
                print(f"\n⏱️ Zeit-Limit erreicht ({max_time}s)")
                break
            
            # Teste Kandidat
            result = self._test_candidate(combination)
            self.stats['tested'] += 1
            
            if result.is_valid:
                results.append(result)
                self.stats['valid'] += 1
                
                # Callback
                if self.result_callback:
                    self.result_callback(result)
            
            # Progress
            if self.stats['tested'] % 100 == 0:
                if self.progress_callback:
                    self.progress_callback(self.stats['tested'], self.stats['valid'], max_iterations)
        
        return results
    
    def _run_parallel(self, max_iterations: int, max_time: float) -> List[ValidationResult]:
        """Parallele Verarbeitung (Multi-Thread)"""
        results = []
        start = time.time()
        
        # Nutze ThreadPoolExecutor für I/O-bound Tasks
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i, combination in enumerate(self._generate_candidates(max_iterations)):
                if self._should_stop:
                    break
                
                if time.time() - start > max_time:
                    break
                
                future = executor.submit(self._test_candidate, combination)
                futures.append(future)
            
            # Sammle Ergebnisse
            for future in as_completed(futures):
                if self._should_stop:
                    break
                
                result = future.result()
                self.stats['tested'] += 1
                
                if result.is_valid:
                    results.append(result)
                    self.stats['valid'] += 1
                    
                    if self.result_callback:
                        self.result_callback(result)
                
                # Progress
                if self.stats['tested'] % 100 == 0:
                    if self.progress_callback:
                        self.progress_callback(self.stats['tested'], self.stats['valid'], max_iterations)
        
        return results
    
    def _test_candidate(self, combination: Tuple[int, ...]) -> ValidationResult:
        """
        Testet einen einzelnen Kandidaten
        
        Args:
            combination: Tuple mit Werten für unbekannte Zellen
            
        Returns:
            ValidationResult
        """
        # Erstelle Kandidaten-Matrix
        candidate = self.matrix.clone()
        
        for (row, col), value in zip(self.unknown_cells, combination):
            candidate.grid[row, col] = CellState.BLACK if value == 1 else CellState.WHITE
        
        # Validiere
        return self.validator.validate(candidate)
    
    def _generate_candidates(self, max_count: int):
        """
        Generiert Kandidaten (intelligentes Sampling)
        
        Yields:
            Tuple mit Werten (0/1) für unbekannte Zellen
        """
        num_unknown = len(self.unknown_cells)
        
        if num_unknown <= 20:
            # Kleine Anzahl: Vollständige Enumeration
            for i, combo in enumerate(product([0, 1], repeat=num_unknown)):
                if i >= max_count:
                    break
                yield combo
        
        else:
            # Große Anzahl: Smart Sampling
            
            # 1. Starte mit "wahrscheinlichen" Mustern
            # QR-Codes haben typischerweise 40-60% schwarze Module
            for _ in range(min(max_count // 3, 1000)):
                # Generiere mit ~50% Wahrscheinlichkeit für schwarz
                yield tuple(np.random.choice([0, 1], size=num_unknown, p=[0.5, 0.5]))
            
            # 2. Variationen um beste bisherige Lösung
            # (wird später implementiert mit adaptive sampling)
            
            # 3. Zufälliges Sampling für den Rest
            remaining = max_count - min(max_count // 3, 1000)
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