"""
QR-Code Rekonstruktions-Tool
Teil von Simon's Toolset
"""

__version__ = "1.0.0"
__author__ = "Simon"

# Import wichtiger Komponenten für einfachen Zugriff
from .core import QRMatrix, CellState, BruteforceEngine, QRValidator

__all__ = [
    'QRMatrix',
    'CellState',
    'BruteforceEngine',
    'QRValidator',
    'MainWindow'
]


def __getattr__(name):
    # UI erst bei Bedarf laden, damit der Core ohne tkinter/customtkinter nutzbar ist
    if name == 'MainWindow':
        from .ui import MainWindow
        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
