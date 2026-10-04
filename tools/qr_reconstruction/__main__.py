"""
Entry point for running the QR-Code Reconstruction tool as a module.

Usage:
    python -m tools.qr_reconstruction
"""

import logging

from .ui.main_window import MainWindow


def main():
    """Starts the application"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger(__name__).info("QR-Code Rekonstruktion startet")

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
