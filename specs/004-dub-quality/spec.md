# Feature Specification: Chất lượng lồng tiếng trên phim thật

**Feature Branch**: `004-dub-quality` | **Created**: 2026-11-11 | **Status**: Implemented

## User Stories
1. **(P1) Dịch đúng nghĩa** — Thay đổi model hay prompt dịch chỉ được chấp nhận khi bộ test hội thoại cho điểm cao hơn.
   *Kiểm tra*: `tools/translation_eval.py` in điểm theo nhóm lỗi cho một model bất kỳ.
2. **(P1) Mỗi nhân vật một giọng** — Với `--speakers`, mỗi người nói được gán một giọng Việt riêng; người dùng sửa được khi máy đoán sai.
   *Kiểm tra*: clip có nhãn người nói → đúng từng câu; `--cast` đổi giới tính giọng.
3. **(P2) Giữ nhạc nền** — Với `--separate`, giọng gốc bị loại, nhạc và hiệu ứng được giữ.
4. **(P2) Câu vừa chỗ** — Câu đọc không vừa khoảng thời gian được rút gọn tự động trước khi phải cắt.

## Requirements
- **FR-001**: Có bộ test dịch gồm phủ định, thời gian, số lượng, tên riêng, thành ngữ, xưng hô; chấm tự động.
- **FR-002**: Câu dịch còn chữ nước ngoài PHẢI được dịch lại; câu không cứu được PHẢI nằm trong báo cáo.
- **FR-003**: Nhận diện người nói và gán giọng là hai module tách rời, thay được độc lập.
- **FR-004**: Model nhận diện người nói PHẢI có giấy phép cho dùng thương mại.
- **FR-005**: Khoảng lặng quanh giọng đọc PHẢI được cắt trước khi khớp thời lượng.
- **FR-006**: Báo cáo mỗi lần chạy ghi người nói, câu rút gọn, câu bị cắt, câu chưa dịch, thời gian từng bước.

## Success Criteria
- **SC-001**: Model dịch mặc định đạt ≥ 85% bộ test (đo: 35/39 = 90%).
- **SC-002**: Clip có nhãn: gán đúng người nói 100% (đo: 9/9).
- **SC-003**: Trên 3 đoạn phim thật: không câu nào chồng câu kế, ≤ 5% câu bị cắt (đo: 1/64).
- **SC-004**: Kết quả đo thực tế nằm ở `docs/quality-evaluation.md`, tách khỏi kết quả giả lập.

## Chưa đạt / còn mở
- Độ chính xác người nói từng câu trên phim thật chưa đo được (không có nhãn) và nhìn kết quả là chưa tin cậy.
- Đoán giới tính theo cao độ sai với giọng diễn xuất.
- Chưa thử pyannote, API dịch trả phí, TTS thương mại, GPU, nguồn tiếng Trung thật.
