"""Synthetische Testbilder für den Bild-Import: sauber, "Foto" (Perspektive, Licht, Rauschen), Flecken"""

import cv2
import numpy as np
import qrcode

from tests.helpers import EC_LEVELS


def code_image(text, version=None, ec='M', box=12, border=4):
    """(BGR-Bild, 0/1-Matrix ohne Rand)"""
    qr = qrcode.QRCode(version=version, error_correction=EC_LEVELS[ec], box_size=box, border=border)
    qr.add_data(text)
    qr.make(fit=version is None)
    gray = np.array(qr.make_image(fill_color="black", back_color="white").convert('L'))
    full = np.array(qr.get_matrix(), dtype=int)
    matrix = full[border:len(full) - border, border:len(full) - border]
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), matrix


def blob(image, cx, cy, radius, color=(30, 30, 30)):
    out = image.copy()
    cv2.circle(out, (int(cx), int(cy)), int(radius), color, -1)
    return out


def photo(image, seed=0):
    """Perspektivisch verzerrt, ungleichmäßig beleuchtet, verrauscht und leicht unscharf"""
    rng = np.random.default_rng(seed)
    h, w = image.shape[:2]
    pad = 80
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), 200, np.uint8)
    canvas[pad:pad + h, pad:pad + w] = image
    H, W = canvas.shape[:2]
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = np.float32([[40, 25], [W - 15, 60], [W - 50, H - 20], [10, H - 45]])
    warped = cv2.warpPerspective(canvas, cv2.getPerspectiveTransform(src, dst), (W, H),
                                 borderValue=(180, 180, 180))
    light = np.linspace(0.65, 1.1, W)[None, :, None]
    noisy = warped * light + rng.normal(0, 12, warped.shape)
    return cv2.GaussianBlur(np.clip(noisy, 0, 255).astype(np.uint8), (5, 5), 1.2)
