from vietdub.auto import qc


def test_uncovered_speech_and_gaps():
    regions = [(0.0, 2.0), (5.0, 9.0)]
    segments = [{"start": 0.2, "end": 1.8}, {"start": 5.2, "end": 6.0}]
    missed, total, gaps = qc.uncovered(regions, segments, pad=0.2)
    assert total == 6.0 and abs(missed - 2.8) < 1e-6
    assert gaps == [(6.2, 9.0)]


def test_line_flags():
    segments = [
        {"index": 1, "text": "We sold 1200 tickets today, not more.", "translation": "Hôm nay bán vé."},
        {"index": 2, "text": "Hello there.", "translation": "我没有时间", "uncertain": True},
        {"index": 3, "text": "这是一个测试", "translation": "Đây là một bài kiểm tra khá dài dòng hơn câu gốc nhiều"},
        {"index": 4, "text": "Fine.", "translation": "Được."},
    ]
    report = {"truncated": [4], "untranslated": [], "line_speed": {"4": 1.38}}
    flags = qc.line_flags(segments, report)
    assert flags[1] == ["so_khong_khop"]
    assert flags[2] == ["chua_dich", "nguoi_noi_khong_chac"]
    assert 3 not in flags  # length ratio is not judged for Chinese/Japanese/Korean sources
    assert flags[4] == ["bi_cat", "doc_nhanh"]


def test_length_ratio_flag():
    flags = qc.line_flags([{"index": 1, "text": "I really did not expect to see you here tonight", "translation": "Ừ."}], {})
    assert flags[1] == ["do_dai_la"]


def test_every_check_and_flag_has_a_label():
    assert qc.CRITICAL <= set(qc.LABELS)
    assert {"chua_dich", "bi_cat", "doc_nhanh", "nguoi_noi_khong_chac", "so_khong_khop", "do_dai_la"} == set(qc.LINE_FLAGS)
