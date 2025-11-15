"""
QR-Code Rekonstruktion - Main Entry Point
Startet die GUI-Anwendung
"""

import sys
import os

# Füge den Projektpfad zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qr_reconstruction.ui.main_window import MainWindow


def main():
    """Hauptfunktion"""
    print("""
╔════════════════════════════════════════════════════════════╗
║        QR-Code Rekonstruktion - Simon's Toolset            ║
║                                                            ║
║  Rekonstruiere beschädigte QR-Codes durch Bruteforcing    ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app = MainWindow()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n\nAnwendung beendet.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()