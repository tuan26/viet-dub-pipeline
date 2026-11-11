import json

import pytest

from vietdub.engines.translate import translate
from vietdub.models import Segment, VietdubError


def segs(n):
    return [Segment(i, i, i + 1, f"line {i}") for i in range(1, n + 1)]


def test_batch_reply_is_applied_in_order():
    s = segs(3)
    translate(s, lambda system, user: 'Kết quả:\n["một", "hai", "ba"]')
    assert [x.translation for x in s] == ["một", "hai", "ba"]


def test_wrong_count_falls_back_to_single_lines():
    calls = []

    def chat(system, user):
        calls.append(user)
        if "Dịch 1 câu" in user:
            text = json.loads(user[user.index("[") :])[0]
            return json.dumps([f"vi:{text}"])
        return '["chỉ có một"]'

    s = segs(2)
    translate(s, chat)
    assert [x.translation for x in s] == ["vi:line 1", "vi:line 2"]
    assert len(calls) == 3


def test_garbage_reply_raises():
    with pytest.raises(VietdubError):
        translate(segs(1), lambda system, user: "xin lỗi, tôi không dịch được")
