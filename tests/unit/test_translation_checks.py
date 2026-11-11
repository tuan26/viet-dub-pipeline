import json
import re
from pathlib import Path

from vietdub.engines.translation_checks import check_line, summarize

CASES = json.loads((Path(__file__).parent.parent / "data/translation_cases.json").read_text(encoding="utf-8"))
LESS = CASES["scenes"][0]["lines"][0]  # "less than an hour"


def test_every_pattern_compiles_and_every_line_has_a_check():
    for scene in CASES["scenes"]:
        for line in scene["lines"]:
            assert line.get("all") or line.get("any"), line["text"]
            for key in ("all", "any", "none"):
                for pattern in line.get(key, []):
                    re.compile(pattern.lower())


def test_correct_and_reversed_meaning():
    assert check_line(LESS, "Chúng ta còn chưa đầy một tiếng trước cuộc họp.") == []
    assert check_line(LESS, "Chúng ta có ít hơn một tiếng nữa.") == []
    assert check_line(LESS, "Chúng ta chỉ còn hơn một tiếng.")  # the error seen in the real run


def test_untranslated_and_literal_idioms_fail():
    idiom = next(l for s in CASES["scenes"] for l in s["lines"] if "cats and dogs" in l["text"])
    assert check_line(idiom, "Ngoài kia mưa như trút nước.") == []
    assert check_line(idiom, "Ngoài kia đang mưa chó mèo.")
    zh = CASES["scenes"][5]["lines"][0]
    assert any("nước ngoài" in p for p in check_line(zh, "会议 chưa đầy nửa tiếng nữa bắt đầu."))
    assert check_line(zh, "") == ["bản dịch rỗng"]


def test_summary_counts_by_category():
    out = summarize([{"cat": "time", "problems": []}, {"cat": "time", "problems": ["x"]}, {"cat": "idiom", "problems": []}])
    assert out == {"passed": 2, "total": 3, "by_category": {"idiom": "1/1", "time": "1/2"}}
