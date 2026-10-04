"""
Eigener Decoder (core/decoder.py) - Ersatz für pyzbar im Validator

Anlass: zbar 0.10 (Windows-Wheels von pyzbar) bricht bei Symbolen mit Structured-Append-Kopf
"Teil 2 von 3" den Prozess per Assertion ab (qrdectxt.c:405). Solche Symbole entstehen bei
mehrdeutigen Rekonstruktionen (z.B. halber Code unbekannt) als gültige Zufallskandidaten.
"""

import random
import subprocess
import sys

import numpy as np
import pytest
from reedsolo import RSCodec

from tools.qr_reconstruction.core.codewords import interleave, render_matrix
from tools.qr_reconstruction.core.decoder import decode_grid
from tools.qr_reconstruction.core.reconstructor import Reconstructor
from tools.qr_reconstruction.core.spec import block_layout, format_info_positions
from tools.qr_reconstruction.core.validator import QRValidator
from tests.helpers import EC_LEVELS, make_known_matrix, make_qr_grid
from tests.test_data_decoder import Bits

URL = 'https://www.github.com/'


def structured_append_symbol(index=1, total=3, text=b'Teil zwei'):
    """Gültiges v2-M-Symbol mit Structured-Append-Kopf (genau der Fall, der zbar abstürzen lässt)"""
    (data_len, nsym), = block_layout(2, 'M')
    bits = Bits().add(0b0011, 4).add(index, 4).add(total - 1, 4).add(0x5A, 8)
    bits.add(0b0100, 4).add(len(text), 8)
    for b in text:
        bits.add(b, 8)
    data = bits.add(0, 4).to_bytes(data_len)
    block = list(RSCodec(nsym).encode(data))
    return render_matrix(2, 'M', 0, interleave([block], 2, 'M'))


def test_structured_append_symbol_is_decoded_without_crash():
    symbol = decode_grid(structured_append_symbol())
    assert symbol.text == 'Teil zwei'
    assert 'structured_append' in symbol.modes


def test_validator_handles_structured_append_symbol():
    from tools.qr_reconstruction.core.qr_matrix import QRMatrix
    matrix = QRMatrix(25)
    matrix.grid = structured_append_symbol().astype(int)
    matrix.locked[:] = True
    result = QRValidator().validate(matrix)
    assert result.decoded_data == 'Teil zwei'


def test_app_does_not_load_pyzbar():
    """Validator, Reconstructor und Bruteforce dürfen zbar nicht mehr laden"""
    code = (
        "import sys, random\n"
        "sys.path.insert(0, '.')\n"
        "from tests.helpers import make_known_matrix, damage\n"
        "from tools.qr_reconstruction.core.reconstructor import Reconstructor\n"
        "from tools.qr_reconstruction.core.bruteforce import BruteforceEngine\n"
        "m = make_known_matrix('https://www.github.com/', ec='M')\n"
        "cells = [(r, c) for r in range(25) for c in range(25) if not m.fixed[r, c]]\n"
        "d = damage(m, random.Random(1).sample(cells, len(cells) // 2))\n"
        "Reconstructor(d).run(max_time=20, max_candidates=256)\n"
        "BruteforceEngine(damage(m, cells[:6]), Reconstructor(d).validator).run(parallel=False)\n"
        "print('pyzbar' in sys.modules)\n"
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith('False')


@pytest.mark.parametrize('version', [1, 2, 7, 15, 27, 40])
@pytest.mark.parametrize('level', list(EC_LEVELS))
def test_decodes_clean_codes(version, level):
    text = f'V{version}{level} ' * (2 + version // 4)
    symbol = decode_grid(make_qr_grid(text, version=version, ec=level))
    assert symbol.text == text and symbol.ec_level == level and symbol.corrected_errors == 0


def test_utf8_is_read_correctly():
    """zbar rät die Kodierung und liest UTF-8 teils als Shift-JIS - der eigene Decoder nicht"""
    text = 'Grüße aus München, 東京'
    assert decode_grid(make_qr_grid(text)).text == text


def test_garbage_and_wrong_sizes():
    rng = np.random.default_rng(0)
    assert decode_grid(rng.integers(0, 2, (25, 25))) is None
    assert decode_grid(np.zeros((24, 24), dtype=int)) is None


def test_at_least_as_tolerant_as_zbar():
    """Beschädigte Daten und Format-Info: alles, was zbar liest, liest auch der eigene Decoder - nie etwas Falsches"""
    pyzbar = pytest.importorskip("pyzbar.pyzbar")
    rng = random.Random(7)
    only_zbar = wrong = 0
    for text in (URL, 'HELLO WORLD 2024'):
        for level in 'LMQH':
            clean = make_qr_grid(text, ec=level)
            n = clean.shape[0]
            format_cells = [p for copy in format_info_positions(n) for p in copy]
            for _ in range(30):
                grid = clean.copy()
                for _ in range(rng.randint(0, n * n // 12)):
                    r, c = rng.randrange(n), rng.randrange(n)
                    grid[r, c] ^= 1
                for r, c in rng.sample(format_cells, rng.randint(0, 10)):
                    grid[r, c] ^= 1
                image = np.pad(((1 - grid) * 255).astype(np.uint8), 4, constant_values=255)
                zbar = pyzbar.decode(image.repeat(4, 0).repeat(4, 1))
                own = decode_grid(grid)
                only_zbar += bool(zbar) and own is None
                wrong += own is not None and own.text != text
    assert only_zbar == 0 and wrong == 0


def test_half_unknown_code_produces_no_crash_and_confirmed_results():
    """Nutzerszenario: halber Code unbekannt, Modus 'accurate' - lief unter Windows in den zbar-Absturz"""
    original = make_known_matrix(URL, ec='Q')
    damaged = original.clone()
    for r in range(original.size // 2):
        for c in range(original.size):
            if not original.fixed[r, c]:
                damaged.locked[r, c] = False
    results = Reconstructor(damaged).run(max_time=60, max_candidates=8192)
    assert results
    assert all(r.decoder_confirmed for r in results)
