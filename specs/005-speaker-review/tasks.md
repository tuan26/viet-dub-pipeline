# Tasks

- [x] T001 Nhãn nháp người nói cho 4 clip `tests/data/speakers/`
- [x] T002 `engines/speaker_metrics.py`, `tools/speaker_eval.py`; so sánh 6 model × 2 cách, quét ngưỡng
- [x] T003 Đổi sang sherpa-onnx + ERes2Net, ngưỡng 0,8, âm gốc; cờ `uncertain` cho câu
- [x] T004 Bỏ việc coi cao độ là giới tính; `suggested_gender`, `voice_basis`
- [x] T005 `review.py`, `--review`, mã thoát 3, `batch` giữ mục chờ duyệt
- [x] T006 `tools/stt_eval.py` (câu sót, tắt lọc tiếng nói); so sánh 4 cỡ Whisper
- [x] T007 `tools/tts_eval.py`; chạy thật Piper; sửa cách gọi Piper
- [x] T008 Lưu thời gian từng bước qua các lần chạy tiếp
- [x] T009 Chạy lại 3 clip: bản tự động và bản đã duyệt; `docs/evaluation-2026-11-12.md`
- [ ] T010 Người nghe xác nhận nhãn; gán nhãn vai phụ Tears of Steel
- [ ] T011 Thử pyannote 3.1 đầy đủ khi có token
- [ ] T012 Đo một TTS trả phí nhiều giọng và VieNeu-TTS 0.5B sau khi xác minh giấy phép
- [ ] T013 Thử `campplus-zh-en` trên phim tiếng Trung có quyền sử dụng
