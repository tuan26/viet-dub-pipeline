# Feature Specification: Đo và duyệt người nói; đo nhận dạng và giọng đọc

**Feature Branch**: `005-speaker-review` | **Created**: 2026-11-12 | **Status**: Implemented

## User Stories
1. **(P0) Đo được việc gán người nói** — Có nhãn chuẩn cho các clip thử và một lệnh so sánh các phương án trên cùng dữ liệu.
   *Kiểm tra*: `tools/speaker_eval.py` in số câu đúng, số câu nhầm, số câu không có người nói cho từng phương án.
2. **(P0) Người dùng duyệt vai trước khi xuất** — `--review` dừng trước khi tạo giọng, cho sửa người nói từng câu và chọn giọng.
   *Kiểm tra*: lần chạy đầu thoát mã 3 và chưa có video; sau khi duyệt, chạy lại xuất video đúng vai đã sửa.
3. **(P1) Đo nhận dạng lời thoại** — WER, câu sót, lệch mốc, thời gian cho từng model và từng loại âm đầu vào.
4. **(P2) So sánh giọng đọc** — Cùng một bộ câu qua các engine; lưu file để nghe.

## Requirements
- **FR-001**: Nhãn chuẩn chỉ chứa mốc thời gian, mã người nói và mức tin cậy; không chứa lời thoại.
- **FR-002**: Phép đo ghép nhãn tìm được với nhân vật thật trước khi đếm; nhãn thừa tính là sai.
- **FR-003**: Giới tính suy từ cao độ CHỈ là gợi ý; báo cáo PHẢI ghi giọng được chọn theo máy hay theo người duyệt.
- **FR-004**: Ở chế độ duyệt, KHÔNG tạo giọng nào trước khi `reviewed` là true; thiếu giọng cho một người thì dừng kèm lý do.
- **FR-005**: Model người nói, model nhận dạng và engine giọng đọc thay được độc lập; mặc định chỉ đổi khi có số đo.
- **FR-006**: Không dùng nhân bản giọng người thật.

## Success Criteria
- **SC-001**: Phương án người nói mặc định vượt mức sàn "một người" trên bộ câu chuẩn (đo: 56/61 so với 42/61).
- **SC-002**: Bước duyệt chạy được trên cả ba clip thật (đo: 3/3 dừng rồi xuất video).
- **SC-003**: Số câu sót ở Tears of Steel giảm so với cấu hình cũ (đo: 12 → 8 với tách nhạc + `medium`).

## Chưa đạt
- Độ chính xác tự động end-to-end gần như không đổi (43/49 → 47/53).
- Nhãn chuẩn chưa được người nghe xác nhận; cờ "không chắc" chỉ bắt được 1/6 câu sai.
- Chưa có TTS nhiều giọng với điều khoản thương mại đã kiểm chứng.
