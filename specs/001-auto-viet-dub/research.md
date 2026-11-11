# Research: lựa chọn công cụ

| Bước | Quyết định | Lý do | Đã cân nhắc |
|---|---|---|---|
| Nhận dạng | faster-whisper (MIT) | Nhanh, chạy được CPU, có VAD | WhisperX (thêm căn từ, phân người nói — để dành cho phân vai) |
| Dịch | Endpoint OpenAI-compatible; preset Ollama và Gemini | Một cài đặt dùng cho model chạy máy mình lẫn free tier | NLLB (dịch từng câu, mất ngữ cảnh xưng hô) |
| Giọng đọc | edge-tts mặc định; Piper offline | Dễ nhất, nghe ổn; Piper không cần mạng | F5-TTS tiếng Việt, viXTTS (nhân bản giọng, cần GPU) |
| Tách nhạc | Demucs (MIT), tuỳ chọn | Chất lượng tốt; nặng nên không bật mặc định | UVR |
| Ghép | FFmpeg + module `wave` chuẩn | Không thêm phụ thuộc | pydub, numpy |

## Lưu ý license cần kiểm tra lại trước khi dùng thương mại
- edge-tts gọi dịch vụ của Microsoft không qua kênh chính thức.
- XTTS/viXTTS: Coqui Public Model License, phi thương mại.
- Tên model mặc định (`qwen2.5:7b`, `gemini-2.5-flash`) có thể đã cũ; đổi bằng `--model`.

## Khớp thời lượng
Tiếng Việt đọc thường dài hơn câu gốc tiếng Trung. Thứ tự xử lý: tràn vào khoảng lặng trước câu kế →
tăng tốc (mặc định tối đa 1,4×, trên mức này nghe gấp) → cắt kèm fade và báo trong report để người
dùng rút gọn bản dịch.
