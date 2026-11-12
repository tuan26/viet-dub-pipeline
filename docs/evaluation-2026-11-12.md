# Đánh giá đợt 2 — người nói, nhận dạng lời thoại, giọng đọc (2026-11-12)

Máy: 4 nhân CPU, 15 GB RAM, không GPU. Ba clip phim CC-BY (mỗi clip 150 s) giữ nguyên từ đợt trước.
Số liệu gốc: `docs/benchmarks/speakers-2026-11-12.json`, `stt-2026-11-12.jsonl`, `tts-2026-11-12.json`.

## 0. Điều cần biết trước khi đọc số

- **Nhãn người nói là nhãn nháp.** Chúng được gán bằng cách đọc lời thoại, dựa vào hiểu biết về phim và cao độ
  giọng, **không phải bằng cách nghe**. Cần một người nghe xác nhận (`tests/data/speakers/*.json`, chỉ chứa mốc
  thời gian và mã người nói).
- Tears of Steel: chỉ 15/34 câu gán được chắc (hai nhân vật chính); 19 câu của các nhân vật phụ không gán được
  và bị loại khỏi phép đo.
- Elephants Dream lệch hẳn về một nhân vật (19/22 câu), nên "đoán tất cả là một người" đã đạt 86%.
- Tổng cộng 61 câu được chấm trên 4 clip. Chênh lệch vài câu nằm trong sai số.

## 1. Người nói (P0)

### 1.1 So sánh phương án, cùng một bộ câu (mốc thời gian chuẩn)

Cách đo: gán người nói cho từng câu, ghép nhãn tìm được với nhân vật thật sao cho khớp nhiều nhất, đếm số câu đúng.
Mức sàn (đoán tất cả là một người): **42/61 = 69%**. Tất cả chạy máy, không cần token.

| Phương án | Tự đếm số người, ngưỡng 0,75, giọng đã tách | Ghi chú |
|---|---|---|
| WeSpeaker ResNet34-LM (đang dùng trước đây) | 42/61 | Bằng mức sàn: gộp hết về một người |
| WeSpeaker ResNet293-LM | 42/61 | |
| WeSpeaker CAM++ | 42/61 | |
| NVIDIA TitaNet-large | 48/61 | |
| 3D-Speaker ERes2Net (en) | 48/61 | |
| 3D-Speaker CAM++ (zh-en) | 49/61 | |
| pyannote segmentation 3.0 + ResNet34 (qua sherpa-onnx) | 39/61 | Tách quá vụn: 4–11 "người nói" mỗi clip |
| pyannote segmentation 3.0 + ResNet293 | 45/61 | Chậm nhất (33–72 s mỗi clip) |
| pyannote segmentation 3.0 + 4 model còn lại | 24–30/61 | |

Quét ngưỡng cho ba model tốt nhất (tự đếm số người):

| Ngưỡng / nguồn âm | ERes2Net | TitaNet-large | CAM++ zh-en |
|---|---|---|---|
| 0,6 giọng đã tách | 44 | 37 | 50 |
| 0,7 giọng đã tách | 44 | 48 | 50 |
| 0,8 giọng đã tách | 50 | 48 | 52 |
| 0,7 âm gốc | 46 | 46 | 51 |
| **0,8 âm gốc** | **56 (92%)** | 55 | 47 |

Khi cho biết trước số nhân vật (3 clip, 46 câu, mức sàn 32): ERes2Net 43, TitaNet 42, CAM++ zh-en 37, ResNet34 36.

**Chọn:** ERes2Net, ngưỡng 0,8, lấy đặc trưng từ âm gốc (không phải giọng đã tách). Giấy phép: mã 3D-Speaker
Apache-2.0; sherpa-onnx Apache-2.0. Kết quả nhạy với ngưỡng (0,7 → 46, 0,8 → 56) và ngưỡng được chọn trên chính
61 câu này, nên con số 92% là lạc quan.

