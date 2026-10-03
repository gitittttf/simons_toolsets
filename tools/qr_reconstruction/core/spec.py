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


# =============================================================================
# Fehlerkorrektur-Blöcke (Tabelle 9 der Spezifikation), Index = Version (0 ungenutzt)
# =============================================================================
ECC_CODEWORDS_PER_BLOCK = {
    'L': (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28,
          28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    'M': (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26,
          26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    'Q': (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30,
          28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    'H': (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28,
          30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}

NUM_EC_BLOCKS = {
    'L': (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8,
          8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    'M': (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16,
          17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    'Q': (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20,
          23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    'H': (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25,
          25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}


def num_raw_data_modules(version: int) -> int:
    """Anzahl Module für Daten + EC (inkl. Restbits), d.h. alles außer Funktionsmustern"""
    result = (16 * version + 128) * version + 64
    if version >= 2:
        num_align = version // 7 + 2
        result -= (25 * num_align - 10) * num_align - 55
        if version >= 7:
            result -= 36
    return result


def num_total_codewords(version: int) -> int:
    return num_raw_data_modules(version) // 8


def block_layout(version: int, ec_level: str) -> List[Tuple[int, int]]:
    """(Daten-Codewörter, EC-Codewörter) je Block; kurze Blöcke zuerst"""
    num_blocks = NUM_EC_BLOCKS[ec_level][version]
    ec_len = ECC_CODEWORDS_PER_BLOCK[ec_level][version]
    total = num_total_codewords(version)
    short_len = total // num_blocks
    num_short = num_blocks - total % num_blocks
    return [(short_len - ec_len + (0 if i < num_short else 1), ec_len) for i in range(num_blocks)]


def num_data_codewords(version: int, ec_level: str) -> int:
    return sum(data_len for data_len, _ in block_layout(version, ec_level))


# =============================================================================
# Masken (x = Spalte, y = Zeile)
# =============================================================================
_MASK_FUNCTIONS = (
    lambda y, x: (x + y) % 2 == 0,
    lambda y, x: y % 2 == 0,
    lambda y, x: x % 3 == 0,
    lambda y, x: (x + y) % 3 == 0,
    lambda y, x: (x // 3 + y // 2) % 2 == 0,
    lambda y, x: x * y % 2 + x * y % 3 == 0,
    lambda y, x: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda y, x: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


def mask_pattern(mask: int, size: int) -> np.ndarray:
    """bool-Array [row, col]: True = Modul wird durch die Maske invertiert"""
    rows, cols = np.indices((size, size))
    return _MASK_FUNCTIONS[mask](rows, cols)


# =============================================================================
# Datenkodierung
# =============================================================================
MODE_TERMINATOR = 0b0000
MODE_NUMERIC = 0b0001
MODE_ALPHANUMERIC = 0b0010
MODE_STRUCTURED_APPEND = 0b0011
MODE_BYTE = 0b0100
MODE_FNC1_FIRST = 0b0101
MODE_ECI = 0b0111
MODE_KANJI = 0b1000
MODE_FNC1_SECOND = 0b1001

ALPHANUMERIC_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

# Bits des Zeichenzählers für Versionen 1-9 / 10-26 / 27-40
_CHAR_COUNT_BITS = {
    MODE_NUMERIC: (10, 12, 14),
    MODE_ALPHANUMERIC: (9, 11, 13),
    MODE_BYTE: (8, 16, 16),
    MODE_KANJI: (8, 10, 12),
}


def char_count_bits(mode: int, version: int) -> int:
    return _CHAR_COUNT_BITS[mode][0 if version <= 9 else 1 if version <= 26 else 2]
