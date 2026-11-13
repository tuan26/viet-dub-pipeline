# Tasks

Chỉ đánh dấu xong khi đã chạy thật (trình duyệt hoặc tiến trình thật); "(test)" là chỉ có test tự động.

- [x] T001 Schema có phiên bản, nâng cấp tại chỗ; kết nối lại PostgreSQL
- [x] T002 Nguồn lưu trong cơ sở dữ liệu, `pipeline.toml` chỉ là dữ liệu khởi tạo
- [x] T003 `vietdub auto worker` chạy liên tục, heartbeat, tiến độ; `vietdub serve` giám sát worker
- [x] T004 Tài khoản, vai trò, CSRF, khoá tạm khi sai mật khẩu (test + trình duyệt thật)
- [x] T005 Trang Tổng quan, Video, Chi tiết video, Nguồn, Lịch sử, Tài khoản, Phát hành (chỗ dành sẵn)
- [x] T006 Trang duyệt: hai trình phát, nghe từng câu, sửa dịch/người nói/giọng, nghe thử, lưu, xuất lại
- [x] T007 QC: mức nghiêm trọng/cảnh báo, cờ từng câu, đoạn có thể sót lời thoại
- [x] T008 Kiểm thử end-to-end bằng trình duyệt thật trên một đoạn phim thật (`tools/ui_e2e_part1.mjs`, `part2.mjs`)
- [ ] T009 Docker image được build và chạy thử
- [ ] T010 Tải lên video từ trình duyệt (hiện chỉ qua nguồn thư mục/danh sách/kênh)
- [ ] T011 Đổi giọng bằng engine khác edge-tts trên trang duyệt (Piper, dịch vụ trả phí)
