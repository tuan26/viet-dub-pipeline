# Implementation Plan: Tự động lồng tiếng Việt cho video

**Branch**: `001-auto-viet-dub` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

## Summary
CLI `vietdub run` chạy 6 bước: tách âm thanh → lấy câu thoại (SRT hoặc nhận dạng) → dịch → giọng đọc
→ khớp thời lượng và ghép đường tiếng → trộn và xuất. Mỗi engine là một hàm truyền vào `Job`.

## Technical Context
**Language/Version**: Python ≥ 3.10
**Primary Dependencies**: lõi không phụ thuộc; extra: faster-whisper, edge-tts, demucs; FFmpeg hệ thống
**Storage**: file trong thư mục kết quả (`work/segments.json`, `work/clips/`)
**Testing**: pytest; test tích hợp dùng ffmpeg thật, engine giả
**Target Platform**: Linux/macOS/Windows có FFmpeg
**Project Type**: cli
**Constraints**: chạy được không GPU khi có SRT; đường tiếng lồng mono 24 kHz
**Scale/Scope**: một video mỗi lần chạy

## Constitution Check
| Nguyên tắc | Đáp ứng |
|---|---|
| I. Nội dung có quyền | `rights.check_rights` chạy trước mọi xử lý; không có crawler |
| II. OSS trước | Mặc định Ollama + edge-tts; Piper/faster-whisper/Demucs đều mở |
| III. Engine thay được | `Job.synth`, `Job.chat`, `Job.transcribe`, `Job.separate` |
| IV. Chạy lại được | Bỏ qua bước đã có kết quả; `--force` để làm lại |
| V. Test | 22 test, không cần mạng |

## Project Structure
```text
src/vietdub/
├── cli.py          # tham số dòng lệnh, in lỗi
├── pipeline.py     # Job và thứ tự các bước
├── rights.py       # cổng kiểm tra quyền, ghi công
├── srt.py          # đọc/ghi SRT
├── timing.py       # kế hoạch khớp thời lượng
├── media.py        # ffmpeg/ffprobe, ghép WAV, trộn
├── models.py       # Segment, VietdubError
└── engines/        # asr.py, translate.py, tts.py, separate.py
tests/
├── unit/
└── integration/
```
