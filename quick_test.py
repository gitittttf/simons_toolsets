"""
Quick Test: Erstelle einen bekannten QR-Code und teste die Rekonstruktion
"""

import numpy as np
import qrcode
from PIL import Image
import os

# Importiere deine Module
from qr_reconstruction.core.qr_matrix import QRMatrix, CellState
from qr_reconstruction.core.validator import QRValidator
from qr_reconstruction.core.bruteforce import BruteforceEngine

print("="*60)
print("QUICK TEST: QR-Code Rekonstruktion")
print("="*60)

# Erstelle Output-Ordner
os.makedirs('test_output', exist_ok=True)
os.makedirs('debug_qr_images', exist_ok=True)

# SCHRITT 1: Erstelle einen echten, gültigen QR-Code
print("\n[Schritt 1] Erstelle Test-QR-Code...")
test_data = "HELLO WORLD"
qr = qrcode.QRCode(version=1, box_size=1, border=0)
qr.add_data(test_data)
qr.make(fit=True)

# Hole die Matrix-Daten
qr_matrix_data = qr.get_matrix()
size = len(qr_matrix_data)
print(f"  QR-Code-Größe: {size}x{size}")
print(f"  Inhalt: '{test_data}'")

# SCHRITT 2: Konvertiere zu unserer QRMatrix
print("\n[Schritt 2] Konvertiere zu QRMatrix...")
matrix = QRMatrix(size)

# WICHTIG: Überschreibe die automatische Struktur mit dem echten QR-Code
for i in range(size):
    for j in range(size):
        if qr_matrix_data[i][j]:
            matrix.grid[i, j] = CellState.BLACK
        else:
            matrix.grid[i, j] = CellState.WHITE
        matrix.locked[i, j] = True  # Alles ist bekannt

print(f"  Matrix erstellt: {matrix}")

# SCHRITT 3: Teste die Validierung
print("\n[Schritt 3] Teste Validierung...")
validator = QRValidator(debug_mode=True)
result = validator.validate(matrix)

print(f"\n  Ergebnis:")
print(f"  - Gültig: {result.is_valid}")
print(f"  - Confidence: {result.confidence:.1f}%")
print(f"  - Dekodiert: {result.decoded_data}")
print(f"  - Debug: {result.debug_info}")

if result.decoded_data == test_data:
    print("\n  ✓ Perfekt! Dekodierung erfolgreich!")
else:
    print(f"\n  ✗ Fehler! Erwartet: '{test_data}', Bekommen: '{result.decoded_data}'")

# Speichere das Bild
binary = matrix.to_binary_grid()
img_array = np.uint8((1 - binary) * 255)
img = Image.fromarray(img_array, mode='L')
img = img.resize((size * 20, size * 20), Image.Resampling.NEAREST)
img.save('test_output/test_valid_qr.png')
print(f"\n  QR-Code gespeichert: test_output/test_valid_qr.png")

# SCHRITT 4: Simuliere teilweise unbekannte Bereiche
print("\n[Schritt 4] Simuliere teilweise unbekannten QR-Code...")

# Erstelle Kopie
partial_matrix = matrix.clone()

# Setze einen kleinen Bereich als unbekannt (z.B. 3x3 Bereich in der Mitte)
unknown_region = []
center_row = size // 2
center_col = size // 2

for i in range(center_row - 1, center_row + 2):
    for j in range(center_col - 1, center_col + 2):
        if not partial_matrix._is_fixed_pattern(i, j):
            partial_matrix.grid[i, j] = CellState.UNKNOWN
            partial_matrix.locked[i, j] = False
            unknown_region.append((i, j))

print(f"  Unbekannte Zellen: {len(unknown_region)}")
print(f"  Position: Zentrum ({center_row}, {center_col})")
print(f"  Mögliche Kombinationen: {2**len(unknown_region)}")

# SCHRITT 5: Teste Bruteforce
print("\n[Schritt 5] Teste Bruteforce-Rekonstruktion...")
print("  (Das kann einen Moment dauern...)\n")

engine = BruteforceEngine(partial_matrix, validator)

# Callback für Ergebnisse
found_correct = False

def on_result(result):
    global found_correct
    if result.decoded_data == test_data:
        print(f"  ✓ KORREKT REKONSTRUIERT! Confidence: {result.confidence:.1f}%")
        found_correct = True

engine.set_result_callback(on_result)

# Starte Bruteforce (schneller Modus)
results = engine.run(mode='fast', max_iterations=2**len(unknown_region), parallel=False)

# SCHRITT 6: Analysiere Ergebnisse
print("\n[Schritt 6] Ergebnis-Analyse...")
print(f"  Gefundene gültige Kandidaten: {len(results)}")

if found_correct:
    print(f"  ✓ Original-Daten erfolgreich rekonstruiert!")
else:
    print(f"  ✗ Original-Daten nicht gefunden")
    if results:
        print(f"\n  Beste Kandidaten:")
        for i, r in enumerate(results[:5], 1):
            print(f"    {i}. Confidence: {r.confidence:.1f}% | Inhalt: {r.decoded_data}")

# SCHRITT 7: Zusammenfassung
print("\n" + "="*60)
print("TEST-ZUSAMMENFASSUNG")
print("="*60)

if found_correct and result.decoded_data == test_data:
    print("✓ ALLE TESTS ERFOLGREICH!")
    print("\nDein System ist bereit für die QR-Rekonstruktion!")
else:
    print("✗ TESTS TEILWEISE FEHLGESCHLAGEN")
    print("\nMögliche Probleme:")
    print("1. Dekodierung funktioniert nicht richtig")
    print("2. Bruteforce findet keine gültigen Kandidaten")
    print("3. Confidence-Scoring ist zu streng")
    print("\nPrüfe die Debug-Bilder in: debug_qr_images/")

print("="*60)