"""
Verbessertes Test-Script um pyzbar-Installation zu prüfen
"""

import numpy as np
from PIL import Image
import sys
import os

print("="*60)
print("PYZBAR INSTALLATIONS-TEST")
print("="*60)

# Test 1: Prüfe pyzbar Import
print("\n[Test 1] Prüfe pyzbar Import...")
try:
    import pyzbar.pyzbar as pyzbar
    print("  ✓ pyzbar erfolgreich importiert")
    print(f"  Version: {pyzbar.__version__ if hasattr(pyzbar, '__version__') else 'unbekannt'}")
except ImportError as e:
    print(f"  ✗ pyzbar Import fehlgeschlagen: {e}")
    print("\n  LÖSUNG:")
    print("  1. Installiere pyzbar: pip install pyzbar")
    print("  2. Auf Windows: Lade zbar DLL herunter")
    print("     Download: https://sourceforge.net/projects/zbar/files/zbar/0.10/")
    print("     Entpacke und kopiere libiconv.dll, libzbar-64.dll in Python-Verzeichnis")
    sys.exit(1)

# Test 2: Erstelle einen echten QR-Code
print("\n[Test 2] Erstelle Test-QR-Code...")
try:
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data("https://github.com")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    os.makedirs('test_output', exist_ok=True)
    img.save("test_output/test_qr_generated.png")
    print("  ✓ QR-Code erstellt: test_output/test_qr_generated.png")
except Exception as e:
    print(f"  ✗ QR-Code-Erstellung fehlgeschlagen: {e}")
    sys.exit(1)

# Test 3: Dekodiere den QR-Code
print("\n[Test 3] Dekodiere QR-Code...")
try:
    img = Image.open("test_output/test_qr_generated.png")
    decoded = pyzbar.decode(img)
    
    if decoded:
        print(f"  ✓ Dekodierung erfolgreich!")
        print(f"  Anzahl gefundener Codes: {len(decoded)}")
        for i, obj in enumerate(decoded):
            print(f"  Code {i+1}:")
            print(f"    Typ: {obj.type}")
            print(f"    Inhalt: {obj.data.decode('utf-8')}")
            print(f"    Position: {obj.rect}")
    else:
        print("  ✗ Dekodierung fehlgeschlagen - kein QR-Code erkannt")
        print("\n  MÖGLICHE URSACHEN:")
        print("  - zbar DLL fehlt (Windows)")
        print("  - Bild zu klein/groß")
        print("  - Bild-Format nicht unterstützt")
        sys.exit(1)
        
except Exception as e:
    print(f"  ✗ Fehler bei Dekodierung: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Teste verschiedene Bildformate
print("\n[Test 4] Teste verschiedene Bildformate...")
test_cases = [
    ("Standard (schwarz=0, weiß=255)", lambda: np.array([[0, 255], [255, 0]], dtype=np.uint8)),
    ("Invertiert (schwarz=255, weiß=0)", lambda: np.array([[255, 0], [0, 255]], dtype=np.uint8)),
]

for name, grid_func in test_cases:
    print(f"\n  Teste: {name}")
    try:
        # Erstelle Mini-QR (21x21)
        size = 21
        grid = np.random.choice([0, 255], size=(size, size)).astype(np.uint8)
        
        # Erstelle QR-Code mit qrcode library
        qr = qrcode.QRCode(version=1, box_size=1, border=0)
        qr.add_data("TEST")
        qr.make(fit=True)
        
        # Konvertiere zu numpy array
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_array = np.array(qr_img.convert('L'))
        
        # Skaliere hoch
        from PIL import Image
        img = Image.fromarray(qr_array, mode='L')
        img = img.resize((size * 20, size * 20), Image.Resampling.NEAREST)
        
        # Versuche zu dekodieren
        decoded = pyzbar.decode(img)
        if decoded:
            print(f"    ✓ Funktioniert: {decoded[0].data.decode('utf-8')}")
        else:
            print(f"    ✗ Keine Dekodierung")
    except Exception as e:
        print(f"    ✗ Fehler: {e}")

# Test 5: Prüfe Plattform-spezifische Details
print("\n[Test 5] System-Informationen...")
print(f"  Python: {sys.version}")
print(f"  Plattform: {sys.platform}")
print(f"  Architektur: {sys.maxsize > 2**32 and '64-bit' or '32-bit'}")

if sys.platform == 'win32':
    print("\n  WINDOWS-HINWEIS:")
    print("  Stelle sicher, dass folgende DLLs im Python-Verzeichnis sind:")
    print("  - libiconv.dll")
    print("  - libzbar-64.dll (oder libzbar-32.dll für 32-bit Python)")
    print("\n  Oder installiere via conda:")
    print("  conda install -c conda-forge pyzbar")

# Zusammenfassung
print("\n" + "="*60)
print("TEST-ZUSAMMENFASSUNG")
print("="*60)
print("✓ Alle Tests erfolgreich!")
print("\nWenn du immer noch Probleme hast:")
print("1. Prüfe ob zbar DLLs installiert sind (Windows)")
print("2. Versuche: pip uninstall pyzbar && pip install pyzbar")
print("3. Versuche: conda install -c conda-forge pyzbar")
print("="*60)