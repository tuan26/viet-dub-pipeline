# Tasks: Chất lượng lồng tiếng trên phim thật

- [x] T001 [US1] Bộ test dịch `tests/data/translation_cases.json` + chấm `engines/translation_checks.py`
- [x] T002 [US1] `tools/translation_eval.py`; chạy Qwen2.5-7B và Gemma 3 12B, hai prompt
- [x] T003 [US1] Tự dịch lại câu còn chữ nước ngoài; đổi mặc định theo kết quả đo
- [x] T004 [US2] `engines/diarize.py` (WeSpeaker + gom nhóm + cao độ), `engines/casting.py`
- [x] T005 [US2] `--speakers`, `--cast`, `--speaker-model`; lưu `speaker` trong `segments.json`
- [x] T006 [US2] Chỉnh ngưỡng/ngữ cảnh theo số đo trên 3 phim thật
- [x] T007 [US3] Demucs chạy thật; tách trước, nhận dạng trên giọng đã tách
- [x] T008 [US4] Cắt khoảng lặng giọng đọc; rút gọn câu không vừa
- [x] T009 Mốc thời gian theo từng từ; `tools/stt_eval.py`, `tools/check_output.py`
- [x] T010 Chạy thật `vietdub batch` trên 3 đoạn phim CC-BY; báo cáo `docs/quality-evaluation.md`
- [ ] T011 Gắn nhãn người nói cho 3 đoạn phim để đo độ chính xác từng câu
- [ ] T012 Thử pyannote 3.1 (cần token Hugging Face) trên cùng 3 đoạn
- [ ] T013 Thử một API dịch lớn và một TTS thương mại nhiều giọng trên cùng bộ test
- [ ] T014 Đo trên GPU; thử nguồn tiếng Trung thật có quyền sử dụng
