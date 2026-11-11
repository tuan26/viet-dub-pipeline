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

Tải model người nói (26 MB, CC-BY-4.0) về `models/voxceleb_resnet34_LM.onnx` từ
https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM rồi:

```bash
vietdub run phim.mp4 --lang en --speakers --separate --license cc-by --source "https://..." --attribution "Tác giả"
```

- `--speakers` gán mỗi người nói một giọng; thêm số (`--speakers 2`) nếu biết số nhân vật.
- `--cast S1=male,S2=female` sửa giới tính giọng khi máy đoán sai (xem `speakers` trong `report.json`).
- `--separate` dùng Demucs bỏ giọng gốc, giữ nhạc và hiệu ứng.

Nhận diện người nói tự động chưa đủ tin cậy trên phim thật; số đo và giới hạn ở `docs/quality-evaluation.md`.
Model dịch mặc định là `gemma3:12b` (35/39 trên bộ test dịch, so với 18/39 của `qwen2.5:7b`); cần khoảng 14 GB RAM.

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
