import random

import numpy as np
import pytest
import pyzbar.pyzbar as pyzbar

from tools.qr_reconstruction.core.validator import QRValidator
from tools.qr_reconstruction.core import spec
from tests.helpers import make_known_matrix

TEXTS = ['https://www.github.com/', 'HELLO WORLD', 'hallo welt test 123', '0123456789']


@pytest.fixture(scope='module')
def validator():
    return QRValidator()


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('ec', ['L', 'H'])
def test_clean_codes_decode(validator, text, ec):
    result = validator.validate(make_known_matrix(text, ec=ec))
    assert result.decoded_data == text
    assert result.is_valid


def test_validator_finds_everything_zbar_reads(validator):
    """
    Regressionstest: Der Validator liest alles, was zbar lesen kann (und manches mehr).
    (Ein Early-Abort über die Format-Info wäre falsch - zbar toleriert dort mehr als 3 Bitfehler.)
    """
    rng = random.Random(42)
    clean = make_known_matrix('https://www.github.com/', ec='L')
    format_cells = [cell for copy in spec.format_info_positions(clean.size) for cell in copy]
    decodable = 0
    for _ in range(150):
        matrix = clean.clone()
        for r, c in rng.sample(format_cells, rng.randint(3, 12)):
            matrix.grid[r, c] ^= 1
        img = np.pad(((1 - matrix.to_binary_grid()) * 255).astype(np.uint8), 4, constant_values=255)
        direct = pyzbar.decode(img.repeat(4, 0).repeat(4, 1))
        expected = direct[0].data.decode('utf-8') if direct else None
        decoded = validator.validate(matrix).decoded_data
        if expected is not None:
            assert decoded == expected
        else:
            assert decoded in (None, 'https://www.github.com/')  # liest mehr als zbar, aber nie etwas Falsches
        decodable += expected is not None
    assert decodable > 20
