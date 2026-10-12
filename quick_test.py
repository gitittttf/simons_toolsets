"""
Quick Test: GitHub-QR-Code mit zufälligem Schaden rekonstruieren

1. Reed-Solomon-Rekonstruktion bei ~20% fehlenden Pixeln (mit Pixel-Bruteforce aussichtslos)
2. Pixel-Bruteforce als Fallback bei 8 fehlenden Pixeln
"""

import random
import sys

import qrcode

from tools.qr_reconstruction.core.qr_matrix import QRMatrix, CellState
from tools.qr_reconstruction.core.validator import QRValidator
from tools.qr_reconstruction.core.bruteforce import BruteforceEngine
from tools.qr_reconstruction.core.reconstructor import Reconstructor

TEST_DATA = "https://www.github.com/"


def make_matrix() -> QRMatrix:
    qr = qrcode.QRCode(box_size=1, border=0)
    qr.add_data(TEST_DATA)
    qr.make(fit=True)
    qr_data = qr.get_matrix()
    matrix = QRMatrix(len(qr_data))
    for r, row in enumerate(qr_data):
        for c, value in enumerate(row):
            matrix.grid[r, c] = CellState.BLACK if value else CellState.WHITE
            matrix.locked[r, c] = True
    return matrix


def damage(matrix: QRMatrix, count: int) -> QRMatrix:
    """Entsperrt `count` zufällige Nicht-Funktions-Zellen und setzt sie auf einen falschen Wert"""
    partial = matrix.clone()
    targets = [(r, c) for r in range(matrix.size) for c in range(matrix.size)
               if not partial._is_fixed_pattern(r, c)]
    for r, c in random.sample(targets, count):
        partial.locked[r, c] = False
        partial.grid[r, c] ^= 1
    return partial


if __name__ == "__main__":
    print("=" * 60)
    print("VERIFICATION: GitHub QR-Code Rekonstruktion")
    print("=" * 60)

    matrix = make_matrix()
    mutable = sum(1 for r in range(matrix.size) for c in range(matrix.size)
                  if not matrix._is_fixed_pattern(r, c))
    print(f"\nOriginal: {TEST_DATA!r}, Version {matrix.version} ({matrix.size}x{matrix.size})")
    validator = QRValidator(debug_mode=False)
    ok = True

    # 1. Reed-Solomon
    count = int(mutable * 0.20)
    print(f"\n[1] Reed-Solomon: {count} von {mutable} Pixeln unbekannt (20%)")
    results = Reconstructor(damage(matrix, count), validator).run(max_time=30)
    if results and results[0].decoded_data == TEST_DATA:
        print(f"  ✓ SUCCESS: {results[0].decoded_data!r} (Confidence {results[0].confidence:.0f}%)")
        print(f"    {results[0].debug_info}")
    else:
        ok = False
        print(f"  ✗ FAILED: {results[0].decoded_data if results else 'keine Lösung'!r}")

    # 2. Pixel-Bruteforce
    print("\n[2] Pixel-Bruteforce: 8 Pixel unbekannt (2^8 = 256 Kombinationen)")
    engine = BruteforceEngine(damage(matrix, 8), validator)
    results = engine.run(mode='fast', max_iterations=1000, parallel=True)
    if any(r.decoded_data == TEST_DATA for r in results):
        print(f"  ✓ SUCCESS: Code wiederhergestellt ({engine.stats['tested']} Tests)")
    else:
        ok = False
        print("  ✗ FAILED: Code nicht gefunden.")

    print("=" * 60)
    sys.exit(0 if ok else 1)
