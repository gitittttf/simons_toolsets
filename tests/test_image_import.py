import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from tools.qr_reconstruction.core import image_import  # noqa: E402
from tools.qr_reconstruction.core.analysis import VERDICT_UNIQUE, analyze_solvability  # noqa: E402
from tools.qr_reconstruction.core.reconstructor import Reconstructor  # noqa: E402
from tests.image_helpers import blob, code_image, photo  # noqa: E402

URL = 'https://www.github.com/'


def wrong_known(result, truth):
    matrix = result.to_matrix()
    return int(((result.black != (truth == 1)) & matrix.locked & ~matrix.fixed).sum())


@pytest.mark.parametrize('distort', ['sauber', 'foto', 'gedreht'])
def test_reads_code_exactly(distort):
    image, truth = code_image(URL)
    if distort == 'foto':
        image = photo(image)
    elif distort == 'gedreht':
        image = np.ascontiguousarray(np.rot90(image))   # Orientierung wird beim Abtasten bestimmt
    result = image_import.sample_grid(image, image_import.detect_corners(image))
    assert result.size == 25
    assert result.pattern_score == pytest.approx(1.0)
    assert wrong_known(result, truth) == 0
    assert Reconstructor(result.to_matrix()).run(max_time=10)[0].decoded_data == URL


@pytest.mark.parametrize('version,box', [(7, 6), (15, 6), (25, 6)])
def test_larger_versions_as_photo(version, box):
    """Bei Perspektive schätzt OpenCV die Ecke ohne Finder-Pattern ungenau - die Verfeinerung muss das ausgleichen"""
    text = f'Version {version} ' * version
    image, truth = code_image(text, version=version, box=box)
    image = photo(image)
    result = image_import.sample_grid(image, image_import.detect_corners(image))
    assert result.size == truth.shape[0]
    assert wrong_known(result, truth) == 0
    assert Reconstructor(result.to_matrix()).run(max_time=30)[0].decoded_data == text


def test_rough_manual_corners_on_damaged_finder():
    """Fleck auf einem Finder-Pattern: OpenCV findet nichts, grob gesetzte Ecken reichen trotzdem"""
    image, truth = code_image(URL)                     # Modul = 12 px, Code von 48 bis 348
    damaged = blob(image, 95, 95, 45)
    assert image_import.detect_corners(damaged) is None
    rough = np.float32([[55, 41], [340, 57], [356, 341], [40, 352]])   # bis zu ~1 Modul daneben
    result = image_import.sample_grid(damaged, rough)
    assert result.size == 25
    assert Reconstructor(result.to_matrix()).run(max_time=10)[0].decoded_data == URL


def test_blob_marked_by_user_is_solvable():
    """Flecken erkennt der Import nicht vollständig - nach Markieren durch den Nutzer ist der Code lösbar"""
    image, truth = code_image(URL)
    damaged = blob(image, 260, 280, 70)
    result = image_import.sample_grid(damaged, image_import.detect_corners(damaged))
    matrix = result.to_matrix()
    # Nutzer markiert alle Module, die der Fleck berührt (Modul = 12 px, Rand 48 px)
    rows, cols = np.indices((25, 25))
    cy, cx = (rows + 0.5) * 12 + 48, (cols + 0.5) * 12 + 48
    touched = (cx - 260) ** 2 + (cy - 280) ** 2 <= (70 + 9) ** 2
    matrix.locked[touched & ~matrix.fixed] = False
    assert analyze_solvability(matrix).verdict == VERDICT_UNIQUE
    assert Reconstructor(matrix).run(max_time=10)[0].decoded_data == URL


def test_to_matrix_keeps_fixed_patterns_and_marks_unsure():
    image, _ = code_image(URL)
    result = image_import.sample_grid(image, image_import.detect_corners(image))
    result.unsure[12, 12] = True
    matrix = result.to_matrix()
    assert matrix.fixed[0, 0] and matrix.locked[0, 0]
    assert not matrix.locked[12, 12]
    assert result.warped.shape == (image_import.WARP_SIZE, image_import.WARP_SIZE)


def test_solid_areas():
    black = np.zeros((25, 25), dtype=bool)
    fixed = np.zeros((25, 25), dtype=bool)
    black[10:15, 10:15] = True
    found = image_import.solid_areas(black, fixed, k=4)
    assert found[10:15, 10:15].all()
    assert found.sum() > 25                      # auch die große weiße Fläche drumherum


def test_load_image_errors(tmp_path):
    bad = tmp_path / "kein_bild.png"
    bad.write_bytes(b"das ist kein Bild")
    with pytest.raises(image_import.ImageImportError):
        image_import.load_image(str(bad))
    with pytest.raises(image_import.ImageImportError):
        image_import.load_image(str(tmp_path / "fehlt.png"))


def test_load_image_with_umlaut_path(tmp_path):
    image, _ = code_image(URL)
    path = tmp_path / "größe_ü.png"
    ok, encoded = cv2.imencode(".png", image)
    path.write_bytes(encoded.tobytes())
    assert image_import.load_image(str(path)).shape == image.shape
