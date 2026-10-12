"""
Eigener QR-Decoder für vollständige Modulraster (0/1-Matrix)

Ersetzt pyzbar/zbar im Validator. Gründe:
- zbar 0.10 (in den Windows-Wheels von pyzbar) bricht bei Symbolen mit Structured-Append-Kopf
  (z.B. "Teil 2 von 3") per Assertion den ganzen Prozess ab (qrdectxt.c, Zeile 405). Solche Symbole
  entstehen bei mehrdeutigen Rekonstruktionen als gültige, aber zufällige Kandidaten.
- zbar rät die Zeichenkodierung von Byte-Segmenten und liest UTF-8 teils als Shift-JIS.
- Für ein Raster braucht es keine Bildverarbeitung - Format, Codewörter, Reed-Solomon und Daten
  sind in core/ bereits vollständig und gegen die qrcode-Bibliothek getestet implementiert.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .codewords import deinterleave, read_codewords
from .data_decoder import DataDecodeError, decode_data
from .qr_matrix import get_version_for_size
from .rs_decoder import solve_block
from .spec import VALID_FORMATS, block_layout, format_info_positions, read_format_bits

# Formate mit bis zu so vielen abweichenden Bits (in der besseren der beiden Kopien) werden probiert.
# BCH(15,5) korrigiert sicher nur 3; die RS-Prüfung bestätigt das Format, daher darf es mehr sein
# (zbar las im Test noch Codes mit 4 abweichenden Bits).
MAX_FORMAT_DISTANCE = 6
# Beide Kopien zusammen (30 Bit) haben zwischen gültigen Formaten mindestens 14 Bit Abstand: bis zu
# dieser Summe ist das nächste Format eindeutig, die übrigen werden dann nicht probiert (spart die teure
# Fehlerkorrektur). Nur eine Kopie zu betrachten reicht nicht - dort kann ein falsches Format näher liegen.
UNIQUE_FORMAT_SUM = 6


@dataclass
class DecodedSymbol:
    text: str
    ec_level: str
    mask: int
    corrected_errors: int   # Codewörter, die die Fehlerkorrektur geändert hat
    format_distance: int    # abweichende Format-Bits (bessere Kopie)
    modes: List[str]
    padding_ok: bool


def decode_grid(grid: np.ndarray, max_format_distance: int = MAX_FORMAT_DISTANCE) -> Optional[DecodedSymbol]:
    """
    Dekodiert eine vollständige 0/1-Matrix (1 = schwarz) oder gibt None zurück.
    Wirft keine Ausnahmen für ungültige Inhalte.
    """
    grid = (np.asarray(grid) == 1).astype(np.uint8)
    size = grid.shape[0]
    version = get_version_for_size(size)
    if version is None or grid.shape != (size, size):
        return None

    copies = [read_format_bits(grid, positions) for positions in format_info_positions(size)]
    candidates = []
    for bits, (level, mask) in VALID_FORMATS.items():
        distances = [bin(bits ^ copy).count('1') for copy in copies]
        candidates.append((sum(distances), min(distances), level, mask))
    candidates.sort()
    # Eindeutig → nur dieses Format; sonst alle mit höchstens max_format_distance Abweichung in einer Kopie
    # (zbar liest auch Codes, bei denen das wahre Format in beiden Kopien 6 Bit abweicht)
    tries = 1 if candidates[0][0] <= UNIQUE_FORMAT_SUM else len(candidates)
    known = np.ones_like(grid, dtype=bool)
    for _, distance, level, mask in candidates[:tries]:
        if distance > max_format_distance:
            continue
        reading = read_codewords(grid, known, version, mask)
        layout = block_layout(version, level)
        blocks, errors = [], 0
        for values, (_, nsym) in zip(deinterleave(reading.values, version, level), layout):
            solution = solve_block(values, [0xFF] * len(values), nsym, allow_errors=True)
            if solution is None:
                break
            blocks.append(solution.codeword())
            errors += solution.corrected_errors
        else:
            data = bytes(b for block, (data_len, _) in zip(blocks, layout) for b in block[:data_len])
            try:
                decoded = decode_data(data, version)
            except DataDecodeError:
                continue
            return DecodedSymbol(text=decoded.text, ec_level=level, mask=mask, corrected_errors=errors,
                                 format_distance=distance, modes=decoded.modes, padding_ok=decoded.padding_ok)
    return None
