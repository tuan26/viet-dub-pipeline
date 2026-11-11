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


def test_edge_voice_retries_dropped_requests(tmp_path, monkeypatch):
    import sys
    import types

    from vietdub.engines import tts

    calls = []

    class Communicate:
        def __init__(self, text, voice, **options):
            pass

        async def save(self, path):
            calls.append(path)
            if len(calls) < 3:
                raise RuntimeError("No audio was received")
            open(path, "wb").write(b"mp3")

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    out = tts.edge(pause=0)("xin chào", tmp_path / "00001_raw")
    assert out.read_bytes() == b"mp3" and len(calls) == 3

    calls.clear()
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(
        Communicate=type("C", (), {"__init__": lambda self, *a, **k: None,
                                   "save": lambda self, path: (_ for _ in ()).throw(RuntimeError("down"))})))
    with pytest.raises(VietdubError, match="sau 2 lần thử"):
        tts.edge(retries=2, pause=0)("xin chào", tmp_path / "x")


def test_line_left_in_chinese_is_retried_alone():
    calls = []

    def chat(system, user):
        calls.append(user)
        if "Dịch 1 câu" in user:
            assert "chỉ viết bằng tiếng Việt" in user
            return '["Tôi không có thời gian."]'
        return '["Xin chào.", "我没有时间。"]'

    s = segs(2)
    assert translate(s, chat) == []
    assert [x.translation for x in s] == ["Xin chào.", "Tôi không có thời gian."]
    assert len(calls) == 2


def test_line_that_stays_foreign_is_reported_not_fatal():
    s = segs(2)
    unresolved = translate(s, lambda system, user: '["我没有时间。"]' if "Dịch 1 câu" in user else '["Xin chào.", "我没有时间。"]')
    assert unresolved == [2] and s[0].translation == "Xin chào."


def test_malformed_single_reply_is_retried_before_failing():
    replies = iter(["oops", "vẫn hỏng", '["được rồi"]'])
    s = segs(1)
    translate(s, lambda system, user: next(replies))
    assert s[0].translation == "được rồi"


@pytest.mark.parametrize("reply", [
    "Ngắn hơn rồi.", '"Ngắn hơn rồi."', '["Ngắn hơn rồi."]',
    '```json\n{\n  "rewritten": "Ngắn hơn rồi."\n}\n```', "Ngắn hơn rồi.\n(giải thích thêm)",
])
def test_shorten_accepts_the_reply_shapes_models_use(reply):
    from vietdub.engines.translate import shorten

    seg = Segment(1, 0, 1, "It is much shorter now, I promise you.", "Bây giờ nó đã ngắn hơn rất nhiều rồi, tôi hứa.")
    assert shorten(seg, lambda system, user: reply, 4) == "Ngắn hơn rồi."


def test_shorten_rejects_a_reply_that_is_not_shorter():
    from vietdub.engines.translate import shorten

    seg = Segment(1, 0, 1, "Hi.", "Chào.")
    assert shorten(seg, lambda system, user: "Xin chào bạn nhé.", 2) is None