"pyannote" ở đây là model phân đoạn pyannote 3.0 (MIT) chạy qua sherpa-onnx. Pipeline pyannote 3.1 đầy đủ (cần
token Hugging Face) **chưa chạy**.

### 1.2 Đo trên chính các câu pipeline tạo ra (end-to-end)

| Clip | Trước (ResNet34, lượt chạy cũ) | Sau (ERes2Net, tự động) | Câu máy đánh dấu "không chắc" | Câu sai được đánh dấu |
|---|---|---|---|---|
| Elephants Dream | 18/21, 2 người | 17/21, 3 người | 3/22 | 1/4 |
| Tears of Steel | 11/13, 2 người | 13/15, 2 người (4 nhãn tính cả vai phụ) | 5/28 | 0/2 |
| Sintel | 14/15, 3 người | 17/17, 2 người | 0/19 | 0/0 |
| **Tổng** | **43/49 (88%)** | **47/53 (89%)** | 8/69 (12%) | 1/6 |

- **Trên đường chạy thật, độ chính xác tự động gần như không đổi (88% → 89%).** Sintel tốt lên, Elephants Dream kém đi một câu.
  Mức tăng ở mục 1.1 không chuyển hết sang đây.
- Số lần nhầm nhân vật sau khi đổi: 6/53 câu. Hệ thống luôn gán một người nói cho mọi câu (0% bỏ trống); 16/69
  câu không có nhãn chuẩn để chấm.
- Cờ "không chắc" bắt được 1/6 câu sai: chưa đủ để chỉ soát riêng các câu có cờ.

### 1.3 Giới tính và bước duyệt của người dùng

- Cao độ giọng chỉ còn là **gợi ý** (`suggested_gender`, `pitch_hz`); báo cáo ghi rõ giọng được chọn theo
  "máy gợi ý" hay "người duyệt". Không còn chỗ nào coi nó là kết quả chắc chắn.
- `--review`: chạy đến hết bước nhận diện người nói rồi **dừng** (mã thoát 3), chưa tạo giọng nào, và ghi ra
  `work/review/`:
  - `lines.tsv`: mỗi câu một dòng (mốc thời gian, người nói, dấu `?` nếu máy không chắc, câu gốc, bản dịch);
    sửa được cột người nói và bản dịch, đặt tên nhân vật tuỳ ý;
  - `cast.json`: mỗi người nói một mục; người duyệt điền `gender` hoặc chỉ định `voice`, rồi đặt `reviewed: true`;
  - vài file `.wav` trích câu dài nhất của từng người để nghe.
  Chạy lại đúng lệnh cũ thì pipeline tạo giọng theo bản đã duyệt. Thiếu giới tính/giọng cho một người thì dừng và báo.
- Bản "đã duyệt" của ba clip trong đợt này dùng **nhãn nháp** làm người duyệt; các vai phụ chưa gán được vẫn giữ nhãn máy.

## 2. Nhận dạng lời thoại (P1)

"Sót" = câu phụ đề chuẩn mà máy nhận ra dưới một nửa số từ ở gần đó (chặt hơn cách đếm ở đợt trước, nên con
số 8/34 trước đây nay là 12/34 với cùng cấu hình).

