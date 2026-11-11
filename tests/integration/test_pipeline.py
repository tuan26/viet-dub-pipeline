"""End-to-end run on a synthetic clip with real ffmpeg, a fake translator and the beep voice."""
import json
import shutil
import subprocess

import pytest

from vietdub import cli, media, pipeline
from vietdub.engines import tts
from vietdub.rights import check_rights

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

SRT = """1
00:00:00,500 --> 00:00:01,500
Hello there

2
00:00:02,000 --> 00:00:02,600
This line is far too long to fit into its little slot of time

3
00:00:04,000 --> 00:00:05,000
Goodbye
"""


@pytest.fixture
def clip(tmp_path):
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=6:size=160x120:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-shortest", str(video)],
        check=True,
    )
    subs = tmp_path / "clip.srt"
    subs.write_text(SRT, encoding="utf-8")
    return video, subs


def fake_chat(system, user):
    lines = json.loads(user[user.index("[") :])
    return json.dumps([f"dịch {t}" for t in lines], ensure_ascii=False)


def make_job(clip, tmp_path, **extra):
    video, subs = clip
    return pipeline.Job(
        video=video, out_dir=tmp_path / "out", rights=check_rights("owned", "self-made test clip", None),
        synth=tts.beep(), chat=fake_chat, subtitles=subs, log=lambda m: None, **extra,
    )


def test_produces_dubbed_video_subtitles_and_report(clip, tmp_path):
    job = make_job(clip, tmp_path)
    output = pipeline.run(job)

    assert output.name == "clip.vi.mp4"
    assert media.has_audio(output)
    assert abs(media.duration(output) - 6.0) < 0.3
    assert "dịch Hello there" in (tmp_path / "out" / "clip.vi.srt").read_text(encoding="utf-8")
    assert "self-made test clip" in (tmp_path / "out" / "CREDITS.txt").read_text(encoding="utf-8")
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["segments"] == 3
    assert report["sped_up"] >= 1 and report["truncated"] == [2]
    assert report["background"] == "ducked-original"


def test_rerun_reuses_translation_and_clips(clip, tmp_path):
    pipeline.run(make_job(clip, tmp_path))

    def no_chat(system, user):
        raise AssertionError("translator called again")

    def no_synth(text, stem):
        raise AssertionError("voice synthesized again")

    job = make_job(clip, tmp_path)
    job.chat, job.synth = no_chat, no_synth
    assert pipeline.run(job).exists()


def test_cli_refuses_without_rights(clip, tmp_path, capsys):
    video, subs = clip
    code = cli.main(["run", str(video), "--srt", str(subs), "--tts", "beep",
                     "--translator", "none", "-o", str(tmp_path / "o")])
    assert code == 2
    assert "--license" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_cli_end_to_end_with_vietnamese_subtitles(clip, tmp_path):
    video, subs = clip
    code = cli.main(["run", str(video), "--srt", str(subs), "--tts", "beep", "--translator", "none",
                     "--license", "owned", "--source", "test", "-o", str(tmp_path / "o")])
    assert code == 0
    assert (tmp_path / "o" / "clip.vi.mp4").exists()
