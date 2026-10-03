"""
QR-Code Spezifikation (ISO/IEC 18004) - Format- und Versionsinformationen

- Format-Info: 15 Bit = BCH(15,5) über (EC-Level, Maske), XOR 0x5412 → nur 32 gültige Werte
- Version-Info (ab Version 7): 18 Bit = BCH(18,6) über die Versionsnummer
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

# EC-Level-Bits wie im Format-String kodiert
EC_LEVEL_BITS = {'L': 0b01, 'M': 0b00, 'Q': 0b11, 'H': 0b10}
EC_LEVEL_FROM_BITS = {bits: level for level, bits in EC_LEVEL_BITS.items()}

FORMAT_GENERATOR = 0x537
FORMAT_XOR_MASK = 0x5412
VERSION_GENERATOR = 0x1F25


def _bch_remainder(value: int, generator: int, ecc_bits: int) -> int:
    gen_degree = generator.bit_length() - 1
    rem = value << ecc_bits
    for shift in range(rem.bit_length() - 1, gen_degree - 1, -1):
        if rem & (1 << shift):
            rem ^= generator << (shift - gen_degree)
    return rem


def format_bits(ec_level: str, mask: int) -> int:
    """15-Bit Format-Information (inkl. XOR-Maske) für EC-Level und Maske"""
    data = (EC_LEVEL_BITS[ec_level] << 3) | mask
    return ((data << 10) | _bch_remainder(data, FORMAT_GENERATOR, 10)) ^ FORMAT_XOR_MASK


def version_bits(version: int) -> int:
    """18-Bit Versions-Information (nur für Version >= 7 definiert)"""
    return (version << 12) | _bch_remainder(version, VERSION_GENERATOR, 12)


# Alle 32 gültigen Format-Strings: bits -> (ec_level, mask)
VALID_FORMATS: Dict[int, Tuple[str, int]] = {
    format_bits(level, mask): (level, mask)
    for level in EC_LEVEL_BITS
    for mask in range(8)
}


def format_info_positions(size: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    (row, col) der 15 Format-Bits, Index i = Bit i (LSB zuerst), für beide Kopien.
    Kopie 1 liegt um den Finder oben links, Kopie 2 ist auf oben rechts / unten links verteilt.
    """
    copy1 = [(i, 8) for i in range(6)] + [(7, 8), (8, 8), (8, 7)] + [(8, 14 - i) for i in range(9, 15)]
    copy2 = [(8, size - 1 - i) for i in range(8)] + [(size - 15 + i, 8) for i in range(8, 15)]
    return copy1, copy2


def version_info_positions(size: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """(row, col) der 18 Versions-Bits (LSB zuerst): Block oben rechts und Block unten links"""
    top_right = [(i // 3, size - 11 + i % 3) for i in range(18)]
    bottom_left = [(size - 11 + i % 3, i // 3) for i in range(18)]
    return top_right, bottom_left


def read_format_bits(grid: np.ndarray, positions: List[Tuple[int, int]]) -> int:
    """Liest 15 Format-Bits aus einem 0/1-Grid"""
    value = 0
    for i, (r, c) in enumerate(positions):
        if grid[r, c] == 1:
            value |= 1 << i
    return value


def decode_format_bits(bits: int, max_distance: int = 3) -> Optional[Tuple[str, int, int]]:
    """
    Nächster gültiger Format-String per Hamming-Distanz.
    BCH(15,5) korrigiert bis zu 3 Bitfehler.

    Returns:
        (ec_level, mask, distance) oder None wenn nicht korrigierbar
    """
    best = min(VALID_FORMATS, key=lambda valid: bin(valid ^ bits).count('1'))
    distance = bin(best ^ bits).count('1')
    if distance > max_distance:
        return None
    level, mask = VALID_FORMATS[best]
    return level, mask, distance
