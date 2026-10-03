import numpy as np
import pytest

from tools.qr_reconstruction.core.qr_matrix import QRMatrix, CellState, QR_VERSIONS
from tests.helpers import make_qr_grid


@pytest.mark.parametrize('version', [1, 2, 6, 7, 14, 25, 40])
def test_fixed_patterns_match_real_code(version):
    matrix = QRMatrix(QR_VERSIONS[version][0])
    real = make_qr_grid('hallo', version=version)
    assert matrix.fixed.any()
    np.testing.assert_array_equal(matrix.grid[matrix.fixed], real[matrix.fixed])


@pytest.mark.parametrize('version', [2, 7, 14])
def test_alignment_dark_module_and_version_info_are_fixed(version):
    size = QR_VERSIONS[version][0]
    matrix = QRMatrix(size)
    center = QR_VERSIONS[version][1][-1]
    assert matrix._is_fixed_pattern(center, center)          # Alignment-Pattern
    assert matrix._is_fixed_pattern(4 * version + 9, 8)      # Dark Module
    if version >= 7:
        assert matrix._is_fixed_pattern(0, size - 11)        # Version-Info oben rechts
        assert matrix._is_fixed_pattern(size - 11, 0)        # Version-Info unten links

    matrix.unlock_cell(center, center)
    assert matrix.locked[center, center]
    assert (center, center) not in matrix.get_unknown_cells()


def test_format_info_stays_unknown():
    matrix = QRMatrix(21)
    assert not matrix._is_fixed_pattern(8, 0)
    assert (8, 0) in matrix.get_unknown_cells()


def test_version_7_has_no_unknown_version_info():
    matrix = QRMatrix(45)
    unknown = set(matrix.get_unknown_cells())
    assert not any(r < 6 and 45 - 11 <= c < 45 - 8 for r, c in unknown)


def test_clone_and_reset_keep_fixed_mask():
    matrix = QRMatrix(25)
    clone = matrix.clone()
    np.testing.assert_array_equal(clone.fixed, matrix.fixed)
    clone.fixed[0, 0] = False
    assert matrix.fixed[0, 0]

    fixed_before = matrix.fixed.copy()
    matrix.set_cell(10, 10, CellState.BLACK)
    matrix.reset()
    np.testing.assert_array_equal(matrix.fixed, fixed_before)
    assert not matrix.locked[10, 10]
