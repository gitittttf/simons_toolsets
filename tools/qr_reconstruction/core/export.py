"""
Export einer (rekonstruierten) QR-Matrix als scanbares Bild

Mit Ruhezone (4 Module weißer Rand, wie von der Spezifikation gefordert) - so lässt sich der
wiederhergestellte Code ausdrucken oder vom Bildschirm mit dem Handy scannen.
"""

from pathlib import Path

import numpy as np
from PIL import Image

QUIET_ZONE = 4


def matrix_to_image(grid: np.ndarray, scale: int = 12, border: int = QUIET_ZONE) -> Image.Image:
    """0/1-Matrix (1 = schwarz) → Graustufenbild"""
    pixels = np.where(np.asarray(grid) == 1, 0, 255).astype(np.uint8)
    pixels = np.pad(pixels, border, constant_values=255)
    return Image.fromarray(pixels.repeat(scale, axis=0).repeat(scale, axis=1), mode='L')


def matrix_to_svg(grid: np.ndarray, border: int = QUIET_ZONE, module_size: int = 10) -> str:
    """0/1-Matrix → SVG (ein Pfad, verlustfrei skalierbar)"""
    grid = np.asarray(grid)
    size = grid.shape[0] + 2 * border
    path = "".join(f"M{c + border},{r + border}h1v1h-1z" for r, c in zip(*np.nonzero(grid == 1)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'width="{size * module_size}" height="{size * module_size}" shape-rendering="crispEdges">'
            f'<rect width="100%" height="100%" fill="#fff"/><path d="{path}" fill="#000"/></svg>')


def save_matrix(grid: np.ndarray, path: str, scale: int = 12):
    """Speichert als SVG (Endung .svg) oder Rasterbild (PNG, JPG, ...)"""
    if Path(path).suffix.lower() == '.svg':
        Path(path).write_text(matrix_to_svg(grid), encoding='utf-8')
    else:
        matrix_to_image(grid, scale).save(path)
