# Đánh giá chất lượng lồng tiếng trên phim thật — 2026-11-11

> Đợt 2 (người nói, nhận dạng, giọng đọc): `docs/evaluation-2026-11-12.md`. Mục 3 dưới đây đã được thay bằng số đo có nhãn ở đó.

Máy chạy: 4 nhân CPU, 15 GB RAM, không GPU. Mọi con số ghi "đo" đến từ lần chạy thật trên máy này;
"ước tính" và "chưa đo" được ghi rõ.

## 1. Cái gì đã chạy thật

| Lệnh / thành phần | Trạng thái |
|---|---|
| `vietdub run` (nhận dạng → dịch → giọng → khớp → xuất) | Chạy thật: clip tự tạo 50 s và 3 đoạn phim |
| `vietdub batch` | **Chạy thật** trên 3 đoạn phim (thư viện 3 mục, cả 3 chuyển sang `dubbed`). Trước đó chỉ có test với nhận dạng giả + giọng beep |
| faster-whisper `small`, `medium` | Chạy thật |
| Dịch bằng model chạy máy qua máy chủ llama.cpp (Qwen2.5-7B, Gemma 3 12B) | Chạy thật |
| edge-tts, 2 giọng Việt + biến thể cao độ | Chạy thật |
| Demucs tách giọng/nhạc | Chạy thật |
| Nhận diện người nói (WeSpeaker ONNX) | Chạy thật |
| FFmpeg ghép, trộn, xuất | Chạy thật |
| Lệnh `ollama` chính hãng, Gemini, Piper | Chưa chạy. Preset `ollama` trỏ cùng giao thức với máy chủ đã thử, nhưng bản thân Ollama chưa được chạy |
| Tải video từ Internet Archive / Commons / YouTube / kênh | Chưa chạy thật (3 phim thử được tải tay từ download.blender.org) |
| 78 test tự động | Dùng FFmpeg thật, còn nhận dạng/dịch/giọng là giả lập |

## 2. Chất lượng dịch

Bộ test: `tests/data/translation_cases.json`, 39 câu thoại tự viết trong 8 cảnh có ngữ cảnh (Anh và Trung),
chấm tự động bằng mẫu khớp (`vietdub/engines/translation_checks.py`). Chạy bằng `tools/translation_eval.py`.
Kết quả đầy đủ: `docs/benchmarks/translation-2026-11-11.json`.

| Phương án (đo) | Đạt | Phủ định | Thời gian | Số lượng | Tên riêng | Thành ngữ | Xưng hô | Câu còn chữ nước ngoài | Thời gian chạy |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-7B, prompt cũ (hiện trạng trước đây) | 17/39 | 2/5 | 2/5 | 3/6 | 4/6 | 5/11 | 1/6 | 15 | 275 s |
| Qwen2.5-7B, prompt chặt | 18/39 | 2/5 | 2/5 | 5/6 | 4/6 | 4/11 | 1/6 | 14 | 243 s |
| Qwen2.5-7B, prompt chặt + tự dịch lại câu lỗi | 24/39 | 4/5 | 2/5 | 5/6 | 4/6 | 7/11 | 2/6 | 4 | 322 s |
| Gemma 3 12B, prompt cũ | 35/39 | 5/5 | 3/5 | 6/6 | 6/6 | 9/11 | 6/6 | 0 | 437 s |
| **Gemma 3 12B, prompt chặt** | **35/39** | 4/5 | 4/5 | 6/6 | 6/6 | 9/11 | 6/6 | 0 | 447 s |

- Lỗi chính của Qwen 7B: trả lời bằng tiếng Trung thay vì tiếng Việt, kể cả khi nguồn là tiếng Anh.
- Gemma 12B chậm hơn khoảng 1,7 lần và cần gần 14 GB RAM (phải tắt khoá bộ nhớ mới chạy được trên máy 15 GB).
- Qwen2.5-14B: định thử nhưng bỏ vì hết đĩa. Gemini và các API trả phí: chưa thử (cần khoá API).
- Giới hạn của bộ chấm: khớp mẫu, 39 câu, một lần chạy mỗi phương án. Hai mẫu quá chặt đã được nới sau khi
  đọc kết quả (chấp nhận "chưa ai", "một vạn hai") và áp dụng lại cho mọi phương án.
