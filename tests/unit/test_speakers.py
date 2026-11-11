import numpy as np
import pytest

from vietdub.engines import casting, diarize
from vietdub.engines.asr import split_on_pauses


def test_cluster_groups_similar_vectors_and_numbers_by_first_appearance():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=32), rng.normal(size=32)
    vectors = [a + 0.05 * rng.normal(size=32) if who == "a" else b + 0.05 * rng.normal(size=32)
               for who in "abbaab"]
    assert diarize.cluster(vectors) == [0, 1, 1, 0, 0, 1]


def test_cluster_respects_requested_speaker_count():
    rng = np.random.default_rng(1)
    vectors = [rng.normal(size=16) for _ in range(6)]
    assert len(set(diarize.cluster(vectors, speakers=3))) == 3
    assert len(set(diarize.cluster(vectors, speakers=1))) == 1


@pytest.mark.parametrize("hz", [110, 220])
def test_pitch_of_a_pure_tone(hz):
    t = np.arange(diarize.RATE) / diarize.RATE
    assert abs(diarize.pitch(np.sin(2 * np.pi * hz * t).astype(np.float32) * 0.5) - hz) < 6


def test_pitch_of_silence_is_zero():
    assert diarize.pitch(np.zeros(diarize.RATE, np.float32)) == 0.0


def test_cast_gives_each_speaker_a_distinct_voice_by_gender():
    voices = casting.cast({
        "S1": {"gender": "male", "lines": 3}, "S2": {"gender": "female", "lines": 5},
        "S3": {"gender": "male", "lines": 9}, "S4": {"gender": "male", "lines": 1},
    })
    assert voices["S2"] == casting.Voice("vi-VN-HoaiMyNeural")
    assert voices["S3"] == casting.Voice("vi-VN-NamMinhNeural")  # most lines keeps the plain voice
    assert len(set(voices.values())) == 4
    assert all(v.name == "vi-VN-NamMinhNeural" for s, v in voices.items() if s != "S2")


def test_words_are_split_into_lines_at_pauses():
    words = [(0.5, 0.8, " Hello"), (0.8, 1.2, " there."), (2.4, 2.7, " Hi"), (2.75, 3.0, " you.")]
    assert split_on_pauses(words) == [(0.5, 1.2, "Hello there."), (2.4, 3.0, "Hi you.")]


def test_single_line_clusters_join_the_nearest_speaker():
    a, b, noisy_a = [1, 0, 0], [0, 1, 0], [0.6, 0.1, 0.8]  # the last is a poor embedding of speaker a
    vectors = [a, a, a, b, b, b, noisy_a]
    assert len(set(diarize.cluster(vectors, threshold=0.3))) == 3
    labels = diarize.cluster(vectors, threshold=0.3, min_lines=2)
    assert len(set(labels)) == 2 and labels[6] == labels[0]
