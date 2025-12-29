"""
Quick Test: GitHub Preset mit Random Damage
"""

import numpy as np
import qrcode
import random
import os
from PIL import Image

# Importiere deine Module
from tools.qr_reconstruction.core.qr_matrix import QRMatrix, CellState
from tools.qr_reconstruction.core.validator import QRValidator
from tools.qr_reconstruction.core.bruteforce import BruteforceEngine

if __name__ == "__main__":
    print("="*60)
    print("VERIFICATION: GitHub QR-Code Rekonstruktion")
    print("="*60)

    # Output
    os.makedirs('test_output', exist_ok=True)

    # 1. Erstelle GitHub QR
    print("\n[1] Erstelle Original 'https://www.github.com/'...")
    test_data = "https://www.github.com/"
    qr = qrcode.QRCode(version=1, box_size=1, border=0)
    qr.add_data(test_data)
    qr.make(fit=True)

    qr_data = qr.get_matrix()
    size = len(qr_data)
    print(f"  Größe: {size}x{size}")

    # 2. Convert to Matrix
    matrix = QRMatrix(size)
    for r in range(size):
        for c in range(size):
            matrix.grid[r, c] = CellState.BLACK if qr_data[r][c] else CellState.WHITE
            matrix.locked[r, c] = True

    # 3. Simulate Damage
    print("\n[2] Simuliere Schaden (Lösche ~20% der Pixel)...")
    partial = matrix.clone()
    damage_count = 0
    total_mutable = 0

    # Random seed for reproducibility during dev, but user wants random so maybe just log it?
    # random.seed(42) 

    for r in range(size):
        for c in range(size):
            if not partial._is_fixed_pattern(r, c):
                total_mutable += 1
                if random.random() < 0.20: # 20% Chance
                    # Mark as UNKNOWN (unlock)
                    partial.grid[r, c] = CellState.WHITE # Visual default
                    partial.locked[r, c] = False 
                    damage_count += 1

    print(f"  Gelöschte Pixel: {damage_count} / {total_mutable} ({damage_count/total_mutable*100:.1f}%)")
    print(f"  Mögliche Kombinationen: 2^{damage_count}")

    # 4. Run Reconstruction
    print("\n[3] Starte Bruteforce (Fast Mode)...")
    validator = QRValidator(debug_mode=False)
    engine = BruteforceEngine(partial, validator)

    found = False
    def on_res(r):
        global found
        if r.decoded_data == test_data:
            print(f"  ✓ GEFUNDEN! Confidence: {r.confidence}%")
            found = True

    engine.set_result_callback(on_res)

    print("  (Korrigiere Schaden auf testbares Niveau für Quick-Test: max 8 fehlende Pixel)")
    # Reset and re-damage carefully
    partial = matrix.clone()
    targets = []
    for r in range(size):
        for c in range(size):
            if not partial._is_fixed_pattern(r, c):
                targets.append((r,c))

    random.shuffle(targets)
    selected = targets[:8] # Remove 8 random pixels (2^8 = 256 options, safely fits in Fast Mode's 1000 limit)
    for r, c in selected:
        partial.locked[r, c] = False
        # Set to wrong value potentially? Or just white (unknown)
        partial.grid[r, c] = CellState.WHITE

    print(f"  Tatsächlich fehlend: {len(selected)} Pixel")
    print(f"  Suchraum: 2^{len(selected)} = {2**len(selected)} Operationen")

    results = engine.run(mode='fast', max_iterations=1000, parallel=True) 
    # Parallel True to test multithreading too!

    print("\n[4] Ergebnis:")
    if found:
        print("  ✓ SUCCESS: Code wiederhergestellt.")
    else:
        print("  ✗ FAILED: Code nicht gefunden.")
        if results:
            print(f"  Bester Kandidat: {results[0].decoded_data}")

    print("="*60)