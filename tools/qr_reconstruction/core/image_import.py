"""
QR-Code aus einem Bild (Foto/Screenshot) in eine QRMatrix übernehmen

Ablauf:
  1. Ecken des Codes finden (OpenCV) - oder vom Nutzer setzen lassen; bei beschädigten Codes
     (z.B. Fleck auf einem Finder-Pattern) findet OpenCV oft nichts
  2. Perspektive entzerren und Beleuchtung ausgleichen
  3. Für jede Orientierung und jede Version das Raster abtasten; gewählt wird die Kombination,
     bei der die festen Muster (Finder, Timing, Alignment, Version-Info) am besten passen
  4. Unsichere Module (Grauwert nahe der Schwelle) und große einfarbige Flächen (typisch für Flecken
     oder Reflexe, in echten QR-Daten selten) werden als unbekannt markiert

Flecken, die Module vollständig überdecken, sind im Bild nicht von echten Modulen zu unterscheiden -
die muss der Nutzer im Editor als unbekannt markieren (dafür gibt es das entzerrte Foto als Hintergrund).

OpenCV wird erst beim Aufruf importiert, damit das Tool auch ohne OpenCV läuft.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .qr_matrix import QRMatrix, VALID_QR_SIZES

# Auflösung des entzerrten Bilds (Pixel je Kante), unabhängig von der Version
WARP_SIZE = 1200
# Abtastraster: Pixel je Modul beim Abtasten
SAMPLE_PX = 10
# Modul gilt als unsicher, wenn sein Grauwert näher als dieser Anteil an der Schwelle liegt
# (1.0 = typischer Abstand einer Klasse zur Schwelle)
UNSURE_CONTRAST = 0.35
# Einfarbige Flächen ab dieser Kantenlänge (in Modulen) gelten als verdächtig
SOLID_AREA = 4


class ImageImportError(Exception):
    pass


@dataclass
class ImportResult:
    size: int
    black: np.ndarray          # bool [n, n]: Modul ist schwarz
    unsure: np.ndarray         # bool [n, n]: als unbekannt vorschlagen
    pattern_score: float       # Anteil passender Module der festen Muster (1.0 = perfekt)
    corners: np.ndarray        # 4×2, Reihenfolge oben-links, oben-rechts, unten-rechts, unten-links
    warped: np.ndarray         # entzerrtes Graubild (uint8) des Codes, für den Editor-Hintergrund

    def to_matrix(self) -> QRMatrix:
        """QRMatrix mit festen Mustern aus der Spezifikation und abgetasteten Datenmodulen"""
        matrix = QRMatrix(self.size)
        data = ~matrix.fixed
        matrix.grid[data] = self.black[data].astype(int)
        matrix.locked[data] = ~self.unsure[data]
        return matrix


def _cv2():
    try:
        import cv2
    except ImportError as e:
        raise ImageImportError(
            "Für den Bild-Import wird OpenCV benötigt: pip install opencv-python") from e
    return cv2


def load_image(path: str) -> np.ndarray:
    """Lädt ein Bild als BGR-Array (funktioniert auch mit Umlauten im Pfad unter Windows)"""
    cv2 = _cv2()
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as e:
        raise ImageImportError(f"Datei konnte nicht gelesen werden: {e}") from e
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageImportError("Unbekanntes oder beschädigtes Bildformat")
    return image


def detect_corners(image: np.ndarray) -> Optional[np.ndarray]:
    """Ecken des QR-Codes (4×2) oder None, wenn OpenCV keinen Code findet"""
    cv2 = _cv2()
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, 'QRCodeDetectorAruco'):
        detectors.append(cv2.QRCodeDetectorAruco())
    for detector in detectors:
        try:
            found, points = detector.detect(image)
        except cv2.error:
            continue
        if found and points is not None:
            return np.asarray(points, dtype=np.float32).reshape(4, 2)
    return None


def default_corners(image: np.ndarray) -> np.ndarray:
    """Startwerte für die manuelle Eckenauswahl: zentriertes Quadrat"""
    h, w = image.shape[:2]
    side = min(h, w) * 0.6
    x0, y0 = (w - side) / 2, (h - side) / 2
    return np.array([[x0, y0], [x0 + side, y0], [x0 + side, y0 + side], [x0, y0 + side]], dtype=np.float32)


def _warp(gray: np.ndarray, corners: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    target = np.array([[0, 0], [WARP_SIZE, 0], [WARP_SIZE, WARP_SIZE], [0, WARP_SIZE]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(np.array(corners, dtype=np.float32), target)
    return cv2.warpPerspective(gray, transform, (WARP_SIZE, WARP_SIZE), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)


def _module_values(flat: np.ndarray, n: int) -> np.ndarray:
    """Mittlerer Grauwert der inneren 40 % jedes Moduls (Ränder sind durch Unschärfe gemischt)"""
    cv2 = _cv2()
    grid = cv2.resize(flat, (n * SAMPLE_PX, n * SAMPLE_PX), interpolation=cv2.INTER_AREA)
    inner = slice(3, SAMPLE_PX - 3)
    return grid.reshape(n, SAMPLE_PX, n, SAMPLE_PX)[:, inner, :, inner].mean(axis=(1, 3))


def _classify(values: np.ndarray):
    """Schwarz/weiß trennen: Otsu, dann Schwelle genau zwischen die Mittelwerte beider Klassen"""
    cv2 = _cv2()
    span = max(1e-6, float(np.ptp(values)))
    norm = (values - values.min()) / span * 255
    otsu, _ = cv2.threshold(norm.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = norm[norm <= otsu]
    light = norm[norm > otsu]
    dark_mean = dark.mean() if dark.size else 0.0
    light_mean = light.mean() if light.size else 255.0
    threshold = (dark_mean + light_mean) / 2
    half = max(1.0, (light_mean - dark_mean) / 2)
    return norm < threshold, np.abs(norm - threshold) / half


def solid_areas(black: np.ndarray, fixed: np.ndarray, k: int = SOLID_AREA) -> np.ndarray:
    """Module in einfarbigen k×k-Flächen außerhalb der festen Muster"""
    n = black.shape[0]
    out = np.zeros_like(black, dtype=bool)
    if n < k:
        return out
    for value in (True, False):
        same = ((black == value) & ~fixed).astype(np.int32)
        # Summierte Fläche: k×k-Fenster komplett gleichfarbig, wenn Summe == k*k
        integral = np.pad(same.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        window = integral[k:, k:] - integral[:-k, k:] - integral[k:, :-k] + integral[:-k, :-k]
        for r, c in zip(*np.nonzero(window == k * k)):
            out[r:r + k, c:c + k] = True
    return out


def _pattern_correlation(gray: np.ndarray, corners: np.ndarray, reference: QRMatrix) -> float:
    """Korrelation zwischen abgetasteten Modulen und den festen Mustern (glatt, gut zum Optimieren)"""
    cv2 = _cv2()
    n = reference.size
    side = n * SAMPLE_PX
    target = np.array([[0, 0], [side, 0], [side, side], [0, side]], dtype=np.float32)
    flat = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(np.array(corners, dtype=np.float32), target), (side, side),
                               flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    inner = slice(3, SAMPLE_PX - 3)
    values = flat.reshape(n, SAMPLE_PX, n, SAMPLE_PX)[:, inner, :, inner].mean(axis=(1, 3))
    sampled = values[reference.fixed]
    expected = (reference.grid[reference.fixed] != 1).astype(np.float32)  # weiß = 1
    if sampled.std() < 1e-6:
        return -1.0
    return float(np.corrcoef(sampled, expected)[0, 1])


def refine_corners(gray: np.ndarray, corners: np.ndarray, reference: QRMatrix) -> np.ndarray:
    """
    Verschiebt jede Ecke schrittweise, solange die festen Muster besser passen.
    Nötig, weil OpenCV bei Perspektive die Ecke ohne Finder-Pattern (unten rechts) oft um mehrere
    Module falsch schätzt - und manuell gesetzte Ecken selten pixelgenau sind.
    """
    corners = np.array(corners, dtype=np.float32).copy()
    edge = np.linalg.norm(corners[1] - corners[0]) + np.linalg.norm(corners[3] - corners[0])
    step = max(1.0, edge / 2 / reference.size)  # Startschritt ≈ ein Modul
    best = _pattern_correlation(gray, corners, reference)
    directions = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    while step >= 0.5:
        improved = True
        while improved:
            improved = False
            for i in range(4):
                for dx, dy in directions:
                    candidate = corners.copy()
                    candidate[i] += (dx * step, dy * step)
                    score = _pattern_correlation(gray, candidate, reference)
                    if score > best + 1e-4:
                        best, corners, improved = score, candidate, True
        step /= 2
    return corners


def sample_grid(image: np.ndarray, corners: np.ndarray, sizes: Optional[List[int]] = None,
                refine: bool = True) -> ImportResult:
    """
    Tastet den Code innerhalb der Ecken ab.

    Args:
        image: BGR- oder Graubild
        corners: 4×2 Ecken in beliebiger Drehung, aber im Umlaufsinn (wie von OpenCV geliefert)
        sizes: zu prüfende Größen (Standard: alle 40 Versionen)
        refine: Ecken anhand der festen Muster nachjustieren (für die besten Kandidaten)
    """
    cv2 = _cv2()
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.float32)
    corners = np.array(corners, dtype=np.float32).reshape(4, 2)
    sizes = sizes or VALID_QR_SIZES
    fixed_masks = {n: QRMatrix(n) for n in sizes}

    def evaluate(rotated, candidate_sizes):
        flat = _warp(gray, rotated)
        # Beleuchtung ausgleichen: durch stark weichgezeichneten Hintergrund teilen
        background = cv2.GaussianBlur(flat, (0, 0), WARP_SIZE / 30)
        normalized = flat / np.maximum(background, 1.0)
        for n in candidate_sizes:
            black, contrast = _classify(_module_values(normalized, n))
            reference = fixed_masks[n]
            score = float((black[reference.fixed] == (reference.grid[reference.fixed] == 1)).mean())
            yield (score, n, black, contrast, rotated, flat)

    # 1. Grob: jede Orientierung × jede Größe mit den gegebenen Ecken
    candidates = [c for rotation in range(4) for c in evaluate(np.roll(corners, rotation, axis=0), sizes)]
    if not candidates:
        raise ImageImportError("Keine Größe zum Prüfen angegeben")
    candidates.sort(key=lambda c: c[0], reverse=True)
    best = candidates[0]

    # 2. Fein: Ecken der besten Kandidaten nachjustieren und neu bewerten
    if refine and best[0] < 0.999:
        for _, n, _, _, rotated, _ in candidates[:3]:
            refined = refine_corners(gray, rotated, fixed_masks[n])
            for result in evaluate(refined, [n]):
                if result[0] > best[0]:
                    best = result

    score, n, black, contrast, rotated, flat = best
    fixed = fixed_masks[n].fixed
    unsure = (contrast < UNSURE_CONTRAST) | solid_areas(black, fixed)
    unsure &= ~fixed
    warped = np.clip(flat, 0, 255).astype(np.uint8)
    return ImportResult(size=n, black=black, unsure=unsure, pattern_score=score,
                        corners=rotated, warped=warped)
