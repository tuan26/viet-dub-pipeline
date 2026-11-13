# Kiểm chứng Phase 1 bằng tiến trình thật — 2026-11-13

Máy: 4 nhân CPU, 15 GB RAM, không GPU. PostgreSQL 16 thật. Script: `tools/phase1_check.py` (chạy lại được).
Số liệu gốc: `docs/benchmarks/phase1-2026-11-13.json`.

## Phạm vi và cách làm

Mỗi kịch bản khởi động **tiến trình worker thật** (`vietdub auto worker` hoặc `vietdub serve`), dùng cơ sở dữ liệu
PostgreSQL thật và 7 clip có lời thoại thật cắt từ ba phim CC-BY (6 clip 20 giây, 1 clip 150 giây). Để tập trung vào
phần điều phối và chạy nhanh:

- giọng đọc dùng engine `beep` (offline), không phải edge-tts;
- bước dịch gọi một máy chủ HTTP thật trên máy (`tools/fake_translator.py`) chỉ thêm tiền tố "Bản dịch:", để có thể
  **tắt/bật một phụ thuộc mạng thật** khi thử cơ chế thử lại.

Nhận dạng lời thoại (faster-whisper), FFmpeg, kiểm tra chất lượng tự động và toàn bộ luồng trạng thái là thật.
Chất lượng lồng tiếng không phải mục tiêu của đợt này (đã đo ở các báo cáo trước).

## Kết quả

| # | Kịch bản | Kết quả | Bằng chứng chính |
|---|---|---|---|
| 1 | Hai worker song song, 6 video | Đạt | Mỗi video lồng tiếng đúng 1 lần; mỗi worker làm 3 video; hai worker chạy cùng lúc; 36 s thực so với 65 s cộng dồn |
| 2 | Tự thử lại khi bộ dịch không trả lời | Đạt | Lần 1 lỗi "Connection refused" → video về hàng đợi, hẹn thử lại sau 6 s; bật bộ dịch → tự xong (`QC_PASS`) |
| 3 | Dừng sau số lần tối đa, rồi thử lại tay | Đạt | `max_attempts = 2` → `FAILED` sau đúng 2 lần, lý do ghi rõ; sau khi sửa nguyên nhân và "Thử lại" → `NEEDS_REVIEW` |
| 4 | `kill -9` worker giữa lúc lồng tiếng; heartbeat | Đạt | Worker còn sống làm 17 s trên job (giới hạn 6 s) mà không bị lấy mất nhờ heartbeat; sau `kill -9`, video vẫn ở `DUBBING`, worker kia khôi phục sau 5 s và làm tiếp đến hết |
| 5 | Khởi động lại PostgreSQL giữa lúc lồng tiếng | Đạt | Video đang xử lý vẫn xong, 0 lần thử lại; file mới thêm sau đó vẫn được phát hiện và xử lý |
| 6 | Kiểm tra nguồn theo lịch, chống trùng | Đạt | Chu kỳ 6 s: 15 s không có gì mới → không thêm video; file mới được thấy sau 1 s; bản sao nội dung → `DUPLICATE`; 2 lần lồng tiếng cho 3 file |
| 7 | Giới hạn tài nguyên | Đạt | Ổ đĩa dưới ngưỡng → không tải, chờ thử lại; RAM dưới ngưỡng → không lồng tiếng; hết phút trong ngày → hoãn tới hôm sau, không tính là lỗi; video quá dài → `FAILED` ngay |
| 8 | `vietdub serve`: giám sát worker, web, các trạng thái | Đạt (lần 4, sau khi sửa lỗi) | Worker nhận `OMP_NUM_THREADS=2`, `nice 7`; `kill -9` worker-2 → được khởi động lại; qua web thật: tạm dừng + xác nhận quyền → đứng yên 10 s → tiếp tục → xong; duyệt → `READY`; SIGTERM → cả hai worker ghi "stopped" |

Các trạng thái đã đi qua trong lần chạy thật: `AWAITING_RIGHTS`, `APPROVED`, `DOWNLOADING`, `DOWNLOADED`, `DUBBING`,
`DUBBED`, `CHECKING`, `QC_PASS`, `NEEDS_REVIEW`, `READY`, `DUPLICATE`, `FAILED`.

## Lỗi thật tìm thấy và đã sửa

1. **`serve` để lại worker mồ côi khi bị SIGTERM** (kịch bản 8, lần 2 không đạt). uvicorn bản mới phát lại tín hiệu sau khi
   tự tắt nên phần dọn dẹp không chạy; hai worker tiếp tục chạy sau khi `serve` đã thoát. Sửa: bắt SIGTERM thành thoát bình
   thường; trên Linux, worker tự nhận SIGTERM khi `serve` chết. Kiểm tra lại: `kill -9 serve` → 0 worker còn lại.
2. **Worker bị ngắt giữa lúc dọn dẹp** (lần 3 không đạt): nhận tín hiệu dừng lần hai. Sửa: bỏ qua tín hiệu lặp lại.
3. Script kiểm chứng tự treo khi khởi động lại PostgreSQL (lỗi của script, không phải của hệ thống).

Ba thay đổi sau được làm **trước** khi chạy, khi thiết kế kịch bản 5, nên không có lần chạy nào cho thấy lỗi của bản cũ:
lỗi kết nối PostgreSQL nay là lỗi tạm thời (trước đây có thể làm video thành `FAILED`); việc ghi tiến độ không còn làm
hỏng lượt lồng tiếng; worker trả video về hàng đợi nếu DB rớt đúng lúc trả kết quả.

## Chưa kiểm chứng (và vì sao)

| Mục | Lý do |
|---|---|
| Chạy liên tục nhiều giờ / một ngày | Mỗi kịch bản chỉ chạy vài phút; chưa có lần chạy dài |
| Hạn mức phút đặt lại lúc nửa đêm | Không chờ qua nửa đêm |
| Ổ đĩa đầy giữa lúc đang tải | Chỉ thử ngưỡng kiểm tra trước khi tải |
| Giới hạn CPU có hiệu quả thật | Chỉ xác nhận biến môi trường và mức `nice` của worker, chưa đo mức dùng CPU |
| Worker trên nhiều máy | Chỉ chạy trên một máy |
| Nguồn Commons, YouTube CC, kênh đã cấp phép trong luồng tự động | Chưa chạy (Commons từng giới hạn tần suất với máy thử) |
| Docker | Có `Dockerfile` và `docker/compose.yml` nhưng máy thử không có Docker daemon |