| Model | Âm đầu vào | ToS: sai từ | ToS: sót | ToS: lệch mốc p90 | ToS: thời gian | Sintel: sai từ | Sintel: sót |
|---|---|---|---|---|---|---|---|
| small (mặc định) | âm gốc | 28,0% | 12/34 | 1,40 s | 30 s | 14,1% | 1/15 |
| small | giọng đã tách | 24,8% | 10/34 | 2,05 s | 16 s | 12,8% | 1/15 |
| medium | âm gốc | 24,8% | 10/34 | 1,03 s | 66 s | 15,4% | 2/15 |
| **medium** | **giọng đã tách** | 25,6% | **8/34** | **0,58 s** | 35 s | 15,4% | 1/15 |
| large-v3-turbo | âm gốc | 23,2% | 10/34 | 0,51 s | 77 s | 14,1% | 2/15 |
| large-v3-turbo | giọng đã tách | 25,6% | 9/34 | 0,54 s | 45 s | 12,8% | 1/15 |
| large-v3 | âm gốc | 22,4% | 10/34 | 0,69 s | 147 s | 12,8% | 2/15 |
| large-v3 | giọng đã tách | 24,8% | 10/34 | 0,51 s | 58 s | 12,8% | 1/15 |
| large-v3-turbo, tắt lọc tiếng nói | giọng đã tách | 55,2% | 6/34 | 0,56 s | 65 s | 202,6% | 0/15 |

**Vì sao Tears of Steel sót câu.** Tám câu sót ở mọi model: 3 câu là tiếng hét không thành lời, 3 câu là lệnh
một từ được hét lên, 1 câu bị ngắt giữa chừng, 1–2 câu ngắn cuối clip lẫn trong tiếng động. Model lớn hơn không
cứu được các câu này. Tắt bộ lọc tiếng nói cứu thêm 2 câu nhưng model bịa lời hàng loạt (sai từ 55% và 203%).
Thử nhận dạng lại riêng các khoảng có tiếng người chưa có câu: cứu 1 câu, thêm 1–2 câu thừa → không dùng.

**Kết luận.** Tách nhạc trước khi nhận dạng có lợi đo được (sót 12 → 10, sai từ 28,0% → 24,8% với `small`).
`medium` trên giọng đã tách cho ít câu sót nhất (8) và mốc thời gian tốt hơn hẳn (p90 2,05 → 0,58 s), đổi lại chậm
gấp đôi và sai từ không giảm. Bằng chứng chỉ là 2 câu trên một clip nên **mặc định vẫn là `small`**; với phim nên
dùng `--separate --asr-model medium` (ba bản "sau" trong đợt này dùng cấu hình đó). Elephants Dream không có phụ đề
chuẩn nên không đo được.

## 3. Giọng đọc (P2)

Đo trên 10 câu tiếng Việt tự viết (`tools/tts_eval.py`):

| Engine / giọng | Lỗi | Thời gian tạo mỗi câu | Tốc độ nói | Máy nghe sai |
|---|---|---|---|---|
| edge-tts HoaiMy (nữ) — mốc so sánh | 0/10 | 0,51 s | 3,8 tiếng/giây | 21,7% |
| edge-tts NamMinh (nam) | 0/10 | 0,94 s | 4,1 tiếng/giây | 23,9% |
| Piper vais1000 (nữ, chạy máy) | 0/10 | 2,09 s | 4,6 tiếng/giây | 30,4% |

Tỉ lệ "nghe sai" ở đây cao vì chấm từng câu ngắn riêng lẻ và chưa chuẩn hoá cách viết số; chỉ nên so tương đối
giữa các giọng, không so với con số ở phần phim. Độ tự nhiên chưa đo — cần người nghe các file mẫu.

Điều khoản (đã đọc model card hoặc trang nguồn; giá dịch vụ đám mây **chưa xác minh trên trang chính thức**):

| Engine | Số giọng Việt | Điều khoản thương mại | Đã chạy |
|---|---|---|---|
| edge-tts | 2 | Kênh không chính thức của Microsoft, không có điều khoản cho phép | Có |
| Piper `vais1000` | 1 nữ | Model card: dữ liệu CC-BY 4.0; mã Piper MIT → dùng được khi ghi công | Có |
| Piper `25hours_single` | 1 | Model card: giấy phép dữ liệu "Unknown" → không dùng | Không |
| Piper `vivos` | 65 | Model card: CC BY-NC-SA 4.0 → không dùng thương mại | Không |
| VieNeu-TTS | nhiều giọng mẫu, có nhân bản giọng | Theo trang PyPI: bản 0.5B Apache 2.0, bản 0.3B CC BY-NC 4.0 — cần đọc giấy phép từng bản | Không |
| Azure Speech | chính là 2 giọng của edge-tts | Dịch vụ trả phí có điều khoản; một nguồn thứ ba ghi khoảng 15 USD/1 triệu ký tự | Không (cần khoá) |
| Google Cloud TTS, FPT.AI, Viettel AI, Zalo AI | nhiều giọng (chưa kiểm đếm) | Dịch vụ trả phí; chưa đọc điều khoản | Không (cần khoá) |

