# Tasks: Tự động lồng tiếng Việt cho video

## Phase 1: Setup
- [x] T001 Khởi tạo spec-kit, `pyproject.toml`, cấu trúc `src/vietdub`, `tests/`
- [x] T002 Viết constitution tại `.specify/memory/constitution.md`

## Phase 2: Foundational
- [x] T003 [P] `Segment`, `VietdubError` trong `src/vietdub/models.py`
- [x] T004 [P] Đọc/ghi SRT trong `src/vietdub/srt.py` + `tests/unit/test_srt.py`
- [x] T005 [P] Wrapper ffmpeg/ffprobe trong `src/vietdub/media.py`

## Phase 3: US2 — Chặn nội dung không rõ quyền (P1)
- [x] T006 [US2] `check_rights`, `Rights.credits` trong `src/vietdub/rights.py` + `tests/unit/test_rights.py`

## Phase 4: US1 — Lồng tiếng từ phụ đề (P1) 🎯 MVP
- [x] T007 [US1] Kế hoạch khớp thời lượng `src/vietdub/timing.py` + `tests/unit/test_timing.py`
- [x] T008 [P] [US1] Engine dịch OpenAI-compatible `src/vietdub/engines/translate.py` + test
- [x] T009 [P] [US1] Engine giọng đọc edge/piper/beep `src/vietdub/engines/tts.py`
- [x] T010 [US1] Ghép đường tiếng và trộn trong `src/vietdub/media.py`
- [x] T011 [US1] `Job`, `run` trong `src/vietdub/pipeline.py`
- [x] T012 [US1] CLI `src/vietdub/cli.py`
- [x] T013 [US1] Test tích hợp `tests/integration/test_pipeline.py`

## Phase 5: US5 — Chạy lại và sửa bản dịch (P2)
- [x] T014 [US5] Bỏ qua bước đã có kết quả, `--force`; test chạy lại

## Phase 6: US3 — Nhận dạng lời thoại (P2)
- [x] T015 [US3] `src/vietdub/engines/asr.py` (faster-whisper)
- [ ] T016 [US3] Chạy thử trên video có lời thoại thật và ghi kết quả vào research.md

## Phase 7: US4 — Giữ nhạc nền (P3)
- [x] T017 [US4] `src/vietdub/engines/separate.py` (Demucs)
- [ ] T018 [US4] Chạy thử Demucs trên video thật

## Phase 8: Polish
- [x] T019 README, quickstart
- [ ] T020 Chạy thử edge-tts và Ollama/Gemini thật trên máy có mạng
- [ ] T021 CI GitHub Actions chạy pytest

## Việc sau (tính năng riêng, cần spec mới)
- 002: dùng pyVideoTrans làm engine lồng tiếng thay engine tự viết
- 007: phân vai nhiều giọng (WhisperX + pyannote, mỗi nhân vật một giọng)
- 003: nhập video từ nguồn được phép — đã làm, xem `specs/003-licensed-ingest/`
- 004: đọc phụ đề cứng bằng OCR
- 005: xuất HLS và trang xem đơn giản
