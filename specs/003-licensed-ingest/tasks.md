# Tasks: Nhập video tự động từ nguồn được phép

## Phase 1: Foundational
- [x] T001 [P] Chuẩn hoá giấy phép `src/vietdub/ingest/licenses.py` + `tests/unit/test_licenses.py`
- [x] T002 [P] `Item`, `Catalog` trong `src/vietdub/ingest/catalog.py`
- [x] T003 [P] HTTP có khoảng nghỉ `src/vietdub/ingest/net.py`

## Phase 2: US1 — Nguồn giấy phép mở (P1)
- [x] T004 [P] [US1] Internet Archive `src/vietdub/ingest/archive.py`
- [x] T005 [P] [US1] Wikimedia Commons `src/vietdub/ingest/commons.py`
- [x] T006 [P] [US1] YouTube CC-BY `src/vietdub/ingest/ytdlp.py`
- [x] T007 [US1] Lệnh `ingest search` trong `src/vietdub/cli.py`

## Phase 3: US2 — Kênh đã cấp phép (P1)
- [x] T008 [US2] `sources.toml`, kiểm tra bằng chứng, `sync` trong `src/vietdub/ingest/channels.py`
- [x] T009 [US2] Lệnh `ingest sync`; mẫu `docs/sources.example.toml`
- [x] T010 [US2] Mẫu thư xin phép `docs/outreach/permission-request.md`

## Phase 4: US3 — Duyệt rồi mới tải (P1)
- [x] T011 [US3] Lệnh `ingest list|approve|reject`
- [x] T012 [US3] `src/vietdub/ingest/fetch.py` và lệnh `ingest fetch`

## Phase 5: US4 — Lồng tiếng hàng loạt (P2)
- [x] T013 [US4] Lệnh `batch`

## Phase 6: Kiểm chứng với nguồn thật
- [x] T014 Tìm và đọc metadata trên Internet Archive thật
- [ ] T015 Tải file thật từ Internet Archive
- [ ] T016 Tìm và tải trên Wikimedia Commons thật
- [ ] T017 Tìm YouTube CC-BY và đồng bộ một kênh thật bằng yt-dlp
- [ ] T018 Chuyển mã video WebM/Ogg trước khi ghép MP4
- [ ] T019 Chạy `ingest sync` + `fetch` + `batch` theo lịch
