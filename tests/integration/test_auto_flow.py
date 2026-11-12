"""Folder source -> hash -> real pipeline (beep voice, fake recognition) -> real QC."""
import json
import shutil
import subprocess

import pytest

from vietdub import cli
from vietdub.auto import config as auto_config
from vietdub.auto import qc
from vietdub.auto.store import Store
from vietdub.engines import asr
from vietdub.models import Segment

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "videos").mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x120:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-shortest", str(tmp_path / "videos" / "clip.mp4")], check=True)
    (tmp_path / "pipeline.toml").write_text('''
[storage]
library = "library"
[dubbing]
tts = "beep"
translator = "none"
[[source]]
name = "mine"
type = "folder"
path = "videos"
license = "owned"
rights = "verified"
''', encoding="utf-8")
    monkeypatch.setattr(asr, "transcribe", lambda audio, language, model: [Segment(1, 0.5, 1.5, "Xin chào"), Segment(2, 3.0, 4.0, "Tạm biệt")])
    return tmp_path


def test_cli_runs_the_whole_flow_and_humans_decide_the_rest(project, capsys):
    cfg_arg = ["--config", str(project / "pipeline.toml")]
    assert cli.main(["auto", "run", *cfg_arg]) == 0
    store = Store(auto_config.load(project / "pipeline.toml").database)
    row = store.videos()[0]
    assert row["state"] in ("QC_PASS", "NEEDS_REVIEW") and len(row["content_hash"]) == 64
    result = json.loads((project / "library" / "dubbed" / "folder_mine_clip_mp4" / "qc.json").read_text(encoding="utf-8"))
    by_name = {c["name"]: c for c in result["checks"]}
    assert by_name["mp4_giai_ma"]["ok"] and by_name["thoi_luong"]["ok"] and by_name["co_loi_thoai"]["value"] == 2

    assert cli.main(["auto", "run", *cfg_arg]) == 0  # nothing new, nothing redone
    assert len(store.videos()) == 1
    assert cli.main(["auto", "approve", row["id"], "--note", "đã xem", *cfg_arg]) == 0
    assert store.get(row["id"])["state"] == "READY"
    assert cli.main(["auto", "allow", row["id"], "--note", "x", *cfg_arg]) == 2  # wrong state for that command
    assert cli.main(["auto", "dashboard", "--out", str(project / "d.html"), *cfg_arg]) == 0
    assert "READY" in (project / "d.html").read_text(encoding="utf-8")
    assert any(e["stage"] == "human" for e in store.events(row["id"]))


def test_qc_flags_a_silent_or_untranslated_result(project):
    cli.main(["auto", "run", "--config", str(project / "pipeline.toml")])
    out = project / "library" / "dubbed" / "folder_mine_clip_mp4"
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    report["untranslated"] = [1]
    report["duration_seconds"] = 60.0
    (out / "report.json").write_text(json.dumps(report), encoding="utf-8")
    result = qc.check(out, auto_config.QC)
    assert result["status"] == "NEEDS_REVIEW"
    failed = {c["name"] for c in result["checks"] if not c["ok"]}
    assert {"cau_chua_dich", "thoi_luong"} <= failed