Không phương án nào ở đây dùng nhân bản giọng diễn viên; tính năng nhân bản của VieNeu-TTS không được dùng.
**Chưa có engine chạy máy nào vừa nhiều giọng vừa rõ điều khoản thương mại được kiểm chứng trong đợt này.**
Hướng thực tế: một dịch vụ trả phí nhiều giọng (cần bạn cấp khoá để đo) hoặc kiểm tra kỹ giấy phép VieNeu-TTS 0.5B.

## 4. Ba clip, trước và sau (P3)

| | Elephants Dream | Tears of Steel | Sintel |
|---|---|---|---|
| Số câu lồng tiếng: trước → sau | 22 → 22 | 26 → 28 | 16 → 19 |
| Người nói đúng (tự động): trước → sau | 18/21 → 17/21 | 11/13 → 13/15 | 14/15 → 17/17 |
| Câu phải tăng tốc (bản đã duyệt) | 1 | 3 | 1 |
| Câu bị cắt | 0 | 0 | 0 |
| Câu chồng câu kế | 0 | 0 | 0 |
| Máy nghe lại giọng Việt, sai: trước → sau | 1,8% → 1,0% | 8,4% → 4,8% | 9,6% → 8,3% |
| File ra | 15,3 MB, 150,00 s, không lỗi | 20,3 MB, 150,00 s, không lỗi | 20,9 MB, 150,00 s, không lỗi |

Mỗi clip có ba video: `_1_truoc` (kết quả đợt trước), `_2_sau_tu_dong` (cấu hình mới, không ai duyệt),
`_3_sau_da_duyet_vai` (qua bước duyệt, dùng nhãn nháp), kèm đường tiếng Việt riêng của bản đã duyệt.

## 5. Đã chạy thật / chưa chạy / chưa có dữ liệu

- **Chạy thật:** so sánh 6 model người nói × 2 cách trên 4 clip; quét ngưỡng; 4 cỡ Whisper × âm gốc/giọng tách;
  edge-tts và Piper; `--review` dừng và chạy tiếp trên cả 3 clip; 9 video xuất ra.
- **Chưa chạy:** pyannote 3.1 đầy đủ, WhisperX, TTS đám mây, VieNeu-TTS, GPU, nguồn tiếng Trung.
- **Chưa có dữ liệu:** nhãn người nói được người nghe xác nhận; nhãn cho vai phụ của Tears of Steel; phụ đề chuẩn
  của Elephants Dream; đánh giá độ tự nhiên của giọng; soát bản dịch trên phim.
- **Test tự động (89 test):** vẫn dùng nhận dạng/dịch/giọng giả lập; số liệu ở tài liệu này không đến từ test.

## 6. Việc cần người kiểm tra thủ công

1. Nghe ba clip và sửa `tests/data/speakers/*.json` (đặc biệt 19 câu chưa gán của Tears of Steel); chạy lại
   `tools/speaker_eval.py` để có số đáng tin.
2. Nghe so sánh ba bản của mỗi clip: giọng có hợp vai không, hai nhân vật cùng giới có phân biệt được không.
3. Nghe ba file mẫu TTS và cho biết Piper có chấp nhận được không.
4. Đọc soát bản dịch trong `lines.tsv` của một clip.
5. Quyết định có cấp khoá cho một dịch vụ TTS/dịch trả phí để đo hay không.
