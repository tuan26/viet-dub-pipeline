# Quickstart

```bash
pip install -e '.[asr,tts]'
```

Chạy thử không cần mạng (giọng "beep" thay giọng đọc):

```bash
vietdub run clip.mp4 --srt clip.vi.srt --translator none --tts beep --license owned --source "clip của tôi"
```

Chạy thật với Ollama (cần `ollama pull qwen2.5:7b`) và edge-tts:

```bash
vietdub run clip.mp4 --lang zh --license cc-by --source "https://..." --attribution "Tác giả"
```

Kiểm tra: mở `out/clip.vi.mp4`, xem `out/report.json` mục `truncated`.
