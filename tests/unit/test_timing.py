from vietdub.models import Segment
from vietdub.timing import GAP, plan

SEGS = [Segment(1, 0.0, 2.0, "a"), Segment(2, 3.0, 4.0, "b"), Segment(3, 4.0, 5.0, "c")]


def test_clip_that_fits_is_untouched():
    p = plan(SEGS, [1.5, 0.5, 0.5], 10.0)[0]
    assert (p.speed, p.length, p.truncated) == (1.0, 1.5, False)


def test_clip_may_spill_into_following_silence():
    p = plan(SEGS, [2.8, 0.5, 0.5], 10.0)[0]  # line ends at 2.0, next starts at 3.0
    assert p.speed == 1.0 and not p.truncated


def test_long_clip_is_sped_up_to_fit():
    p = plan(SEGS, [1.0, 1.14, 0.5], 10.0)[1]  # slot is 1.0 - GAP
    assert 1.0 < p.speed <= 1.4 and not p.truncated
    assert abs(p.length - (1.0 - GAP)) < 1e-3


def test_very_long_clip_is_capped_and_truncated():
    p = plan(SEGS, [1.0, 5.0, 0.5], 10.0)[1]
    assert p.speed == 1.4 and p.truncated
    assert abs(p.length - (1.0 - GAP)) < 1e-9


def test_last_clip_uses_video_end():
    p = plan(SEGS, [1.0, 0.5, 5.9], 10.0)[2]
    assert p.speed == 1.0 and not p.truncated
