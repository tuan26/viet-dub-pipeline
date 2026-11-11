# Feature Specification: Nhập video tự động từ nguồn được phép

**Feature Branch**: `003-licensed-ingest`
**Created**: 2026-11-11
**Status**: Implemented
**Input**: "Tự tìm và tải video để lồng tiếng, theo hai hướng: nguồn có giấy phép mở và kênh đã cấp phép"

## User Scenarios & Testing

### User Story 1 - Tìm video có giấy phép mở (Priority: P1)
Người dùng gõ từ khoá; hệ thống tìm trên Internet Archive, Wikimedia Commons hoặc YouTube, chỉ giữ
video có giấy phép cho phép phái sinh và thương mại, ghi vào thư viện ở trạng thái chờ duyệt.

**Independent Test**: Tìm một từ khoá trên Internet Archive; mọi mục trả về có giấy phép thuộc nhóm được nhận.

**Acceptance Scenarios**:
1. **Given** kết quả có cả CC0, CC-BY-NC và không rõ giấy phép, **When** tìm, **Then** chỉ mục CC0 vào thư viện.
2. **Given** video CC-BY không có tên tác giả, **When** tìm, **Then** bị bỏ vì không ghi công được.
3. **Given** một video đã có trong thư viện, **When** tìm lại, **Then** không tạo mục trùng.

### User Story 2 - Theo dõi kênh đã cấp phép (Priority: P1)
Người dùng khai báo các kênh/studio đã cho phép, kèm nội dung cấp phép và file bằng chứng. Hệ thống
lấy danh sách tập mới của đúng các kênh đó.

**Independent Test**: Khai báo một kênh thiếu file bằng chứng → bị từ chối; có đủ → tập mới vào thư viện.

**Acceptance Scenarios**:
1. **Given** kênh thiếu `permission` hoặc file `evidence` không tồn tại, **When** đồng bộ, **Then** dừng và nêu kênh nào thiếu gì.
2. **Given** kênh hợp lệ có 2 tập mới, **When** đồng bộ, **Then** 2 mục vào thư viện ở trạng thái đã duyệt, mang thông tin cấp phép.

### User Story 3 - Duyệt rồi mới tải (Priority: P1)
Mục tìm được từ nguồn mở phải được người dùng duyệt trước khi tải, vì giấy phép trên các trang này do
người đăng tự khai và có thể sai.

**Acceptance Scenarios**:
1. **Given** mục chờ duyệt, **When** chạy tải, **Then** mục đó không được tải.
2. **Given** 2 mục đã duyệt, một mục tải lỗi, **When** chạy tải, **Then** mục kia vẫn tải xong; mục lỗi ghi lý do và duyệt lại được.

### User Story 4 - Lồng tiếng hàng loạt (Priority: P2)
Một lệnh lồng tiếng mọi video đã tải, tự lấy giấy phép, nguồn, tác giả từ thư viện để ghi công.

### Edge Cases
- Nguồn giới hạn tần suất (HTTP 429): báo lỗi rõ, không thử dồn dập.
- Mục Internet Archive không có file video: đánh dấu lỗi.
- `sources.toml` sai cú pháp: báo dòng lỗi.

## Requirements
- **FR-001**: Hệ thống CHỈ nhận video có giấy phép CC0, phạm vi công cộng, CC-BY, CC-BY-SA, hoặc thuộc kênh có khai báo cấp phép kèm bằng chứng.
- **FR-002**: Giấy phép thiếu, không nhận ra, hoặc có NC/ND PHẢI bị loại.
- **FR-003**: Hệ thống KHÔNG có cơ chế tải từ trang bất kỳ ngoài ba nguồn mở và danh sách kênh đã cấp phép.
- **FR-004**: Mục từ nguồn mở PHẢI qua bước duyệt của người dùng trước khi tải.
- **FR-005**: Thư viện PHẢI chống trùng theo mã nguồn và lưu trạng thái từng mục.
- **FR-006**: Mỗi mục PHẢI mang đủ thông tin để ghi công: nguồn, giấy phép, tác giả, nội dung cấp phép.
- **FR-007**: Hệ thống PHẢI gọi nguồn một cách chừng mực: có khoảng nghỉ giữa các yêu cầu, có giới hạn số mục.
- **FR-008**: Lỗi ở một mục KHÔNG được dừng các mục còn lại.

### Key Entities
- **Item**: một video trong thư viện — mã, nguồn, tiêu đề, trang gốc, giấy phép, tác giả, ngôn ngữ, cấp phép, trạng thái, đường dẫn file, lỗi.
- **Channel**: một kênh đã cấp phép — tên, URL, nội dung cấp phép, file bằng chứng, tên ghi công, ngôn ngữ.

## Success Criteria
- **SC-001**: 100% mục vào thư viện có giấy phép thuộc nhóm được nhận.
- **SC-002**: Từ từ khoá đến video lồng tiếng chỉ cần 4 lệnh: tìm, duyệt, tải, lồng tiếng.
- **SC-003**: Tập mới của kênh đã cấp phép vào thư viện bằng 1 lệnh, không cần duyệt lại từng tập.
- **SC-004**: Tìm lại cùng từ khoá không tạo mục trùng.

## Assumptions
- Giấy phép trên Internet Archive và YouTube do người đăng tự khai; người dùng chịu trách nhiệm kiểm tra khi duyệt.
- Tình trạng phạm vi công cộng khác nhau theo từng nước; hệ thống không tự phán đoán điều này.
- Chạy theo lịch (cron) và trang duyệt trên web là tính năng sau.
