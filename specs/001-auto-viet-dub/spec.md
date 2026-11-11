# Feature Specification: Tự động lồng tiếng Việt cho video

**Feature Branch**: `001-auto-viet-dub`
**Created**: 2026-11-11
**Status**: Implemented (MVP)
**Input**: "Tự động lồng tiếng Việt cho phim nước ngoài bằng OSS/công cụ miễn phí"

## User Scenarios & Testing

### User Story 1 - Lồng tiếng từ phụ đề có sẵn (Priority: P1)
Người dùng có một video được phép dùng và file phụ đề. Họ chạy một lệnh và nhận video có giọng
đọc tiếng Việt khớp thời điểm từng câu, kèm phụ đề Việt.

**Why this priority**: Đây là lõi giá trị; chạy được mà không cần GPU hay model nhận dạng.
**Independent Test**: Chạy trên clip tổng hợp + SRT, kiểm tra file ra có hình, có tiếng, đúng thời lượng.

**Acceptance Scenarios**:
1. **Given** video và SRT tiếng Việt, **When** chạy với `--translator none`, **Then** có `<tên>.vi.mp4` cùng thời lượng video gốc và `<tên>.vi.srt`.
2. **Given** SRT tiếng nước ngoài và bộ dịch, **When** chạy, **Then** mọi câu được dịch trước khi đọc.
3. **Given** một câu đọc dài hơn khoảng trống của nó, **When** ghép, **Then** câu được tăng tốc tối đa tới giới hạn, chỉ cắt khi vẫn không vừa, và được liệt kê trong báo cáo.

### User Story 2 - Chặn nội dung không rõ quyền (Priority: P1)
Người dùng phải khai báo giấy phép và nguồn; thiếu hoặc giấy phép không cho phép thì công cụ dừng
trước khi xử lý.

**Independent Test**: Chạy thiếu `--license` → mã thoát 2, không tạo thư mục kết quả.

**Acceptance Scenarios**:
1. **Given** không có `--license`, **When** chạy, **Then** báo lỗi và không xử lý gì.
2. **Given** `cc-by-nc` hoặc `cc-by-nd`, **When** chạy, **Then** bị từ chối kèm lý do.
3. **Given** `cc-by` kèm tên tác giả, **When** chạy xong, **Then** `CREDITS.txt` ghi nguồn, giấy phép, tác giả.

### User Story 3 - Lồng tiếng thẳng từ video không phụ đề (Priority: P2)
Công cụ tự nhận dạng lời thoại bằng model mã nguồn mở rồi dịch và lồng tiếng.

**Independent Test**: Chạy trên video có lời thoại thật, không đưa `--srt`.

**Acceptance Scenarios**:
1. **Given** video có lời thoại, **When** chạy không có `--srt`, **Then** lời thoại được nhận dạng kèm mốc thời gian và đi tiếp qua các bước sau.

### User Story 4 - Giữ nhạc nền (Priority: P3)
Với `--separate`, giọng gốc được loại bỏ, nhạc và tiếng động được giữ dưới giọng Việt. Không bật thì
tiếng gốc được hạ nhỏ.

### User Story 5 - Chạy lại và sửa bản dịch (Priority: P2)
Chạy lại cùng lệnh không dịch lại, không đọc lại những câu đã có. Người dùng sửa bản dịch trong thư
mục làm việc rồi chạy lại.

**Independent Test**: Chạy hai lần; lần hai bộ dịch và giọng đọc không được gọi.

### Edge Cases
- Video không có tiếng: vẫn lồng tiếng được nếu có SRT; không có SRT thì báo lỗi.
- Phụ đề vượt quá độ dài video: các câu sau điểm kết thúc bị bỏ.
- Bộ dịch trả về sai số câu: thử lại từng câu; vẫn sai thì dừng, nêu câu lỗi.
- Thiếu FFmpeg hoặc thư viện tuỳ chọn: báo lỗi kèm lệnh cài.

## Requirements

### Functional Requirements
- **FR-001**: Hệ thống PHẢI từ chối chạy khi thiếu khai báo giấy phép/nguồn hoặc giấy phép không cho phép phái sinh/thương mại.
- **FR-002**: Hệ thống PHẢI nhận lời thoại từ file SRT hoặc tự nhận dạng từ âm thanh.
- **FR-003**: Hệ thống PHẢI dịch lời thoại sang tiếng Việt theo lô có ngữ cảnh, hỗ trợ bảng tên riêng/xưng hô.
- **FR-004**: Hệ thống PHẢI tạo giọng đọc tiếng Việt cho từng câu và đặt đúng thời điểm bắt đầu câu gốc.
- **FR-005**: Hệ thống PHẢI khớp thời lượng: cho tràn vào khoảng lặng, tăng tốc tới giới hạn cấu hình, cắt là phương án cuối.
- **FR-006**: Hệ thống PHẢI xuất video giữ nguyên hình, tiếng mới gồm giọng Việt trên nền tiếng gốc hạ nhỏ hoặc nhạc nền đã tách.
- **FR-007**: Hệ thống PHẢI xuất phụ đề Việt, file ghi công và báo cáo lần chạy.
- **FR-008**: Hệ thống PHẢI lưu kết quả từng bước và tiếp tục được khi chạy lại.
- **FR-009**: Mỗi bước PHẢI có một lựa chọn miễn phí, thay được bằng tuỳ chọn dòng lệnh.

### Key Entities
- **Segment**: một câu thoại — số thứ tự, bắt đầu, kết thúc, lời gốc, bản dịch.
- **Rights**: giấy phép, nguồn, tác giả.
- **Placement**: quyết định đặt một câu đọc — bắt đầu, hệ số tốc độ, độ dài, có bị cắt không.
- **Report**: tóm tắt lần chạy.

## Success Criteria
- **SC-001**: Một lệnh duy nhất biến video + phụ đề thành video lồng tiếng Việt, không thao tác tay.
- **SC-002**: Thời lượng video ra lệch video gốc dưới 0,3 giây.
- **SC-003**: Không câu đọc nào chồng lên câu kế tiếp.
- **SC-004**: 100% lần chạy thiếu khai báo quyền bị dừng trước khi xử lý.
- **SC-005**: Chạy lại sau khi đã xong không gọi lại bộ dịch hay giọng đọc.
- **SC-006**: Toàn bộ test chạy được không cần mạng, GPU hay khoá API.

## Assumptions
- Đầu vào là file video trên máy; việc thu thập video từ nguồn được phép là tính năng sau.
- Một giọng đọc cho cả video; phân vai nhiều giọng là tính năng sau.
- Người dùng chịu trách nhiệm về tính đúng đắn của khai báo quyền.
- Website, đăng mạng xã hội, quảng cáo nằm ngoài phạm vi tính năng này.
