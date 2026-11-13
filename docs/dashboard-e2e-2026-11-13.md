# Kiểm thử Dashboard bằng trình duyệt thật — 2026-11-13

Một người dùng (điều khiển bằng Playwright/Chromium) đi hết luồng chỉ bằng trình duyệt, trên một đoạn phim thật:
*Tears of Steel* (Blender Foundation, CC-BY 3.0), trích 150 giây, nhiều nhân vật, có nhạc nền.
Script: `tools/ui_e2e_part1.mjs`, `tools/ui_e2e_part2.mjs`. Máy: 4 nhân CPU, 15 GB RAM, không GPU; PostgreSQL 16.
Cấu hình lồng tiếng: Whisper `medium`, tách nhạc Demucs, Gemma 3 12B dịch, edge-tts, nhận diện người nói ERes2Net.

## Diễn biến (giờ thật)

| Lúc | Việc người dùng làm trên trình duyệt | Hệ thống |
|---|---|---|
| 04:40:31 | Mở trang lần đầu → tạo tài khoản quản trị | |
| 04:40:32 | Thêm nguồn "Thư mục", giấy phép CC-BY, quyền **chưa xác minh** | |
| 04:40:33 | | Worker phát hiện video → "Chờ xác minh quyền" |
| 04:40:36 | Mở video, ghi căn cứ, bấm "Xác nhận quyền" | Tải (1 s) |
| 04:48:07 | | Lồng tiếng xong trong 442 s → kiểm tra → **Cần duyệt** (2 cảnh báo: 29% câu không chắc người nói, vai do máy gán) |
| 04:49:49 | Trang duyệt: đổi người nói 15 câu sang THOM/CELIA, sửa 11 bản dịch, chọn giọng cho 6 nhân vật, tick "Đã kiểm tra người nói của mọi câu" | |
| 04:49:51 | Bấm 🔊 nghe thử câu 12 | Trả về file MP3 (200) |
| 04:49:53 | Bấm "Lưu và xuất lại video" | |
| 04:50:46 | | Xuất lại trong **47 s** (chỉ làm lại các câu bị sửa) → **Đạt kiểm tra**, 0 lỗi, 0 cảnh báo |
| 04:50:51 | Ghi chú, bấm "Duyệt bản cuối" → **Đã duyệt**; bấm "Tải MP4" | File tải về trùng từng byte với file trên máy chủ |

Không có thao tác dòng lệnh, JSON hay TSV nào giữa lúc tạo tài khoản và lúc tải MP4.

## Những gì người duyệt sửa (thật, trong lần chạy này)

- **Người nói:** máy chia 6 nhóm và gợi ý cả 6 đều là nữ, kể cả nhân vật nam Thom. Người duyệt gom 9 câu thành THOM
  (giọng NamMinh), 6 câu thành CELIA (giọng HoaiMy); 4 nhóm vai phụ còn lại được gán các biến thể giọng.
- **Bản dịch:** xưng hô anh/em sai giữa hai nhân vật chính (câu 8, 9, 14, 19, 22), câu 1 dịch sai nghĩa ("Tất đi!" cho
  "And... Action!"), câu 12 do nhận dạng nghe nhầm ("Spirit of Tom, leave it to Celia!" thay vì "Speed it up, Thom!
  Vivacissimo!"), câu 26–28 lủng củng.
- Lịch sử chỉnh sửa ghi 35 dòng: 15 đổi người nói, 11 bản dịch, 8 giọng, 1 xác nhận người nói — mỗi dòng có người,
  thời gian, giá trị trước và sau.

## Ảnh chụp màn hình

`docs/screenshots/`: cài đặt lần đầu, thêm nguồn, xác nhận quyền, tổng quan khi đang xử lý, trang duyệt khi đang sửa,
trang duyệt sau khi xuất lại, video đã duyệt, danh sách video, lịch sử, giao diện điện thoại.

## Lỗi tìm thấy trong lần kiểm thử này và đã sửa

1. Trang duyệt hiển thị sai số phiên bản ở chân trang và làm hỏng việc làm mới CSS/JS (biến bị đè).
2. Khung kiểm tra tự động ghi "Đạt kiểm tra — chờ duyệt" cả khi video đã được duyệt.
3. Thanh menu vỡ thành cột dọc trên màn hình điện thoại.
4. Thiếu cách để người duyệt xác nhận người nói của các câu máy đánh dấu "không chắc" nhưng thật ra đúng: thêm ô
   "Đã kiểm tra người nói của mọi câu".

## Giới hạn và rủi ro còn tồn tại

| Mục | Ghi chú |
|---|---|
| Nhận diện người nói | Vẫn cần người duyệt: lần này máy chia 6 nhóm cho 2 nhân vật chính + vai phụ, và gợi ý giới tính sai cả 6 |
| Giọng đọc | Chỉ có 2 giọng edge-tts (kênh không chính thức, không có điều khoản thương mại) và các biến thể cao độ |
| Hạn mức phút mỗi ngày | Lần xuất lại tính lại toàn bộ thời lượng video vào hạn mức, dù chỉ làm lại vài câu |
| Bản trước khi sửa | Xuất lại ghi đè bản cũ; chưa lưu được các phiên bản để so sánh |
| Tải video lên từ trình duyệt | Chưa có; video vào hệ thống qua nguồn thư mục, danh sách file hoặc kênh |
| Phát hành | Trang "Phát hành" chỉ là chỗ dành sẵn; chưa đăng lên đâu |
| Docker | Có `Dockerfile` và `docker/compose.yml`, chưa build được vì máy thử không có Docker daemon |
| Bảo mật | Chưa có HTTPS tích hợp (cần reverse proxy khi mở ra mạng); chưa có xác thực hai lớp; chưa kiểm thử bảo mật độc lập |
| Hiệu năng | Lồng tiếng 150 s phim mất 442 s trên CPU (2,9 lần thời lượng), Gemma 12B cần ~14 GB RAM |
