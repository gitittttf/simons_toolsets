import random
import threading

import numpy as np
import pytest

from tools.qr_reconstruction.core import codewords as cw
from tools.qr_reconstruction.core.reconstructor import Reconstructor, rank_formats
from tools.qr_reconstruction.core.spec import block_layout, format_info_positions
from tools.qr_reconstruction.core.validator import QRValidator
from tests.helpers import damage, make_known_matrix

TEXT = 'https://www.github.com/simon'


@pytest.fixture(scope='module')
def validator():
    return QRValidator()


def data_cells(matrix):
    return [(r, c) for r in range(matrix.size) for c in range(matrix.size)
            if not matrix._is_fixed_pattern(r, c)]


def unknown_codewords_per_block(matrix, level, mask):
    reading = cw.read_codewords((matrix.grid == 1).astype(np.uint8), matrix.locked, matrix.version, mask)
    masks = cw.deinterleave(reading.known_masks, matrix.version, level)
    return [sum(m != 0xFF for m in block) for block in masks]


@pytest.mark.parametrize('version', [1, 2, 3, 4, 5])
@pytest.mark.parametrize('level', ['L', 'M', 'Q', 'H'])
@pytest.mark.parametrize('fraction', [0.05, 0.15, 0.3])
def test_reconstructs_when_within_capacity(validator, version, level, fraction):
    original = make_known_matrix(TEXT[:4 + version], version=version, ec=level, mask=3)
    cells = data_cells(original)
    damaged = damage(original, random.Random(version * 100 + int(fraction * 100)).sample(
        cells, int(len(cells) * fraction)))
    nsym = block_layout(version, level)[0][1]
    within = all(n <= nsym for n in unknown_codewords_per_block(damaged, level, 3))

    results = Reconstructor(damaged, validator).run(max_time=30)

    if within:
        # Erasures innerhalb der Kapazität: eindeutige, korrekte Lösung mit voller Confidence
        assert results, 'keine Lösung gefunden'
        top = results[0]
        assert top.decoded_data == TEXT[:4 + version]
        assert top.method == 'rs' and top.is_valid and top.ambiguous_bits == 0
        assert top.decoder_confirmed
        assert top.confidence == pytest.approx(100)
        np.testing.assert_array_equal(top.matrix, original.grid)
    elif results:
        # Jenseits der Erasure-Kapazität: entweder bitweise doch eindeutig, oder als mehrdeutig markiert
        top = results[0]
        assert top.decoded_data == TEXT[:4 + version] or top.ambiguous_bits > 0


def test_twenty_percent_damage_github(validator):
    """Szenario aus quick_test.py: mit Pixel-Bruteforce aussichtslos"""
    original = make_known_matrix('https://www.github.com/')
    cells = data_cells(original)
    damaged = damage(original, random.Random(0).sample(cells, len(cells) // 5))
    assert len(damaged.get_unknown_cells()) > 70
    results = Reconstructor(damaged, validator).run(max_time=30)
    assert results[0].decoded_data == 'https://www.github.com/'


@pytest.mark.parametrize('version,level', [(7, 'M'), (10, 'Q'), (15, 'H'), (25, 'L')])
def test_multi_block_versions(validator, version, level):
    text = ('Mehrere Blöcke und Version-Info ' * version)[:version * 8]
    original = make_known_matrix(text, version=version, ec=level)
    cells = data_cells(original)
    damaged = damage(original, random.Random(version).sample(cells, len(cells) // 10))
    results = Reconstructor(damaged, validator).run(max_time=60)
    assert results[0].decoded_data == text
    assert results[0].ambiguous_bits == 0


def test_completely_unknown_format_info(validator):
    original = make_known_matrix(TEXT, ec='Q', mask=6)
    damaged = damage(original, [p for copy in format_info_positions(original.size) for p in copy])
    assert all(f.known_bits == 0 for f in rank_formats(damaged))
    results = Reconstructor(damaged, validator).run(max_time=30)
    assert results[0].decoded_data == TEXT
    assert results[0].error_correction_level == 'Q' and results[0].mask_pattern == 6


def test_wrong_format_bits_are_tolerated(validator):
    original = make_known_matrix(TEXT, ec='M', mask=2)
    damaged = original.clone()
    for r, c in format_info_positions(original.size)[0][:2]:
        damaged.grid[r, c] ^= 1  # bekannt, aber falsch abgemalt
    results = Reconstructor(damaged, validator).run(max_time=30)
    assert results[0].decoded_data == TEXT
    assert results[0].confidence < 100


def test_wrongly_painted_data_pixels_are_corrected(validator):
    original = make_known_matrix(TEXT, version=4, ec='H', mask=1)
    damaged = original.clone()
    rows, cols = cw.data_module_order(4)
    for i in (0, 40, 200):  # drei verschiedene Codewörter, als bekannt markiert, aber falsch
        damaged.grid[rows[i], cols[i]] ^= 1
    results = Reconstructor(damaged, validator).run(max_time=30)
    assert results[0].decoded_data == TEXT
    assert results[0].corrected_errors == 3
    np.testing.assert_array_equal(results[0].matrix, original.grid)


def test_ambiguous_damage_is_flagged(validator):
    original = make_known_matrix('https://www.github.com/', ec='M')
    cells = data_cells(original)
    damaged = damage(original, random.Random(1).sample(cells, len(cells) // 2))
    results = Reconstructor(damaged, validator).run(max_time=30, max_candidates=4096)
    assert results
    assert all(r.ambiguous_bits > 0 for r in results)
    assert results[0].confidence <= 50


def test_stop(validator):
    original = make_known_matrix('https://www.github.com/', ec='M')
    cells = data_cells(original)
    damaged = damage(original, random.Random(1).sample(cells, len(cells) // 2))
    reconstructor = Reconstructor(damaged, validator)
    threading.Timer(0.3, reconstructor.stop).start()
    reconstructor.run(max_time=60)
    assert reconstructor.stop_requested
    assert reconstructor.get_stats()['elapsed'] < 10


def test_callbacks_and_stats(validator):
    original = make_known_matrix(TEXT)
    damaged = damage(original, data_cells(original)[:30])
    progress, found = [], []
    reconstructor = Reconstructor(damaged, validator)
    reconstructor.set_progress_callback(lambda t, v, total: progress.append((t, v, total)))
    reconstructor.set_result_callback(found.append)
    results = reconstructor.run()
    assert [r.decoded_data for r in found] == [r.decoded_data for r in results] == [TEXT]
    assert progress and progress[-1][2] == 32
    assert reconstructor.get_stats()['valid'] == 1