- Trên phim thật: 0 câu chưa dịch ở cả 3 phim. So với phụ đề tiếng Việt chính thức của Sintel, chrF2 = 49,9
  (15 câu, một bản tham chiếu, chỉ mang tính tham khảo). Bản dịch trên phim chưa được người đọc soát.

**Quyết định:** đổi mặc định sang Gemma 3 12B + prompt chặt + nhiệt độ 0, và giữ cơ chế tự dịch lại câu còn chữ nước ngoài.

## 3. Nhiều nhân vật

Phương án đã cân nhắc (chỉ WeSpeaker được chạy):

| Phương án | License | Ghi chú |
|---|---|---|
| **WeSpeaker ResNet34-LM (ONNX) + gom nhóm** — đã làm | CC-BY-4.0 (theo model card), dùng thương mại được khi ghi công | 26 MB, chạy CPU bằng onnxruntime, không cần PyTorch |
| pyannote speaker-diarization-3.1 | MIT, nhưng phải chấp nhận điều khoản trên Hugging Face và có token | Chuẩn phổ biến nhất; chưa thử vì cần token của bạn |
| WhisperX | BSD, bên trong dùng pyannote | Chưa thử |
| NVIDIA NeMo / TitaNet, sherpa-onnx | CC-BY-4.0 / Apache | Chưa thử |

Giọng Việt (chưa kiểm chứng giá và điều khoản, cần xem trang chính thức trước khi dùng thương mại):
edge-tts là kênh không chính thức, chỉ có 1 giọng nữ + 1 giọng nam; các nhân vật cùng giới được phân biệt bằng
lệch cao độ/tốc độ. Azure Speech (bản chính thức của cùng hai giọng), Google Cloud TTS (nhiều giọng vi-VN),
VieNeu-TTS (được ghi là Apache 2.0, chưa xác minh), Piper (offline) là các hướng cho bản thương mại.

Kết quả đo:

| Clip | Số nhân vật thật | Bản đầu (ngưỡng 0,55, ngữ cảnh 1 s) | Sau khi chỉnh (ngưỡng 0,75, ngữ cảnh 2,5 s, gộp nhóm 1 câu) |
|---|---|---|---|
| Clip tự tạo (có nhãn) | 2 | 2, đúng 9/9 câu | 2, đúng 9/9 câu |
| Elephants Dream | 2 (đều nam) | 13 "người nói", tất cả xếp là nữ | 2, nhưng chia 20/2 câu — không hợp lý với hội thoại qua lại; giới tính đoán sai, phải dùng `--cast` |
| Tears of Steel | khoảng 4–5 (ước lượng của người viết) | 21 | 3 |
| Sintel | 2 | 11 | 3 (1 nam 8 câu, 2 nhóm nữ 6 + 2 câu) |

Phim thật không có nhãn người nói từng câu nên **độ chính xác từng câu chưa đo được**. Kết luận: nhận diện tự động
đủ để tạo ra nhiều giọng, chưa đủ tin cậy để phát hành không soát. Nguyên nhân đo được: câu thoại phim ngắn
(trung vị 1,1–1,6 s) và đoán giới tính theo cao độ sai với giọng diễn xuất. Cách dùng hiện tại: `--speakers N`
khi biết số nhân vật, `--cast S1=male,...` để sửa giới tính, hoặc sửa `speaker` trong `work/segments.json`.

## 4. Ba đoạn phim thật

Nguồn: download.blender.org, giấy phép CC-BY, mỗi đoạn 150 giây. Lưu ý: riêng các file nhạc phim (OST) của
Tears of Steel có giấy phép CC BY-ND; ở đây chỉ dùng bản phim, không dùng file OST.

