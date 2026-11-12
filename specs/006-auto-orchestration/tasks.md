# Tasks

Chỉ đánh dấu xong khi đã chạy thật; mục chỉ có test tự động ghi rõ "(test)".

## Phase 1 — Auto Ingest & Orchestration
- [x] T001 `auto/store.py`: trạng thái trong PostgreSQL/SQLite, nhận việc nguyên tử — chạy thật trên PostgreSQL 16
- [x] T002 `auto/config.py`: `pipeline.toml`, từ chối `verified` thiếu căn cứ
- [x] T003 `auto/sources.py`: thêm `manifest`, `folder`; dùng lại archive/commons/youtube/channel
- [x] T004 Chống trùng theo ID và SHA-256 — chạy thật
- [x] T005 Tải → lồng tiếng → kiểm tra trong một vòng — chạy thật (clip 50 s và phim 11 phút)
- [x] T006 Nhật ký, thời gian từng bước, lỗi — chạy thật
- [x] T007 `AWAITING_RIGHTS` + `auto allow/deny` có ghi chú — chạy thật
- [x] T008 `auto retry`, `auto redo`, tiếp tục từ kết quả đã có — chạy thật
- [ ] T009 Thử lại tự động có giãn cách; lỗi vĩnh viễn dừng ngay (test; nhánh lỗi vĩnh viễn đã gặp thật)
- [ ] T010 Khôi phục việc worker bỏ dở (test)
- [ ] T011 Hai worker thật chạy song song
- [ ] T012 `auto run --every` chạy liên tục một ngày với nguồn thật
- [ ] T013 Nguồn commons, youtube_cc, channel và tải từ Internet Archive trong luồng tự động

## Phase 2 — QC & Human Review
- [x] T020 `auto/qc.py`: 9–11 phép kiểm, `QC_PASS`/`NEEDS_REVIEW` — chạy thật, bắt được 2 vấn đề thật
- [x] T021 `auto approve/reject` → `READY`/`REJECTED`, ghi vào nhật ký (test + lệnh `allow`, `redo`, `retry` chạy thật)
- [x] T022 Trang trạng thái chỉ đọc `auto dashboard` — chạy thật
- [ ] T023 Giao diện local: xem video, nghe từng câu, sửa dịch/speaker/giọng, xuất lại
- [ ] T024 Lịch sử chỉnh sửa từng câu

## Phase 3, Phase 4
- [ ] Chưa bắt đầu. Xem `docs/roadmap-gap-analysis.md`.
