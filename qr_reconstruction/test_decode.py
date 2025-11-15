"""
Test-Script um zu prüfen ob pyzbar funktioniert
"""

import numpy as np
from PIL import Image
import qrcode

# Teste 1: Erstelle einen echten QR-Code
print("Test 1: Erstelle QR-Code...")
qr = qrcode.QRCode(version=1, box_size=10, border=4)
qr.add_data("https://github.com")
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.save("test_qr_generated.png")
print("  QR-Code erstellt: test_qr_generated.png")

# Teste 2: Versuche zu dekodieren
print("\nTest 2: Dekodiere QR-Code...")
try:
    import pyzbar.pyzbar as pyzbar
    
    img = Image.open("test_qr_generated.png")
    decoded = pyzbar.decode(img)
    
    if decoded:
        print(f"  Dekodierung erfolgreich!")
        print(f"  Inhalt: {decoded[0].data.decode('utf-8')}")
    else:
        print("   Dekodierung fehlgeschlagen - kein QR-Code erkannt")
        
except ImportError:
    print("   pyzbar ist nicht installiert!")
    print("   Installiere mit: pip install pyzbar")
    print("   WICHTIG: Auf Windows brauchst du auch die DLL!")
    print("   Download: https://sourceforge.net/projects/zbar/files/zbar/0.10/")
except Exception as e:
    print(f"   Fehler: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Wenn Test 2 fehlschlägt, ist pyzbar nicht richtig installiert.")
print("Auf Windows: Lade zbar DLL herunter und kopiere sie ins Python-Verzeichnis")
print("="*60)