# Kiểm chứng end-to-end ngày 2026-11-11

> Đợt kiểm chứng đầu tiên (clip tự tạo). Kết quả trên phim thật, `vietdub batch` chạy thật và so sánh model dịch
> nằm ở `docs/quality-evaluation.md`; ở đó thay thế các mục "chưa chạy" bên dưới.

Một lần chạy thật trên máy 4 nhân CPU, 15 GB RAM, không GPU. Số liệu "đo" là từ lần chạy này;
số liệu "ước tính" được ghi rõ.

## Clip thử
Clip tự tạo 50 giây (`tools/make_test_clip.py`): 9 câu thoại tiếng Anh tự viết, hai nhân vật nam/nữ,
giọng tổng hợp, có nền âm nhỏ. Quyền: tự sở hữu. Đây là trường hợp dễ nhất cho nhận dạng giọng nói
(tiếng sạch, không nhạc, không nói chồng); phim thật sẽ khó hơn.

## Thành phần đã chạy thật

| Thành phần | Trạng thái |
|---|---|
| Tách âm thanh, khớp thời lượng, trộn, xuất MP4 (FFmpeg) | Chạy thật |
| Nhận dạng lời thoại (faster-whisper `small`, CPU) | Chạy thật |
| Dịch (Qwen2.5-7B Q4 chạy máy, qua endpoint OpenAI-compatible) | Chạy thật |
| Giọng đọc (edge-tts `vi-VN-HoaiMyNeural`) | Chạy thật |
| Tìm kiếm Internet Archive | Chạy thật |
| `vietdub batch` | Chỉ test với nhận dạng giả + giọng beep |
| Demucs, Piper, Gemini, Ollama chính hãng | Chưa chạy |
| Tải từ Internet Archive, Commons, YouTube, đồng bộ kênh | Chưa chạy thật |

## Lỗi tìm thấy và đã sửa
1. edge-tts không dùng proxy hệ thống → truyền proxy từ `HTTPS_PROXY`.
2. edge-tts thỉnh thoảng trả "No audio was received" cho câu hợp lệ → thử lại tối đa 4 lần.
3. faster-whisper lỗi khi đọc file với PyAV mới (`metadata_errors`) → tự giải mã bằng FFmpeg.
4. `batch` cắt mã ngôn ngữ sai (`chi` → `ch`) → bảng chuyển sang mã hai chữ, không rõ thì tự nhận.
5. Câu chỉ có ký hiệu (♪) làm giọng đọc lỗi → bỏ qua câu không có chữ.
6. Báo cáo thiếu thời gian từng bước → thêm `stage_seconds`, `output_bytes`.

## Chất lượng (đo trên clip thử)

| Tiêu chí | Kết quả |
|---|---|
| Nhận dạng lời thoại | Sai 3% số từ; lỗi thật duy nhất là tên "Linh" nghe thành "Lynn". Tách 9 câu thành 10 đoạn |
| Mốc thời gian nhận dạng | Lệch so với thực tế 0,04–1,1 giây; đoạn sau bị làm tròn về giây chẵn, sớm tới 1,1 giây |
| Dịch | 8/10 câu đúng nghĩa. "less than an hour" bị dịch thành "hơn một tiếng" (ngược nghĩa) ở cả hai lần chạy; "By the way" bị để nguyên "Btw". Xưng hô không ổn định giữa các lần chạy (bạn/tôi, anh/tôi) |
| Giọng Việt | Nghe lại bằng nhận dạng tiếng Việt ra gần đúng từng chữ → rõ, dễ nghe. Độ tự nhiên chưa được người nghe đánh giá |
| Đồng bộ | Giọng Việt phát sau mốc dự kiến 0,16–0,21 giây. 3/10 câu phải tăng tốc (tối đa 1,14×), 0 câu bị cắt, không câu nào chồng câu kế. 4 câu kéo dài quá câu gốc tới 0,76 giây |
| Nhiều nhân vật | Không hỗ trợ: cả nhân vật nam và nữ đều do một giọng nữ đọc |
| File MP4 | H.264 640×480 25fps giữ nguyên hình, AAC 44,1 kHz stereo 153 kbps, 50,08 giây (bằng bản gốc), giải mã không lỗi. Tiếng Anh gốc vẫn nghe được nhỏ ở nền (12%) |

## Hiệu năng (đo)

| Bước | Thời gian |
|---|---|
| Tách âm thanh | 0,2 s |
| Nhận dạng lời thoại | 9,2 s |
| Dịch | 45,3 s |
| Giọng đọc | 55,7 s (gồm thời gian thử lại và độ trễ mạng) |
| Khớp và ghép | 1,2 s |
| Trộn và xuất | 2,4 s |
| **Tổng** | **114 s cho 50 s video (2,3 lần thời lượng)** |

Chi phí API: 0 đồng (không gọi dịch vụ trả phí nào). File ra 1,03 MB; hình clip thử rất nhẹ nên
con số này không đại diện — với phim thật, dung lượng ≈ dung lượng hình gốc + khoảng 1,1 MB tiếng mỗi phút.

## Ước tính cho 100 tập × 5 phút (500 phút)
- Thời gian: khoảng 19 giờ máy trên cấu hình này, nếu tỉ lệ 2,3× giữ nguyên. Phim thật có mật độ
  thoại khác nên có thể lệch nhiều. GPU sẽ rút ngắn bước nhận dạng và dịch (chưa đo).
- Tiền: 0 đồng dịch vụ; chỉ có tiền điện/thuê máy. Thuê máy CPU 4 nhân khoảng 19 giờ là vài đô la (ước tính thô).
- Rủi ro: edge-tts là dịch vụ không chính thức, đã thấy rớt yêu cầu ngay ở 10 câu; 100 tập là hàng nghìn câu.

## Kết luận về pyVideoTrans
Không có lỗi kỹ thuật nào buộc phải đổi engine: engine hiện tại chạy trọn vẹn. Lý do duy nhất đáng
cân nhắc pyVideoTrans là phân vai nhiều giọng, thứ engine này chưa có.

## Việc nên làm tiếp, theo mức ảnh hưởng
1. Chất lượng dịch: thử model lớn hơn hoặc Gemini, thêm bước soát nghĩa (số, phủ định, so sánh).
2. Phân vai nam/nữ: nhận diện người nói rồi gán giọng `HoaiMy`/`NamMinh`.
3. Tách giọng gốc bằng Demucs để không còn tiếng gốc ở nền.
4. Chạy lại trên một clip phim thật có quyền sử dụng, có nhạc và nhiều người nói.
