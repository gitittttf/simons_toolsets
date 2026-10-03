import random

import numpy as np
import pytest
import qrcode.util

from tools.qr_reconstruction.core import spec
from tests.helpers import EC_LEVELS, make_qr_grid


@pytest.mark.parametrize('level', list(EC_LEVELS))
@pytest.mark.parametrize('mask', range(8))
def test_format_bits_match_reference(level, mask):
    assert spec.format_bits(level, mask) == qrcode.util.BCH_type_info((EC_LEVELS[level] << 3) | mask)


@pytest.mark.parametrize('version', range(7, 41))
def test_version_bits_match_reference(version):
    assert spec.version_bits(version) == qrcode.util.BCH_type_number(version)


def test_exactly_32_valid_formats():
    assert len(spec.VALID_FORMATS) == 32


@pytest.mark.parametrize('version', [1, 2, 7, 15])
@pytest.mark.parametrize('level', list(EC_LEVELS))
def test_format_positions_read_real_codes(version, level):
    grid = make_qr_grid('x', version=version, ec=level, mask=5)
    for positions in spec.format_info_positions(grid.shape[0]):
        assert spec.decode_format_bits(spec.read_format_bits(grid, positions)) == (level, 5, 0)


@pytest.mark.parametrize('version', [7, 20, 40])
def test_version_positions_read_real_codes(version):
    grid = make_qr_grid('x', version=version)
    bits = spec.version_bits(version)
    for block in spec.version_info_positions(grid.shape[0]):
        assert [grid[r, c] for r, c in block] == [(bits >> i) & 1 for i in range(18)]


def test_decode_format_corrects_up_to_three_errors():
    rng = random.Random(0)
    for bits, (level, mask) in spec.VALID_FORMATS.items():
        for errors in range(4):
            corrupted = bits
            for pos in rng.sample(range(15), errors):
                corrupted ^= 1 << pos
            assert spec.decode_format_bits(corrupted) == (level, mask, errors)
