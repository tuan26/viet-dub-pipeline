# Gap analysis: hiện trạng so với hệ thống tự động mục tiêu (cập nhật 2026-11-13)

Diễn biến và số đo của lần chạy thật: `docs/auto-e2e-2026-11-12.md`.
Kiểm chứng Phase 1 bằng tiến trình thật (2026-11-13): `docs/phase1-verification-2026-11-13.md` — 8/8 kịch bản đạt.
Dashboard và trang duyệt (2026-11-13): `specs/007-web-dashboard/`, hướng dẫn cài đặt `docs/INSTALL.md`.

Luồng mục tiêu: Auto Crawler → Download/Ingest → AI Dubbing → Automated QC → Optional Human Review →
Video Processing → Publish YouTube/Facebook/TikTok.

Cột "Kiểm chứng": **thật** = đã chạy với dữ liệu và dịch vụ thật; **test** = chỉ có test tự động với phần giả lập;
**chưa** = chưa chạy lần nào.

## Phase 1 — Auto Ingest & Orchestration

| Yêu cầu | Trước đợt này | Sau đợt này | Kiểm chứng |
|---|---|---|---|
| 1. Kiểm tra nguồn theo lịch | Lệnh tay `ingest search/sync` | `vietdub auto run --every N`, mỗi nguồn có `interval_minutes` | Một vòng: thật. Lặp theo chu kỳ nhiều giờ: chưa |
| 2. Phát hiện video mới, metadata, giấy phép | Có bộ lọc giấy phép, cổng quyền | Dùng lại; thêm nguồn `manifest`, `folder` | Folder, manifest, Internet Archive: thật. Commons, YouTube, kênh: chưa |
| 3. Chống trùng theo source ID và content hash | Chỉ theo ID | Khoá chính theo ID + SHA-256 nội dung → `DUPLICATE` | Thật |
| 4. Tải và đưa vào hàng đợi | Tải tay | Hàng đợi trạng thái trong PostgreSQL | Tải trực tiếp: thật. Qua yt-dlp: chưa |
| 5. Tự gọi pipeline lồng tiếng | `batch` chạy tay | Bước `dub` gọi engine hiện có, không sửa engine | Thật |
| 6. Trạng thái, log, thời gian, lỗi | `catalog.json`, `report.json` | Bảng `videos`, `events`, `sources` | Thật |
| 7. Retry, resume, tránh xử lý trùng | Resume trong một video | Lỗi tạm thời thử lại có giãn cách; lỗi vĩnh viễn dừng ngay; nhận việc nguyên tử; heartbeat; khôi phục việc bỏ dở | Thật (2026-11-13): hai worker song song, tự thử lại, kill -9, khởi động lại PostgreSQL |
| 8. Nguồn chưa xác minh phải chờ duyệt | Mục `found` chờ `approve` | `AWAITING_RIGHTS`; `rights = "verified"` bị từ chối nếu thiếu căn cứ | Thật |

## Phase 2 — Automated QC & Human Review

| Yêu cầu | Hiện trạng | Kiểm chứng |
|---|---|---|
| 1. Kiểm tra sót thoại, chưa dịch, speaker, âm thanh, thời lượng, lỗi MP4 | `auto/qc.py`: 9–11 tiêu chí, mức nghiêm trọng/cảnh báo, cờ từng câu, đoạn có thể sót | Thật |
| 2. Phân loại QC_PASS / NEEDS_REVIEW | Có, kèm lưu ý QC_PASS không chứng minh bản dịch đúng hay quyền đủ | Thật |
| 3. Giao diện local xem video, nghe từng câu, sửa dịch/speaker/giọng | Dashboard web (`vietdub serve`) | Thật, bằng trình duyệt (Playwright) |
| 4. Xuất lại sau khi sửa | Chỉ làm lại câu bị sửa | Thật |
| 5. Lịch sử chỉnh sửa | Bảng `edits`: ai, lúc nào, câu nào, trước/sau; quyết định ghi trong nhật ký | Thật |
| 6. Không tự đăng khi chưa duyệt | Chưa có chức năng đăng; `READY` chỉ qua người duyệt | Thật |

## Phase 3 — Content Production: chưa làm

Chưa có: bản 9:16, trailer, tiêu đề/mô tả/hashtag, thumbnail, kiểm tra "giấy phép có cho phép cắt không"
(hiện cổng quyền chỉ phân biệt được/không được phái sinh).

## Phase 4 — Multi-platform Publishing: chưa làm

Chưa có: YouTube Data API, Facebook Graph API, TikTok Content Posting API, OAuth, lịch đăng, quota.
Cần bạn tạo ứng dụng và cấp quyền trên từng nền tảng; TikTok yêu cầu ứng dụng được duyệt mới đăng công khai được.

## Yêu cầu kiến trúc

| Yêu cầu | Hiện trạng |
|---|---|
| Python, PostgreSQL, FFmpeg | Có. PostgreSQL 16 đã chạy thật; SQLite cho máy đơn và test |
| Giữ engine, không viết lại | Engine không bị sửa trong đợt này ngoài việc phân loại lỗi tạm thời |
| Module độc lập, thay được | `auto/` gồm store, config, sources, orchestrator, qc, dashboard; các bước truyền vào qua `Steps` |
| Dashboard | Web app có đăng nhập và vai trò (`vietdub serve`) |
| Dry-run | `auto run --dry-run`: chỉ liệt kê, không ghi/tải/lồng tiếng. Dry-run cho việc đăng: chưa (chưa có đăng) |
| Kiểm soát chi phí, CPU/RAM, dung lượng, số worker | Hạn mức phút/ngày, giới hạn độ dài và dung lượng, ngưỡng đĩa và RAM trống, số worker, số luồng CPU và mức nice. Đã chạy thật, trừ việc đo hiệu quả giới hạn CPU |
| Không vượt CAPTCHA, DRM, giới hạn truy cập | Chỉ dùng API công khai, yt-dlp không cookie, file người dùng khai báo. Không có mã nào xử lý CAPTCHA/DRM |

## Thứ tự đề xuất tiếp theo
1. Chạy `vietdub serve` liên tục vài ngày với nguồn thật của bạn; build và chạy thử Docker trên máy có Docker.
2. Phase 3 (tạo nội dung) bắt đầu từ bản 9:16 và thumbnail, có bước duyệt riêng.
3. Phase 4 bắt đầu từ YouTube ở chế độ chạy thử và đăng riêng tư.