| | Elephants Dream (ít nhân vật) | Tears of Steel (nhiều nhân vật) | Sintel (nhạc + hiệu ứng) |
|---|---|---|---|
| Nhận dạng: tỉ lệ sai từ, `small` / `medium` | không có phụ đề chuẩn | 28,0% / 24,8% | 14,1% / 15,4% |
| Số câu nhận ra / số câu phụ đề chuẩn | 22 / — | 26 / 34 | 16 / 15 |
| Nhận dạng trên giọng đã tách nhạc (Sintel) | — | — | 14,1% (không khác bản chưa tách) |
| Câu chưa dịch | 0 | 0 | 0 |
| Câu phải tăng tốc: trước → sau khi cắt khoảng lặng | 7 → 0 | 14 → 2 | 3 → 1 |
| Câu bị cắt: trước → sau | 0 → 0 | 6 → 0 | 1 → 1 |
| Giọng Việt phát trễ so với mốc (trung vị) | 0,25 → 0,02 s | 0,20 → 0,02 s | 0,25 → 0,02 s |
| Câu chồng lên câu kế | 0 | 0 | 0 |
| Giọng Việt nghe lại bằng máy: tỉ lệ nghe sai | 1,8% | 8,4% | 9,6% |
| File ra | 15,3 MB, 150,00 s, giải mã không lỗi | 20,3 MB, 150,00 s, không lỗi | 20,9 MB, 150,00 s, không lỗi |

Độ tự nhiên của giọng, chất lượng tách nhạc và độ hợp vai **chưa được đo** — cần người nghe.
`medium` không tốt hơn `small` rõ rệt mà chậm gấp đôi nên giữ `small`.

## 5. Thời gian và chi phí (đo, lượt chạy đầy đủ đầu tiên bằng `batch`)

| Bước | Elephants Dream | Tears of Steel | Sintel |
|---|---|---|---|
| Tách nhạc (Demucs) | 95,7 s | 73,5 s | 82,1 s |
| Nhận dạng | 18,5 s | 21,3 s | 15,1 s |
| Dịch (Gemma 12B) | 148,8 s | 183,8 s | 111,6 s |
| Nhận diện người nói | 1,5 s | 1,7 s | 1,4 s |
| Giọng đọc | 60,8 s | 75,8 s | 36,1 s |
| Ghép và xuất | 7,5 s | 8,4 s | 7,5 s |
| **Tổng** | **334 s (2,2×)** | **365 s (2,4×)** | **255 s (1,7×)** |

- Chi phí API (đo): 0 đồng.
- Ước tính 100 tập × 5 phút: khoảng 17–20 giờ máy CPU, nếu tỉ lệ 1,7–2,4× giữ nguyên; chưa đo với GPU.
- Lỗi vận hành gặp phải: edge-tts rớt yêu cầu lẻ tẻ (đã tự thử lại, không lần chạy nào hỏng); máy chủ dịch bị
  hệ thống tắt 2 lần vì thiếu RAM khi chạy Gemma 12B với khoá bộ nhớ.

## 6. Lỗi tìm thấy trong đợt này và đã sửa
1. Dịch: câu trả về còn chữ Trung → tự dịch lại từng câu, câu không cứu được ghi vào `untranslated`.
2. Giọng đọc có khoảng lặng gần 1 giây quanh mỗi clip, làm câu 1–2 từ không vừa chỗ → cắt khoảng lặng trước khi khớp.
3. Nhận diện người nói tách quá vụn trên phim thật → ngữ cảnh 2,5 s, ngưỡng 0,75, gộp nhóm chỉ có 1 câu.
4. Mốc thời gian câu lấy theo từng từ thay cho theo đoạn; tách câu tại khoảng nghỉ ≥ 0,7 s.
5. Bước rút gọn câu không đọc được phản hồi dạng JSON object của Gemma → nhận mọi dạng phản hồi.
6. Khi tách nhạc, nhận dạng và nhận diện người nói dùng giọng đã tách.

## 7. Đề xuất

| Tiêu chí | Lựa chọn | Lý do |
|---|---|---|
| Chất lượng dịch | Gemma 3 12B, prompt chặt | 35/39 so với 18/39; bước tiếp theo đáng thử là một API lớn hơn trên cùng bộ test |
| Tốc độ | GPU 12 GB trở lên | Dịch và tách nhạc chiếm khoảng 70% thời gian; chưa đo trên GPU |
| Chi phí | Giữ toàn bộ chạy máy | 0 đồng dịch vụ |
| Nhiều nhân vật | Tự động + người soát vai (`--cast`, sửa `segments.json`); thử pyannote khi có token | Tự động hiện chưa đủ tin cậy |
| Giọng thương mại | Chuyển khỏi edge-tts sang dịch vụ có điều khoản rõ | edge-tts không chính thức và chỉ có 2 giọng |
| Kiến trúc | Giữ nguyên: mỗi bước là một hàm truyền vào `Job` | Đợt này thêm 3 engine mà không sửa các engine cũ |
