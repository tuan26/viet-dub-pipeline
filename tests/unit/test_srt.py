import pytest

from vietdub.models import VietdubError
from vietdub.srt import parse_srt, write_srt

SAMPLE = """﻿1
00:00:01,000 --> 00:00:02,500
<i>你好</i>

2
00:00:03,000 --> 00:01:04,250
第二句
还有一行
"""


def test_parse_reads_times_and_joins_lines():
    segs = parse_srt(SAMPLE)
    assert [(s.index, s.start, s.end, s.text) for s in segs] == [
        (1, 1.0, 2.5, "你好"),
        (2, 3.0, 64.25, "第二句 还有一行"),
    ]


def test_round_trip_uses_translation():
    segs = parse_srt(SAMPLE)
    segs[0].translation, segs[1].translation = "Xin chào", "Câu hai"
    again = parse_srt(write_srt(segs, translated=True))
    assert [s.text for s in again] == ["Xin chào", "Câu hai"]
    assert again[1].end == 64.25


def test_empty_file_is_an_error():
    with pytest.raises(VietdubError):
        parse_srt("không có gì")
