# vietdub Constitution

## Core Principles

### I. Chỉ xử lý nội dung có quyền (KHÔNG THƯƠNG LƯỢNG)
Mọi lần chạy phải có khai báo giấy phép và nguồn gốc video. Giấy phép cấm phái sinh (ND) hoặc
cấm thương mại (NC) bị từ chối. Dự án không chứa trình thu thập (crawler) cho nguồn không cho phép
tải và phát hành lại. Mỗi kết quả kèm file ghi công.

### II. Mã nguồn mở và miễn phí trước
Mỗi bước phải có ít nhất một lựa chọn mã nguồn mở hoặc miễn phí chạy được trên máy cá nhân.
Dịch vụ trả phí chỉ là lựa chọn thêm. License của từng model/dịch vụ được ghi trong research.md.

### III. Các bước độc lập, thay thế được
Nhận dạng, dịch, giọng đọc, tách nhạc là các engine sau một giao diện hàm đơn giản. Phần lõi không
phụ thuộc thư viện ngoài; thư viện nặng là extra tuỳ chọn và được import khi cần.

### IV. Chạy lại được, kiểm tra được
Mỗi bước ghi kết quả ra thư mục làm việc; chạy lại tiếp tục từ bước dang dở. Người dùng sửa được
bản dịch giữa chừng. Mỗi lần chạy xuất report.json (số câu, câu bị tăng tốc, câu bị cắt, thời gian).

### V. Test bằng ffmpeg thật, engine giả
Logic thuần (SRT, khớp thời lượng, quyền, phân tích phản hồi dịch) có unit test. Pipeline có test
tích hợp chạy ffmpeg thật trên clip tổng hợp, với bộ dịch giả và giọng "beep", không cần mạng hay GPU.

## Ràng buộc kỹ thuật
Python ≥ 3.10, FFmpeg cài sẵn. Giao diện là CLI; lỗi người dùng in bằng tiếng Việt, mã thoát 2,
không traceback. Không lưu khoá API trong repo; khoá đọc từ biến môi trường.

## Quy trình
Tính năng mới đi qua spec → plan → tasks trong `specs/NNN-ten/` trước khi code. Một tính năng chỉ
xong khi test qua và quickstart chạy được.

## Governance
Constitution này đứng trên mọi quy ước khác. Sửa đổi cần ghi lý do và tăng phiên bản.

**Version**: 1.0.0 | **Ratified**: 2026-11-11 | **Last Amended**: 2026-11-11
