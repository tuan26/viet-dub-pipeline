# Feature Specification: Web Dashboard và Human Review

**Feature Branch**: `007-web-dashboard` | **Created**: 2026-11-13 | **Status**: Implemented

## Mục tiêu
Người dùng mở Dashboard trên trình duyệt, xem video được hệ thống tự động xử lý, sửa những chỗ chưa đạt, duyệt và tải
MP4 hoàn chỉnh mà không phải sửa JSON/TSV hay chạy dòng lệnh.

## User Stories
1. **(P1) Quản lý job** — Thấy mọi video theo trạng thái, tiến độ, thời gian, nhật ký, lý do lỗi; thử lại, tạm dừng, tiếp tục.
2. **(P1) Duyệt bản lồng tiếng** — Xem bản gốc và bản lồng tiếng cạnh nhau; nghe từng câu; sửa bản dịch và người nói;
   chọn giọng cho từng nhân vật; nghe thử; lưu; xuất lại chỉ các câu đã sửa; duyệt hoặc từ chối bản cuối.
3. **(P1) Quản lý nguồn** — Thêm, sửa, bật/tắt nguồn; lịch kiểm tra; bằng chứng quyền sử dụng; xác nhận quyền từng video.
4. **(P2) Kiểm tra tự động dễ đọc** — Từng tiêu chí, mức nghiêm trọng/cảnh báo; câu nghi ngờ; đoạn có thể sót lời thoại.
5. **(P2) Kiểm soát truy cập** — Tài khoản và vai trò; thao tác duyệt, xoá, quản lý nguồn và quyền chỉ dành cho vai trò phù hợp.
6. **(P3) Chỗ cho giai đoạn sau** — Trang "Phát hành" liệt kê video đã duyệt; chưa đăng gì.

## Requirements
- **FR-001**: Không có tác vụ nặng nào chạy trong request web; web chỉ đổi trạng thái, worker thực hiện.
- **FR-002**: Mọi thao tác ghi cần đăng nhập, đúng vai trò và mã chống CSRF.
- **FR-003**: Chỉ phục vụ file mà cơ sở dữ liệu trỏ tới; không nhận đường dẫn tuỳ ý từ người dùng.
- **FR-004**: Mỗi chỉnh sửa được ghi: ai, lúc nào, câu nào, trước, sau.
- **FR-005**: Xuất lại chỉ tạo lại giọng cho câu bị sửa hoặc nhân vật đổi giọng.
- **FR-006**: Duyệt bản cuối cần ghi chú; bản còn lỗi nghiêm trọng cần xác nhận thêm.
- **FR-007**: Xác nhận quyền sử dụng chỉ quản trị viên làm được và phải ghi căn cứ.
- **FR-008**: QC_PASS được hiển thị kèm lưu ý rằng nó không chứng minh bản dịch đúng hay quyền đã đủ.
- **FR-009**: Khởi động lại máy hay tiến trình không làm mất dữ liệu; cấu trúc dữ liệu nâng cấp tại chỗ.
- **FR-010**: Cài được trên máy cá nhân không cần GPU; không cần bước build giao diện.

## Success Criteria
- **SC-001**: Một người duyệt hoàn tất được: xác nhận quyền → chờ xử lý → sửa → xuất lại → duyệt → tải MP4, chỉ bằng trình duyệt.
- **SC-002**: Xuất lại sau khi sửa vài câu nhanh hơn nhiều so với lồng tiếng lại từ đầu.
- **SC-003**: Vai trò "Chỉ xem" không thay đổi được gì; "Người duyệt" không quản lý được nguồn, quyền, tài khoản.
