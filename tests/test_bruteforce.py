import random
import threading

import pytest

from tools.qr_reconstruction.core.bruteforce import BruteforceEngine, CandidateSpace, PARALLEL_THRESHOLD
from tools.qr_reconstruction.core.validator import QRValidator
from tests.helpers import make_known_matrix, damage

TEXT = 'https://www.github.com/'


@pytest.fixture(scope='module')
def validator():
    return QRValidator()


@pytest.fixture(scope='module')
def original():
    return make_known_matrix(TEXT, ec='L')


def data_cells(matrix, count, seed=1):
    cells = [(r, c) for r in range(matrix.size) for c in range(matrix.size)
             if not matrix._is_fixed_pattern(r, c) and r > 8 and c > 8]
    return random.Random(seed).sample(cells, count)


def as_int(bits):
    return int(''.join(map(str, bits[::-1])), 2)


def test_candidate_space_exhaustive_covers_everything():
    space = CandidateSpace(num_unknown=10, count=10_000, seed=0)
    assert space.count == 1024
    assert sorted(as_int(space.bits(i)) for i in range(space.count)) == list(range(1024))


@pytest.mark.parametrize('num_unknown', [12, 40, 130])
def test_candidate_space_sample_has_no_duplicates(num_unknown):
    space = CandidateSpace(num_unknown=num_unknown, count=3000, seed=7)
    values = {as_int(space.bits(i)) for i in range(space.count)}
    assert len(values) == space.count
    assert all(len(space.bits(i)) == num_unknown for i in range(5))


def test_sequential_finds_original_and_counts_exactly(validator, original):
    engine = BruteforceEngine(damage(original, data_cells(original, 8)), validator)
    results = engine.run(mode='fast', max_iterations=1000, parallel=False)

    assert engine.stats['tested'] == 256
    assert results and results[0].decoded_data == TEXT
    # Dedupe: ein Eintrag pro Inhalt, valid zählt eindeutige Ergebnisse
    assert len({r.decoded_data for r in results}) == len(results) == engine.stats['valid']


def test_explicit_limits_override_mode_defaults(validator, original):
    engine = BruteforceEngine(damage(original, data_cells(original, 8)), validator)
    engine.run(mode='fast', max_iterations=50, parallel=False)
    assert engine.stats['tested'] == 50


def test_result_callback_once_per_unique_text(validator, original):
    seen = []
    engine = BruteforceEngine(damage(original, data_cells(original, 8)), validator)
    engine.set_result_callback(lambda r: seen.append(r.decoded_data))
    engine.run(mode='custom', max_iterations=256, parallel=False)
    assert len(seen) == len(set(seen)) >= 1


def test_multiprocess_counts_exactly_and_finds_original(validator, original):
    engine = BruteforceEngine(damage(original, data_cells(original, 11)), validator)
    progress = []
    engine.set_progress_callback(lambda tested, valid, total: progress.append(tested))
    results = engine.run(mode='custom', max_iterations=10_000, max_time=120, parallel=True)

    assert 2048 > PARALLEL_THRESHOLD
    assert engine.stats['tested'] == 2048
    assert progress[-1] == 2048 and progress == sorted(progress)
    assert any(r.decoded_data == TEXT for r in results)


def test_multiprocess_respects_time_limit(validator, original):
    engine = BruteforceEngine(damage(original, data_cells(original, 30)), validator)
    engine.run(mode='custom', max_iterations=10_000_000, max_time=1.5, parallel=True)
    stats = engine.get_stats()
    assert 0 < stats['tested'] < 10_000_000
    assert stats['elapsed'] < 15


def test_multiprocess_stop(validator, original):
    engine = BruteforceEngine(damage(original, data_cells(original, 30)), validator)
    threading.Timer(1.0, engine.stop).start()
    engine.run(mode='custom', max_iterations=10_000_000, max_time=120, parallel=True)
    stats = engine.get_stats()
    assert stats['tested'] < 10_000_000
    assert stats['elapsed'] < 15
