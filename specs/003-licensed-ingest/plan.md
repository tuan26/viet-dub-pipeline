# Implementation Plan: Nhập video tự động từ nguồn được phép

**Branch**: `003-licensed-ingest` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

## Summary
Lệnh `vietdub ingest` (search, sync, list, approve, reject, fetch) quản lý một thư viện JSON; lệnh
`vietdub batch` đưa video đã tải qua pipeline lồng tiếng của tính năng 001.

## Technical Context
**Language/Version**: Python ≥ 3.11 (cần `tomllib`)
**Primary Dependencies**: thư viện chuẩn (`urllib`); `yt-dlp` là extra `ingest`
**Storage**: `library/catalog.json`, `library/videos/`, `library/dubbed/`
**Testing**: pytest; nguồn mạng được thay bằng hàm giả theo đúng hình dạng phản hồi thật
**Constraints**: nghỉ 1 giây giữa các yêu cầu (`VIETDUB_REQUEST_DELAY`); user agent đổi được (`VIETDUB_USER_AGENT`)

## Constitution Check
| Nguyên tắc | Đáp ứng |
|---|---|
| I. Nội dung có quyền | Bộ lọc giấy phép ở mọi nguồn; kênh cần bằng chứng; không có trình tải cho trang bất kỳ |
| II. OSS trước | API công khai của Internet Archive, Commons; yt-dlp |
| III. Thay thế được | Mỗi nguồn là một module có hàm `search`; hàm mạng truyền vào được |
| IV. Chạy lại được | Trạng thái từng mục lưu sau mỗi bước; mục lỗi duyệt lại được |
| V. Test | 30 test mới, không cần mạng |

## Project Structure
```text
src/vietdub/ingest/
├── licenses.py   # chuẩn hoá giấy phép → cc0 | public-domain | cc-by | cc-by-sa | None
├── catalog.py    # Item, Catalog (catalog.json)
├── net.py        # HTTP có khoảng nghỉ
├── archive.py    # Internet Archive: tìm, chọn file video
├── commons.py    # Wikimedia Commons
├── ytdlp.py      # YouTube CC-BY, liệt kê kênh, tải
├── channels.py   # sources.toml: kênh đã cấp phép
└── fetch.py      # tải các mục đã duyệt
docs/sources.example.toml
docs/outreach/permission-request.md
```

## Vòng đời một mục
`found` → (người dùng duyệt) `approved` → `fetched` → `dubbed`; lỗi → `failed`; loại → `rejected`.
Mục từ kênh đã cấp phép vào thẳng `approved`.
