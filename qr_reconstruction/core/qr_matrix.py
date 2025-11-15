"""
QR-Matrix Verwaltung - Core Module
Verwaltet die QR-Code Grid-Daten und bekannte/unbekannte Bereiche
"""

import numpy as np
from typing import List, Tuple, Optional
from enum import IntEnum


class CellState(IntEnum):
    """Status einer QR-Code-Zelle"""
    WHITE = 0
    BLACK = 1
    UNKNOWN = -1


class QRMatrix:
    """Verwaltet die QR-Code-Matrix mit bekannten und unbekannten Bereichen"""
    
    # Unterstützte QR-Code-Größen (Version 1-7)
    SUPPORTED_SIZES = [21, 25, 29, 33, 37, 41, 45]
    
    def __init__(self, size: int = 21):
        """
        Initialisiert eine leere QR-Matrix
        
        Args:
            size: Größe des QR-Codes (muss in SUPPORTED_SIZES sein)
        """
        if size not in self.SUPPORTED_SIZES:
            raise ValueError(f"Ungültige QR-Größe. Unterstützt: {self.SUPPORTED_SIZES}")
        
        self.size = size
        self.grid = np.full((size, size), CellState.UNKNOWN, dtype=int)
        self.locked = np.zeros((size, size), dtype=bool)
        
        # Füge QR-Struktur automatisch hinzu
        self._add_fixed_patterns()
    
    def _add_fixed_patterns(self):
        """Fügt die festen QR-Code-Muster hinzu (Finder, Timing, etc.)"""
        self._add_finder_patterns()
        self._add_timing_patterns()
        if self.size >= 25:  # Ab Version 2
            self._add_alignment_patterns()
    
    def _add_finder_patterns(self):
        """Fügt die drei Finder-Pattern (Positionsmarker) hinzu"""
        positions = [
            (0, 0),                    # Oben links
            (0, self.size - 7),        # Oben rechts
            (self.size - 7, 0)         # Unten links
        ]
        
        for r, c in positions:
            # Äußerer Rahmen (7x7)
            for i in range(7):
                self._set_locked(r + i, c, CellState.BLACK)
                self._set_locked(r + i, c + 6, CellState.BLACK)
                self._set_locked(r, c + i, CellState.BLACK)
                self._set_locked(r + 6, c + i, CellState.BLACK)
            
            # Weißer Rahmen (5x5 innen)
            for i in range(1, 6):
                for j in range(1, 6):
                    if i == 1 or i == 5 or j == 1 or j == 5:
                        self._set_locked(r + i, c + j, CellState.WHITE)
            
            # Schwarzes Zentrum (3x3)
            for i in range(2, 5):
                for j in range(2, 5):
                    self._set_locked(r + i, c + j, CellState.BLACK)
            
            # Separator (weiße Linie um Finder-Pattern)
            # Horizontal
            if r == 0:
                for i in range(8):
                    self._set_locked(7, c + i, CellState.WHITE)
            else:
                for i in range(8):
                    self._set_locked(r - 1, c + i, CellState.WHITE)
            
            # Vertikal
            if c == 0:
                for i in range(8):
                    self._set_locked(r + i, 7, CellState.WHITE)
            else:
                for i in range(8):
                    self._set_locked(r + i, c - 1, CellState.WHITE)
    
    def _add_timing_patterns(self):
        """Fügt die alternierenden Timing-Patterns hinzu"""
        for i in range(8, self.size - 8):
            value = CellState.BLACK if (i % 2 == 0) else CellState.WHITE
            self._set_locked(6, i, value)  # Horizontal
            self._set_locked(i, 6, value)  # Vertikal
    
    def _add_alignment_patterns(self):
        """Fügt Alignment-Patterns hinzu (ab Version 2)"""
        # Vereinfachte Version - nur für häufige Größen
        alignment_positions = {
            25: [(18, 18)],
            29: [(22, 22)],
            33: [(26, 26)],
            37: [(30, 30)],
            41: [(34, 34)],
            45: [(38, 38)]
        }
        
        if self.size not in alignment_positions:
            return
        
        for r, c in alignment_positions[self.size]:
            # 5x5 Pattern
            for i in range(-2, 3):
                for j in range(-2, 3):
                    if abs(i) == 2 or abs(j) == 2:
                        self._set_locked(r + i, c + j, CellState.BLACK)
                    elif i == 0 and j == 0:
                        self._set_locked(r, c, CellState.BLACK)
                    else:
                        self._set_locked(r + i, c + j, CellState.WHITE)
    
    def _set_locked(self, row: int, col: int, value: CellState):
        """Setzt eine Zelle und sperrt sie"""
        if 0 <= row < self.size and 0 <= col < self.size:
            self.grid[row, col] = value
            self.locked[row, col] = True
    
    def set_cell(self, row: int, col: int, value: CellState, locked: bool = True):
        """
        Setzt eine einzelne Zelle
        
        Args:
            row: Zeile (0-indexed)
            col: Spalte (0-indexed)
            value: Zellwert (CellState)
            locked: Soll die Zelle gesperrt werden?
        """
        if not (0 <= row < self.size and 0 <= col < self.size):
            raise ValueError(f"Position ({row}, {col}) außerhalb des Grids")
        
        self.grid[row, col] = value
        if locked:
            self.locked[row, col] = True
    
    def get_cell(self, row: int, col: int) -> Tuple[CellState, bool]:
        """
        Gibt den Status einer Zelle zurück
        
        Returns:
            (value, is_locked)
        """
        return self.grid[row, col], self.locked[row, col]
    
    def toggle_cell(self, row: int, col: int):
        """Wechselt zwischen WHITE, BLACK und UNKNOWN"""
        if self.locked[row, col]:
            return  # Gesperrte Zellen können nicht geändert werden
        
        current = self.grid[row, col]
        if current == CellState.UNKNOWN:
            self.grid[row, col] = CellState.BLACK
        elif current == CellState.BLACK:
            self.grid[row, col] = CellState.WHITE
        else:
            self.grid[row, col] = CellState.UNKNOWN
    
    def lock_cell(self, row: int, col: int):
        """Sperrt eine Zelle (markiert als bekannt)"""
        if self.grid[row, col] != CellState.UNKNOWN:
            self.locked[row, col] = True
    
    def unlock_cell(self, row: int, col: int):
        """Entsperrt eine Zelle (nur wenn nicht Teil der festen Struktur)"""
        # Prüfe ob es ein festes Pattern ist
        if self._is_fixed_pattern(row, col):
            return
        self.locked[row, col] = False
    
    def _is_fixed_pattern(self, row: int, col: int) -> bool:
        """Prüft ob eine Zelle Teil der festen QR-Struktur ist"""
        # Finder-Patterns
        if (row < 9 and col < 9) or \
           (row < 9 and col >= self.size - 9) or \
           (row >= self.size - 9 and col < 9):
            return True
        
        # Timing-Patterns
        if (row == 6 and 8 <= col < self.size - 8) or \
           (col == 6 and 8 <= row < self.size - 8):
            return True
        
        return False
    
    def get_unknown_cells(self) -> List[Tuple[int, int]]:
        """
        Gibt alle unbekannten (nicht gesperrten) Zellen zurück
        
        Returns:
            Liste von (row, col) Tupeln
        """
        unknown = []
        for i in range(self.size):
            for j in range(self.size):
                if not self.locked[i, j]:
                    unknown.append((i, j))
        return unknown
    
    def get_stats(self) -> dict:
        """Gibt Statistiken über die Matrix zurück"""
        total = self.size * self.size
        locked = np.sum(self.locked)
        unknown = total - locked
        
        black = np.sum(self.grid[self.locked] == CellState.BLACK)
        white = np.sum(self.grid[self.locked] == CellState.WHITE)
        
        return {
            'total_cells': total,
            'known_cells': int(locked),
            'unknown_cells': int(unknown),
            'black_cells': int(black),
            'white_cells': int(white),
            'completeness': locked / total * 100
        }
    
    def to_binary_grid(self) -> np.ndarray:
        """
        Konvertiert zu binärem Grid (0/1) für QR-Dekodierung
        UNKNOWN-Zellen werden als 0 behandelt
        
        Returns:
            Binary numpy array (0=weiß, 1=schwarz)
        """
        binary = np.zeros((self.size, self.size), dtype=np.uint8)
        binary[self.grid == CellState.BLACK] = 1
        return binary
    
    def clone(self) -> 'QRMatrix':
        """Erstellt eine tiefe Kopie der Matrix"""
        new_matrix = QRMatrix.__new__(QRMatrix)
        new_matrix.size = self.size
        new_matrix.grid = self.grid.copy()
        new_matrix.locked = self.locked.copy()
        return new_matrix
    
    def reset(self):
        """Setzt die Matrix zurück (behält nur feste Patterns)"""
        self.grid = np.full((self.size, self.size), CellState.UNKNOWN, dtype=int)
        self.locked = np.zeros((self.size, self.size), dtype=bool)
        self._add_fixed_patterns()
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"QRMatrix(size={self.size}, "
                f"known={stats['known_cells']}/{stats['total_cells']} "
                f"[{stats['completeness']:.1f}%])")