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
        def __init__(self, text, voice, proxy=None):
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
