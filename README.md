# vietdub

Tự động lồng tiếng Việt cho video bằng công cụ mã nguồn mở và miễn phí:
nhận dạng lời thoại → dịch → tạo giọng đọc → khớp thời lượng → trộn tiếng.

Dự án được xây theo quy trình [spec-kit](https://github.com/github/spec-kit):
nguyên tắc ở `.specify/memory/constitution.md`, đặc tả và kế hoạch ở `specs/`.

## Cài đặt

Cần Python ≥ 3.10 và FFmpeg.

```bash
pip install -e '.[asr,tts]'
```

Thêm `separate` nếu muốn giữ nhạc nền bằng Demucs (nên có GPU).

## Dùng

Video có lời thoại tiếng Trung, dịch bằng Ollama chạy trên máy, đọc bằng edge-tts:

```bash
vietdub run phim.mp4 --lang zh --license cc-by --source "https://..." --attribution "Tên tác giả"
```

Đã có phụ đề tiếng Việt, chỉ cần lồng tiếng:

```bash
vietdub run phim.mp4 --srt phim.vi.srt --translator none --license owned --source "video của tôi"
```

Kết quả nằm trong `out/`: `phim.vi.mp4`, `phim.vi.srt`, `CREDITS.txt`, `report.json`.
Chạy lại lệnh cũ sẽ tiếp tục từ bước dang dở; sửa bản dịch trong `out/work/segments.json`,
xoá `out/work/clips/` rồi chạy lại để đọc lại theo bản đã sửa.

| Bước | Lựa chọn | Tuỳ chọn |
|---|---|---|
| Nhận dạng lời thoại | faster-whisper, hoặc phụ đề có sẵn | `--asr-model`, `--srt` |
| Dịch | Ollama (máy mình), Gemini (`GEMINI_API_KEY`), endpoint OpenAI-compatible bất kỳ | `--translator`, `--model`, `--base-url`, `--glossary` |
| Giọng đọc | edge-tts (online), Piper (offline), beep (chạy thử) | `--tts`, `--voice` |
| Nhạc nền | hạ nhỏ tiếng gốc, hoặc Demucs tách giọng | `--separate` |

## Nhiều nhân vật, nhạc nền

```bash
pip install -e '.[asr,tts,speakers,separate]'
```

Tải model người nói (26 MB) về thư mục `models/`:

```bash
curl -L -o models/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx
```

```bash
vietdub run phim.mp4 --lang en --separate --asr-model medium --speakers --review --license cc-by --source "https://..." --attribution "Tác giả"
```

- `--speakers` gán mỗi người nói một giọng; thêm số (`--speakers 2`) nếu biết số nhân vật.
- `--review` dừng trước khi tạo giọng và ghi `out/work/review/`: nghe các file `.wav`, sửa cột `speaker` trong
  `lines.tsv`, điền `gender` hoặc `voice` cho từng người trong `cast.json`, đặt `"reviewed": true`, rồi chạy lại đúng lệnh đó.
- Không có `--review` thì máy tự gán vai và chọn giọng theo gợi ý từ cao độ; báo cáo ghi rõ là chưa có người duyệt.
- `--separate` dùng Demucs bỏ giọng gốc, giữ nhạc và hiệu ứng, và giúp nhận dạng lời thoại tốt hơn.

Gán vai tự động đúng khoảng 89% số câu trên ba clip thử (nhãn nháp, chưa được người nghe xác nhận), nên nên dùng
`--review` trước khi phát hành. Số đo: `docs/evaluation-2026-11-12.md` và `docs/quality-evaluation.md`.
Model dịch mặc định là `gemma3:12b` (35/39 trên bộ test dịch, so với 18/39 của `qwen2.5:7b`); cần khoảng 14 GB RAM.

## Dashboard web và luồng tự động

```bash
pip install -e '.[all]'
```

```bash
vietdub serve --config pipeline.toml
```

Mở http://127.0.0.1:8800: lần đầu tạo tài khoản quản trị, sau đó mọi việc làm trên trình duyệt — thêm nguồn, xác nhận
quyền sử dụng, theo dõi worker, duyệt bản lồng tiếng (nghe từng câu, sửa bản dịch, người nói, giọng), xuất lại, duyệt bản
cuối và tải MP4. Hướng dẫn đầy đủ: `docs/INSTALL.md`.

| Trạng thái | Nghĩa |
|---|---|
| Chờ xác minh quyền | Nguồn chưa có căn cứ về quyền sử dụng; quản trị viên xác nhận từng video |
| Chờ tải / Chờ lồng tiếng / Chờ kiểm tra | Trong hàng đợi của worker |
| Cần duyệt | Kiểm tra tự động thấy điểm cần xem |
| Đạt kiểm tra — chờ duyệt | Qua mọi tiêu chí tự động, vẫn cần người duyệt |
| Đã duyệt | Người duyệt đã chấp nhận bản cuối |
| Lỗi | Không tự khắc phục được, hoặc đã thử lại đủ số lần |

Hệ thống chưa đăng gì lên nền tảng nào. Hiện trạng so với mục tiêu: `docs/roadmap-gap-analysis.md`.
Các lệnh `vietdub auto ...` vẫn dùng được cho máy chủ không có giao diện.

## Tự tìm và tải video

Cài thêm `pip install -e '.[ingest]'`. Có hai hướng, chi tiết ở `specs/003-licensed-ingest/quickstart.md`:

- **Nguồn giấy phép mở** — Internet Archive, Wikimedia Commons, YouTube Creative Commons. Chỉ giữ
  CC0, phạm vi công cộng, CC-BY, CC-BY-SA. Mục tìm được phải được bạn duyệt trước khi tải.
- **Kênh đã cấp phép** — khai báo kênh trong `sources.toml` kèm file bằng chứng cấp phép
  (mẫu: `docs/sources.example.toml`; mẫu thư xin phép: `docs/outreach/permission-request.md`).

```bash
vietdub ingest search archive "short film" --limit 10
```

```bash
vietdub ingest approve archive:<mã>
```

```bash
vietdub ingest sync
```

```bash
vietdub ingest fetch
```

```bash
vietdub batch --lang zh
```

Không có trình tải cho trang phim bất kỳ: video chỉ vào thư viện qua hai hướng trên.

## Quyền sử dụng nội dung

Công cụ chỉ chạy khi bạn khai báo `--license` và `--source`. Giấy phép được nhận:
`owned`, `licensed`, `public-domain`, `cc0`, `cc-by`, `cc-by-sa`. Giấy phép có NC hoặc ND bị từ chối.
Việc khai báo đúng là trách nhiệm của người dùng. Lưu ý edge-tts là dịch vụ không chính thức và
một số giọng nhân bản (XTTS) có license phi thương mại — kiểm tra trước khi dùng thương mại.

## Phát triển

```bash
pip install -e '.[dev]'
```

```bash
pytest
```
