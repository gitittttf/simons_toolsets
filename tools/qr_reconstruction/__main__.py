"""
Entry point for running the QR-Code Reconstruction tool as a module.

Usage:
    python -m qr_reconstruction
"""

from .ui.main_window import MainWindow


def main():
    """Starts the application"""
    print("=" * 50)
    print("🔍 QR-Code Rekonstruktion")
    print("   Modern UI • Intelligent Scoring • Easy to use")
    print("=" * 50)
    
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
