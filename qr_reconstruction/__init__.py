"""
QR-Code Rekonstruktions-Tool
Teil von Simon's Toolset
"""

__version__ = "1.0.0"
__author__ = "Simon"

# Import wichtiger Komponenten für einfachen Zugriff
from .core import QRMatrix, CellState, BruteforceEngine, QRValidator
from .ui import MainWindow

__all__ = [
    'QRMatrix',
    'CellState', 
    'BruteforceEngine',
    'QRValidator',
    'MainWindow'
]