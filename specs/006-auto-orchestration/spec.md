# Feature Specification: Luồng tự động từ nguồn đến chờ duyệt

**Feature Branch**: `006-auto-orchestration` | **Created**: 2026-11-12 | **Status**: Phase 1 implemented

## User Stories
1. **(P1) Cấu hình nguồn rồi để hệ thống chạy** — Người dùng khai báo nguồn và giới hạn trong `pipeline.toml`;
   `vietdub auto run` tìm video mới, tải, lồng tiếng, kiểm tra và dừng ở trạng thái chờ người duyệt.
   *Kiểm tra*: một thư mục video tự sở hữu → `QC_PASS` hoặc `NEEDS_REVIEW` không cần thao tác tay.
2. **(P1) Nguồn chưa xác minh quyền phải chờ** — Video từ nguồn chưa có căn cứ dừng ở `AWAITING_RIGHTS`.
   *Kiểm tra*: nguồn tìm kiếm không thể đặt `verified`; `auto allow` kèm ghi chú mới cho chạy tiếp.
3. **(P1) Không làm trùng, không mất việc** — Cùng ID hoặc cùng nội dung chỉ xử lý một lần; lỗi tạm thời được thử lại;
   việc bỏ dở được khôi phục.
4. **(P2) Biết chuyện gì đang xảy ra** — `auto status`, `auto log`, trang `dashboard.html`.
5. **(P2) Không vượt giới hạn tài nguyên** — hạn mức phút mỗi ngày, độ dài, dung lượng, đĩa và RAM trống.

## Requirements
- **FR-001**: Trạng thái mọi video nằm trong cơ sở dữ liệu (PostgreSQL; SQLite cho máy đơn).
- **FR-002**: Một video chỉ được một worker xử lý tại một thời điểm.
- **FR-003**: Chống trùng theo ID nguồn và theo SHA-256 nội dung; file của người dùng không bao giờ bị xoá.
- **FR-004**: `rights = "verified"` chỉ hợp lệ với `license = "owned"` hoặc có file bằng chứng; nguồn tìm kiếm luôn chờ duyệt.
- **FR-005**: Lỗi tạm thời thử lại với giãn cách tăng dần tới `max_attempts`; lỗi khác dừng ngay ở `FAILED` kèm lý do.
- **FR-006**: Mọi bước và mọi quyết định của người được ghi vào nhật ký kèm thời gian.
- **FR-007**: Kiểm tra chất lượng tự động phân loại `QC_PASS` / `NEEDS_REVIEW` và ghi lý do.
- **FR-008**: Không có đường nào tới `READY` ngoài lệnh duyệt của người; hệ thống chưa đăng gì lên đâu.
- **FR-009**: `--dry-run` không ghi cơ sở dữ liệu, không tải, không lồng tiếng.
- **FR-010**: Không đăng nhập, không cookie, không xử lý CAPTCHA/DRM, không né giới hạn truy cập của nguồn.

## Ngoài phạm vi đợt này
Giao diện duyệt local, tạo nội dung (9:16, tiêu đề, thumbnail), đăng lên nền tảng. Xem `docs/roadmap-gap-analysis.md`.
