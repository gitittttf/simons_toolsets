"""
QR-Matrix Verwaltung - Core Module
Verwaltet die QR-Code Grid-Daten mit korrekten offiziellen QR-Code-Spezifikationen

Offizielle QR-Code Größen:
- Version 1: 21×21
- Version 2: 25×25  
- Version 3: 29×29
- ... (jeweils +4)
- Version 40: 177×177
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from enum import IntEnum


class CellState(IntEnum):
    """Status einer QR-Code-Zelle"""
    WHITE = 0
    BLACK = 1
    UNKNOWN = -1


# Offizielle QR-Code Versionen und ihre Größen
# Version = (Größe, Alignment-Pattern-Positionen)
QR_VERSIONS: Dict[int, Tuple[int, List[int]]] = {
    1:  (21, []),
    2:  (25, [6, 18]),
    3:  (29, [6, 22]),
    4:  (33, [6, 26]),
    5:  (37, [6, 30]),
    6:  (41, [6, 34]),
    7:  (45, [6, 22, 38]),
    8:  (49, [6, 24, 42]),
    9:  (53, [6, 26, 46]),
    10: (57, [6, 28, 50]),
    11: (61, [6, 30, 54]),
    12: (65, [6, 32, 58]),
    13: (69, [6, 34, 62]),
    14: (73, [6, 26, 46, 66]),
    15: (77, [6, 26, 48, 70]),
    16: (81, [6, 26, 50, 74]),
    17: (85, [6, 30, 54, 78]),
    18: (89, [6, 30, 56, 82]),
    19: (93, [6, 30, 58, 86]),
    20: (97, [6, 34, 62, 90]),
    # Versionen 21-40 für sehr große QR-Codes
    21: (101, [6, 28, 50, 72, 94]),
    22: (105, [6, 26, 50, 74, 98]),
    23: (109, [6, 30, 54, 78, 102]),
    24: (113, [6, 28, 54, 80, 106]),
    25: (117, [6, 32, 58, 84, 110]),
    26: (121, [6, 30, 58, 86, 114]),
    27: (125, [6, 34, 62, 90, 118]),
    28: (129, [6, 26, 50, 74, 98, 122]),
    29: (133, [6, 30, 54, 78, 102, 126]),
    30: (137, [6, 26, 52, 78, 104, 130]),
    31: (141, [6, 30, 56, 82, 108, 134]),
    32: (145, [6, 34, 60, 86, 112, 138]),
    33: (149, [6, 30, 58, 86, 114, 142]),
    34: (153, [6, 34, 62, 90, 118, 146]),
    35: (157, [6, 30, 54, 78, 102, 126, 150]),
    36: (161, [6, 24, 50, 76, 102, 128, 154]),
    37: (165, [6, 28, 54, 80, 106, 132, 158]),
    38: (169, [6, 32, 58, 84, 110, 136, 162]),
    39: (173, [6, 26, 54, 82, 110, 138, 166]),
    40: (177, [6, 30, 58, 86, 114, 142, 170]),
}

# Generiere Liste aller gültigen Größen
VALID_QR_SIZES = [v[0] for v in QR_VERSIONS.values()]


def get_version_for_size(size: int) -> Optional[int]:
    """Gibt die QR-Version für eine Größe zurück, oder None wenn ungültig"""
    for version, (s, _) in QR_VERSIONS.items():
        if s == size:
            return version
    return None


def get_size_for_version(version: int) -> Optional[int]:
    """Gibt die Größe für eine QR-Version zurück"""
    if version in QR_VERSIONS:
        return QR_VERSIONS[version][0]
    return None


def get_alignment_positions(version: int) -> List[int]:
    """Gibt die Alignment-Pattern-Positionen für eine Version zurück"""
    if version in QR_VERSIONS:
        return QR_VERSIONS[version][1]
    return []


class QRMatrix:
    """Verwaltet die QR-Code-Matrix mit offiziellen QR-Spezifikationen"""
    
    # Nur offizielle QR-Größen erlauben
    SUPPORTED_SIZES = VALID_QR_SIZES
    MIN_SIZE = 21   # Version 1
    MAX_SIZE = 177  # Version 40
    
    def __init__(self, size: int = 21):
        """
        Initialisiert eine QR-Matrix mit korrekten Patterns
        
        Args:
            size: Muss eine offizielle QR-Größe sein (21, 25, 29, ...)
        """
        self.version = get_version_for_size(size)
        
        if self.version is None:
            # Finde nächste gültige Größe
            valid_sizes = VALID_QR_SIZES
            if size < valid_sizes[0]:
                size = valid_sizes[0]
            elif size > valid_sizes[-1]:
                size = valid_sizes[-1]
            else:
                # Finde nächste passende
                for vs in valid_sizes:
                    if vs >= size:
                        size = vs
                        break
            self.version = get_version_for_size(size)
        
        self.size = size
        self.grid = np.full((size, size), CellState.UNKNOWN, dtype=int)
        self.locked = np.zeros((size, size), dtype=bool)
        
        # Füge offizielle QR-Struktur hinzu
        self._add_fixed_patterns()
    
    def _add_fixed_patterns(self):
        """Fügt alle festen QR-Code-Muster gemäß Spezifikation hinzu"""
        self._add_finder_patterns()
        self._add_separators()
        self._add_timing_patterns()
        self._add_dark_module()
        
        if self.version >= 2:
            self._add_alignment_patterns()
        
        if self.version >= 7:
            self._add_version_info_areas()
    
    def _add_finder_patterns(self):
        """Fügt die drei 7×7 Finder-Patterns hinzu"""
        positions = [
            (0, 0),                      # Oben links
            (0, self.size - 7),          # Oben rechts
            (self.size - 7, 0)           # Unten links
        ]
        
        for r, c in positions:
            # 7×7 Finder Pattern
            for i in range(7):
                for j in range(7):
                    # Äußerer Rahmen oder inneres Quadrat = schwarz
                    if i == 0 or i == 6 or j == 0 or j == 6:
                        self._set_locked(r + i, c + j, CellState.BLACK)
                    # Weißer Ring
                    elif i == 1 or i == 5 or j == 1 or j == 5:
                        self._set_locked(r + i, c + j, CellState.WHITE)
                    # Schwarzes Zentrum (3×3)
                    else:
                        self._set_locked(r + i, c + j, CellState.BLACK)
    
    def _add_separators(self):
        """Fügt weiße Separatoren um Finder-Patterns hinzu (genau 1 Modul breit)"""
        # Oben links (Finder bei 0-6, 0-6)
        # Separator: Zeile 7, Spalten 0-7 und Spalte 7, Zeilen 0-7
        for i in range(8):
            self._set_locked(7, i, CellState.WHITE)  # Zeile unter Finder
        for i in range(7):  # Nicht 8, da Ecke schon gesetzt
            self._set_locked(i, 7, CellState.WHITE)  # Spalte rechts von Finder
        
        # Oben rechts (Finder bei 0-6, size-7 bis size-1)
        # Separator: Zeile 7, Spalten size-8 bis size-1 und Spalte size-8, Zeilen 0-7
        for i in range(8):
            self._set_locked(7, self.size - 8 + i, CellState.WHITE)  # Zeile unter Finder
        for i in range(7):
            self._set_locked(i, self.size - 8, CellState.WHITE)  # Spalte links von Finder
        
        # Unten links (Finder bei size-7 bis size-1, 0-6)
        # Separator: Zeile size-8, Spalten 0-7 und Spalte 7, Zeilen size-8 bis size-1
        for i in range(8):
            self._set_locked(self.size - 8, i, CellState.WHITE)  # Zeile über Finder
        for i in range(7):
            self._set_locked(self.size - 7 + i, 7, CellState.WHITE)  # Spalte rechts von Finder
    
    def _add_timing_patterns(self):
        """Fügt die alternierenden Timing-Patterns hinzu (Zeile/Spalte 6)"""
        for i in range(8, self.size - 8):
            value = CellState.BLACK if (i % 2 == 0) else CellState.WHITE
            self._set_locked(6, i, value)  # Horizontal
            self._set_locked(i, 6, value)  # Vertikal
    
    def _add_dark_module(self):
        """Fügt das immer schwarze Dark Module hinzu"""
        # Position: (4 * version + 9, 8)
        row = 4 * self.version + 9
        if row < self.size:
            self._set_locked(row, 8, CellState.BLACK)
    
    def _add_alignment_patterns(self):
        """Fügt Alignment-Patterns gemäß offizieller Spezifikation hinzu"""
        positions = get_alignment_positions(self.version)
        if not positions:
            return
        
        # Generiere alle Kombinationen
        centers = []
        for r in positions:
            for c in positions:
                centers.append((r, c))
        
        # Filtere die, die mit Finder-Patterns überlappen
        for r, c in centers:
            # Prüfe Überlappung mit Finder-Patterns
            if (r <= 8 and c <= 8):  # Oben links
                continue
            if (r <= 8 and c >= self.size - 9):  # Oben rechts
                continue
            if (r >= self.size - 9 and c <= 8):  # Unten links
                continue
            
            # 5×5 Alignment Pattern zeichnen
            for i in range(-2, 3):
                for j in range(-2, 3):
                    pr, pc = r + i, c + j
                    if 0 <= pr < self.size and 0 <= pc < self.size:
                        if abs(i) == 2 or abs(j) == 2:
                            self._set_locked(pr, pc, CellState.BLACK)
                        elif i == 0 and j == 0:
                            self._set_locked(pr, pc, CellState.BLACK)
                        else:
                            self._set_locked(pr, pc, CellState.WHITE)
    
    def _add_version_info_areas(self):
        """Reserviert Bereiche für Version-Info (ab Version 7)"""
        # Diese Bereiche werden später mit Versionsinformationen gefüllt
        # Für Rekonstruktion markieren wir sie als unbekannt
        pass  # Lasse sie als unbekannt für Bruteforce
    
    def _set_locked(self, row: int, col: int, value: CellState):
        """Setzt eine Zelle und sperrt sie"""
        if 0 <= row < self.size and 0 <= col < self.size:
            self.grid[row, col] = value
            self.locked[row, col] = True
    
    def set_cell(self, row: int, col: int, value: CellState, locked: bool = True):
        """Setzt eine einzelne Zelle"""
        if not (0 <= row < self.size and 0 <= col < self.size):
            raise ValueError(f"Position ({row}, {col}) außerhalb des Grids")
        
        self.grid[row, col] = value
        if locked:
            self.locked[row, col] = True
    
    def get_cell(self, row: int, col: int) -> Tuple[CellState, bool]:
        """Gibt den Status einer Zelle zurück: (value, is_locked)"""
        return self.grid[row, col], self.locked[row, col]
    
    def toggle_cell(self, row: int, col: int):
        """Wechselt zwischen WHITE und BLACK"""
        if self.locked[row, col]:
            return
        
        current = self.grid[row, col]
        if current == CellState.BLACK:
            self.grid[row, col] = CellState.WHITE
        else:
            self.grid[row, col] = CellState.BLACK
    
    def lock_cell(self, row: int, col: int):
        """Sperrt eine Zelle"""
        self.locked[row, col] = True
    
    def unlock_cell(self, row: int, col: int):
        """Entsperrt eine Zelle (nur wenn nicht festes Pattern)"""
        if not self._is_fixed_pattern(row, col):
            self.locked[row, col] = False
    
    def _is_fixed_pattern(self, row: int, col: int) -> bool:
        """Prüft ob Zelle Teil der festen QR-Struktur ist"""
        # Finder-Patterns (7×7) + Separatoren (1 breit) = 8×8 Bereich
        # Indices 0-7 = 8 Zellen
        
        # Oben links: rows 0-7, cols 0-7
        if row <= 7 and col <= 7:
            return True
        
        # Oben rechts: rows 0-7, cols size-8 bis size-1
        if row <= 7 and col >= self.size - 8:
            return True
        
        # Unten links: rows size-8 bis size-1, cols 0-7
        if row >= self.size - 8 and col <= 7:
            return True
        
        # Timing-Patterns (Zeile 6, Spalte 6)
        if row == 6 or col == 6:
            return True
        
        return False
    
    def get_unknown_cells(self) -> List[Tuple[int, int]]:
        """Gibt alle nicht gesperrten Zellen zurück"""
        unknown = []
        for i in range(self.size):
            for j in range(self.size):
                if not self.locked[i, j]:
                    unknown.append((i, j))
        return unknown
    
    def get_stats(self) -> dict:
        """Gibt Statistiken zurück"""
        total = self.size * self.size
        locked = int(np.sum(self.locked))
        unknown = total - locked
        
        black = int(np.sum(self.grid[self.locked] == CellState.BLACK))
        white = int(np.sum(self.grid[self.locked] == CellState.WHITE))
        
        return {
            'version': self.version,
            'total_cells': total,
            'known_cells': locked,
            'unknown_cells': unknown,
            'black_cells': black,
            'white_cells': white,
            'completeness': locked / total * 100
        }
    
    def to_binary_grid(self) -> np.ndarray:
        """Konvertiert zu binärem Grid (0/1)"""
        binary = np.zeros((self.size, self.size), dtype=np.uint8)
        binary[self.grid == CellState.BLACK] = 1
        return binary
    
    def clone(self) -> 'QRMatrix':
        """Erstellt eine Kopie"""
        new = QRMatrix.__new__(QRMatrix)
        new.size = self.size
        new.version = self.version
        new.grid = self.grid.copy()
        new.locked = self.locked.copy()
        return new
    
    def reset(self):
        """Setzt die Matrix zurück"""
        self.grid = np.full((self.size, self.size), CellState.UNKNOWN, dtype=int)
        self.locked = np.zeros((self.size, self.size), dtype=bool)
        self._add_fixed_patterns()
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"QRMatrix(version={self.version}, size={self.size}, "
                f"known={stats['known_cells']}/{stats['total_cells']})")