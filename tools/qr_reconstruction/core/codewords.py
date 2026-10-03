"""
Codewort-Ebene eines QR-Codes

- Welche Module gehören zu Daten/EC (alles außer Funktionsmustern und Format-Info)
- Zickzack-Reihenfolge der Datenmodule (Spezifikation 7.7.3)
- Codewörter lesen (inkl. "welche Bits sind bekannt") und wieder in eine Matrix schreiben
- Aufteilung der Codewort-Folge in RS-Blöcke (Interleaving)
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple

import numpy as np

from .qr_matrix import QRMatrix, QR_VERSIONS
from .spec import (
    block_layout, format_bits, format_info_positions, mask_pattern,
    num_raw_data_modules, num_total_codewords,
)


@lru_cache(maxsize=None)
def function_mask(version: int) -> np.ndarray:
    """bool-Array: True für Funktionsmuster (Finder, Timing, Alignment, ...) und Format-Info"""
    size = QR_VERSIONS[version][0]
    mask = QRMatrix(size).fixed.copy()
    for positions in format_info_positions(size):
        for r, c in positions:
            mask[r, c] = True
    mask.flags.writeable = False
    return mask


@lru_cache(maxsize=None)
def data_module_order(version: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    (rows, cols) aller Datenmodule in Platzierungsreihenfolge:
    Spaltenpaare von rechts nach links, abwechselnd aufwärts/abwärts, Spalte 6 (Timing) übersprungen.
    """
    size = QR_VERSIONS[version][0]
    is_function = function_mask(version)
    rows, cols = [], []
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        upward = ((right + 1) & 2) == 0
        for vert in range(size):
            row = size - 1 - vert if upward else vert
            for col in (right, right - 1):
                if not is_function[row, col]:
                    rows.append(row)
                    cols.append(col)
        right -= 2
    assert len(rows) == num_raw_data_modules(version)
    return np.array(rows, dtype=np.intp), np.array(cols, dtype=np.intp)


@dataclass
class CodewordReading:
    """Codewörter in Übertragungsreihenfolge (interleaved), bereits entmaskiert"""
    values: List[int]       # unbekannte Bits als 0
    known_masks: List[int]  # Bit gesetzt = Bit bekannt (0xFF = vollständig bekannt)

    @property
    def num_unknown_codewords(self) -> int:
        return sum(1 for m in self.known_masks if m != 0xFF)


def read_codewords(grid: np.ndarray, known: np.ndarray, version: int, mask: int) -> CodewordReading:
    """
    Liest alle Codewörter aus einer (teilweise bekannten) Matrix.

    Args:
        grid: 0/1-Werte (1 = schwarz); Werte unbekannter Module sind egal
        known: bool-Array, True = Modul bekannt
        mask: Maskennummer 0-7 (wird entfernt)
    """
    size = grid.shape[0]
    rows, cols = data_module_order(version)
    count = num_total_codewords(version) * 8  # Restbits am Ende gehören zu keinem Codewort
    rows, cols = rows[:count], cols[:count]

    bits = (grid[rows, cols] == 1) ^ mask_pattern(mask, size)[rows, cols]
    bits = np.where(known[rows, cols], bits, False).astype(np.uint8)
    known_bits = known[rows, cols].astype(np.uint8)

    # MSB zuerst: 8 aufeinanderfolgende Module bilden ein Codewort
    values = np.packbits(bits).tolist()
    known_masks = np.packbits(known_bits).tolist()
    return CodewordReading(values, known_masks)


def render_matrix(version: int, ec_level: str, mask: int, codewords: List[int]) -> np.ndarray:
    """Vollständige 0/1-Matrix aus allen Codewörtern (interleaved), inkl. Funktionsmuster und Format-Info"""
    size = QR_VERSIONS[version][0]
    base = QRMatrix(size)
    grid = np.where(base.fixed, base.grid, 0).astype(np.uint8)

    rows, cols = data_module_order(version)
    bits = np.unpackbits(np.array(codewords, dtype=np.uint8))
    data_bits = np.zeros(len(rows), dtype=np.uint8)  # Restbits = 0
    data_bits[:len(bits)] = bits
    grid[rows, cols] = data_bits ^ mask_pattern(mask, size)[rows, cols]

    fmt = format_bits(ec_level, mask)
    for positions in format_info_positions(size):
        for i, (r, c) in enumerate(positions):
            grid[r, c] = (fmt >> i) & 1
    return grid


@lru_cache(maxsize=None)
def interleave_order(version: int, ec_level: str) -> Tuple[Tuple[int, int], ...]:
    """
    Für jede Position der übertragenen Codewort-Folge: (Block-Index, Position im Block).
    Erst werden die Datencodewörter spaltenweise über alle Blöcke verteilt, dann die EC-Codewörter.
    """
    layout = block_layout(version, ec_level)
    order = []
    for i in range(max(data_len for data_len, _ in layout)):
        for b, (data_len, _) in enumerate(layout):
            if i < data_len:
                order.append((b, i))
    ec_len = layout[0][1]
    for i in range(ec_len):
        for b, (data_len, _) in enumerate(layout):
            order.append((b, data_len + i))
    return tuple(order)


def deinterleave(sequence: List[int], version: int, ec_level: str) -> List[List[int]]:
    """Übertragene Folge → Liste von Blöcken (jeweils Daten + EC)"""
    layout = block_layout(version, ec_level)
    blocks = [[0] * (data_len + ec_len) for data_len, ec_len in layout]
    for value, (b, pos) in zip(sequence, interleave_order(version, ec_level)):
        blocks[b][pos] = value
    return blocks


def interleave(blocks: List[List[int]], version: int, ec_level: str) -> List[int]:
    """Liste von Blöcken → übertragene Folge"""
    return [blocks[b][pos] for b, pos in interleave_order(version, ec_level)]
