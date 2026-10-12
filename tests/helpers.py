"""Gemeinsame Hilfsfunktionen: echte QR-Codes mit der qrcode-Bibliothek erzeugen"""

import numpy as np
import qrcode

from tools.qr_reconstruction.core.qr_matrix import QRMatrix

EC_LEVELS = {
    'L': qrcode.constants.ERROR_CORRECT_L,
    'M': qrcode.constants.ERROR_CORRECT_M,
    'Q': qrcode.constants.ERROR_CORRECT_Q,
    'H': qrcode.constants.ERROR_CORRECT_H,
}


def make_qr_grid(data: str, version=None, ec='M', mask=None) -> np.ndarray:
    """0/1-Grid (1 = schwarz) ohne Rand"""
    qr = qrcode.QRCode(version=version, error_correction=EC_LEVELS[ec], border=0, mask_pattern=mask)
    qr.add_data(data)
    qr.make(fit=version is None)
    return np.array(qr.get_matrix(), dtype=int)


def make_known_matrix(data: str, **kwargs) -> QRMatrix:
    """QRMatrix mit vollständig bekanntem (gesperrtem) Inhalt"""
    grid = make_qr_grid(data, **kwargs)
    matrix = QRMatrix(grid.shape[0])
    matrix.grid = grid.copy()
    matrix.locked[:] = True
    return matrix


def damage(matrix: QRMatrix, cells, wrong_value: bool = True) -> QRMatrix:
    """Entsperrt Zellen; optional mit falschem Wert, damit die Suche nicht zufällig beim Original startet"""
    damaged = matrix.clone()
    for r, c in cells:
        damaged.locked[r, c] = False
        if wrong_value:
            damaged.grid[r, c] ^= 1
    return damaged
