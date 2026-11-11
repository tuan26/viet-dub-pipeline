# CLI Contract

```
vietdub run VIDEO --license L --source S [--attribution A] [-o OUT]
            [--srt FILE] [--lang CODE] [--asr-model NAME]
            [--translator ollama|gemini|none] [--model NAME] [--base-url URL] [--glossary FILE]
            [--tts edge|piper|beep] [--voice NAME|FILE] [--separate] [--max-speed X] [--force]
```

**Kết quả trong OUT**: `<tên>.vi.mp4`, `<tên>.vi.srt`, `CREDITS.txt`, `report.json`, `work/`.

**Mã thoát**: 0 thành công; 2 lỗi người dùng xử lý được (thông báo ở stderr, bắt đầu bằng `Lỗi:`).

**Giao diện engine**
- giọng đọc: `(text, đường_dẫn_không_đuôi) -> file âm thanh`
- dịch: `(system, user) -> str` chứa mảng JSON các chuỗi
- nhận dạng: `(audio.wav) -> list[Segment]`
- tách nhạc: `(audio.wav, workdir) -> background.wav`
