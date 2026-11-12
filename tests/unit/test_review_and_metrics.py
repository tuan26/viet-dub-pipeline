import importlib.util
import json
from pathlib import Path

import pytest

from vietdub import review
from vietdub.engines import casting, diarize
from vietdub.engines.speaker_metrics import best_mapping, score
from vietdub.models import Segment, VietdubError

ROOT = Path(__file__).parent.parent.parent


def test_score_maps_labels_before_counting():
    truth = ["A", "A", "B", "B", "A"]
    assert score(truth, ["S2", "S2", "S1", "S1", "S2"])["accuracy"] == 1.0
    out = score(truth, ["S1", "S1", "S1", "S2", None])
    assert (out["correct"], out["wrong_speaker"], out["no_speaker"]) == (3, 1, 1)
    assert out["speakers_found"] == 2 and out["speakers_true"] == 2


def test_extra_found_speakers_count_as_errors():
    truth = ["A"] * 4 + ["B"] * 2
    found = ["S1", "S1", "S2", "S3", "S4", "S4"]
    assert best_mapping(truth, found)["S1"] == "A"
    assert score(truth, found)["correct"] == 4  # S1->A (2) + S4->B (2); S2 and S3 are wrong


def test_one_cluster_scores_the_majority_baseline():
    assert score(["A", "A", "A", "B"], ["S1"] * 4)["accuracy"] == 0.75


def test_margins_flag_the_line_between_two_speakers():
    a, b, between = [1, 0, 0], [0, 1, 0], [1, 0.9, 0]
    m = diarize.margins([a, a, b, b, between], [0, 0, 1, 1, 0])
    assert min(m[:4]) > 0.5 and abs(m[4]) < 0.1


def test_cast_uses_confirmed_gender_then_suggestion_then_explicit_voice():
    voices = casting.cast({
        "PROOG": {"gender": "male", "suggested_gender": "female", "lines": 19},
        "EMO": {"suggested_gender": "male", "lines": 3},
        "NARRATOR": {"voice": "custom-voice", "pitch": "-5Hz", "lines": 1},
    })
    assert voices["PROOG"] == casting.Voice("vi-VN-NamMinhNeural")
    assert voices["EMO"].name == "vi-VN-NamMinhNeural" and voices["EMO"] != voices["PROOG"]
    assert voices["NARRATOR"] == casting.Voice("custom-voice", "-5Hz", "+0%")


def _segments():
    return [Segment(1, 0.5, 1.5, "Hello", "Xin chào", "S1"), Segment(2, 2.0, 3.0, "Hi", "Chào", "S2", True),
            Segment(3, 4.0, 5.0, "Bye", "Tạm biệt", "S1")]


def test_review_writes_files_then_waits(tmp_path):
    segs = _segments()
    info = {"S1": {"lines": 2, "pitch_hz": 120.0, "suggested_gender": "male"}, "S2": {"lines": 1, "pitch_hz": 210.0, "suggested_gender": "female"}}
    reviewed, _ = review.sync(tmp_path, segs, info, tmp_path / "missing.wav")
    assert not reviewed
    rows = (tmp_path / "review" / "lines.tsv").read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == review.COLUMNS and rows[2].split("\t")[4] == "?"
    cast = json.loads((tmp_path / "review" / "cast.json").read_text(encoding="utf-8"))
    assert cast["reviewed"] is False and cast["speakers"]["S1"]["gender"] == ""  # the suggestion is not pre-filled as fact
    assert not review.sync(tmp_path, segs, info, tmp_path / "missing.wav")[0]  # still waiting


def test_review_applies_edits_once_confirmed(tmp_path):
    segs = _segments()
    review.sync(tmp_path, segs, {"S1": {}, "S2": {}}, tmp_path / "missing.wav")
    folder = tmp_path / "review"
    lines = (folder / "lines.tsv").read_text(encoding="utf-8").replace("\tS2\t", "\tS1\t").replace("Tạm biệt", "Hẹn gặp lại")
    (folder / "lines.tsv").write_text(lines, encoding="utf-8")
    cast = json.loads((folder / "cast.json").read_text(encoding="utf-8"))
    cast["reviewed"] = True
    cast["speakers"]["S1"]["gender"] = "female"
    (folder / "cast.json").write_text(json.dumps(cast), encoding="utf-8")

    reviewed, speakers = review.sync(tmp_path, segs, {}, tmp_path / "missing.wav")
    assert reviewed and list(speakers) == ["S1"] and speakers["S1"]["lines"] == 3
    assert [s.speaker for s in segs] == ["S1", "S1", "S1"] and segs[2].translation == "Hẹn gặp lại"
    assert not any(s.uncertain for s in segs)


def test_review_refuses_a_speaker_without_confirmed_voice(tmp_path):
    segs = _segments()
    review.sync(tmp_path, segs, {"S1": {}, "S2": {}}, tmp_path / "missing.wav")
    cast_file = tmp_path / "review" / "cast.json"
    cast = json.loads(cast_file.read_text(encoding="utf-8"))
    cast["reviewed"] = True
    cast["speakers"]["S1"]["gender"] = "male"
    cast_file.write_text(json.dumps(cast), encoding="utf-8")
    with pytest.raises(VietdubError, match="S2"):
        review.sync(tmp_path, segs, {}, tmp_path / "missing.wav")


def test_ground_truth_files_are_well_formed():
    files = sorted((ROOT / "tests/data/speakers").glob("*.json"))
    assert len(files) >= 4
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for line in data["lines"]:
            assert line["end"] >= line["start"] and line["speaker"] and line["confidence"] in ("high", "medium", "low")
            assert "text" not in line  # labels only, no dialogue


def test_missed_line_detection():
    spec = importlib.util.spec_from_file_location("stt_eval", ROOT / "tools/stt_eval.py")
    stt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stt)
    ref = [Segment(1, 1.0, 2.0, "Hello there friend"), Segment(2, 10.0, 11.0, "Abort!"), Segment(3, 20.0, 21.0, "Three two one")]
    hyp = [Segment(1, 1.2, 2.1, "hello there, friend"), Segment(2, 19.5, 21.0, "3, 2, 1")]
    assert stt.missed_lines(ref, hyp) == [2]
    assert stt.wer(stt.words("a b c d"), stt.words("a x c")) == 0.5
