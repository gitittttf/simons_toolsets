import numpy as np
import pytest
import qrcode.util

from tools.qr_reconstruction.core import codewords as cw
from tools.qr_reconstruction.core.spec import num_raw_data_modules, block_layout
from tests.helpers import EC_LEVELS
import qrcode


def make(version, level, mask, text):
    qr = qrcode.QRCode(version=version, error_correction=EC_LEVELS[level], mask_pattern=mask, border=0)
    qr.add_data(text)
    qr.make(fit=False)
    grid = np.array(qr.get_matrix(), dtype=np.uint8)
    reference = qrcode.util.create_data(version, EC_LEVELS[level], qr.data_list)
    return grid, reference


@pytest.mark.parametrize('version', [1, 2, 6, 7, 10, 14, 21, 27, 40])
def test_data_module_count(version):
    rows, _ = cw.data_module_order(version)
    assert len(rows) == num_raw_data_modules(version)
    assert int((~cw.function_mask(version)).sum()) == num_raw_data_modules(version)


@pytest.mark.parametrize('version', [1, 3, 7, 13, 27, 40])
@pytest.mark.parametrize('level', list(EC_LEVELS))
@pytest.mark.parametrize('mask', [0, 4, 7])
def test_read_and_render_match_reference(version, level, mask):
    grid, reference = make(version, level, mask, f'V{version}{level}')
    reading = cw.read_codewords(grid, np.ones_like(grid, dtype=bool), version, mask)
    assert reading.values == reference
    assert reading.num_unknown_codewords == 0
    np.testing.assert_array_equal(cw.render_matrix(version, level, mask, reference), grid)


def test_unknown_modules_mark_codewords():
    grid, reference = make(2, 'M', 3, 'hello')
    known = np.ones_like(grid, dtype=bool)
    rows, cols = cw.data_module_order(2)
    known[rows[:3], cols[:3]] = False          # erste 3 Bits von Codewort 0
    known[rows[8:16], cols[8:16]] = False      # Codewort 1 komplett
    reading = cw.read_codewords(grid, known, 2, 3)
    assert reading.known_masks[0] == 0b00011111
    assert reading.known_masks[1] == 0
    assert reading.num_unknown_codewords == 2
    assert reading.values[0] == reference[0] & 0b00011111


@pytest.mark.parametrize('version,level', [(5, 'Q'), (13, 'H'), (40, 'L')])
def test_interleave_roundtrip(version, level):
    _, reference = make(version, level, 0, 'x')
    blocks = cw.deinterleave(reference, version, level)
    assert [len(b) for b in blocks] == [d + e for d, e in block_layout(version, level)]
    assert cw.interleave(blocks, version, level) == reference
