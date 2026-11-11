# Research

| Nguồn | Cách lấy | Giấy phép đọc từ | Đã thử thật |
|---|---|---|---|
| Internet Archive | `advancedsearch.php` + `metadata/<id>` | `licenseurl` | Tìm và metadata: có. Tải file: chưa (máy chủ file bị mạng của môi trường dựng chặn) |
| Wikimedia Commons | `api.php` generator=search, `extmetadata` | `License`, `Artist` | Chưa: API trả 429 cho IP của môi trường dựng |
| YouTube | `yt-dlp ytsearchN:` rồi lọc trường `license` | "Creative Commons Attribution license (reuse allowed)" | Chưa |
| Kênh đã cấp phép | `yt-dlp --flat-playlist` | khai báo trong `sources.toml` | Chưa |

## Ghi chú
- `licenseurl:*publicdomain*` (ký tự đại diện ở đầu) làm API Internet Archive báo lỗi; dùng `licenseurl:http*` rồi lọc ở phía mình.
- Giấy phép trên Internet Archive là tự khai: lần thử thật trả về cả những video gắn nhãn phạm vi công cộng
  mà nội dung rõ ràng không phải của người đăng. Đây là lý do có bước duyệt bắt buộc.
- Wikimedia yêu cầu user agent mô tả rõ công cụ và cách liên hệ; đặt bằng `VIETDUB_USER_AGENT`.
- File Commons thường là WebM/Ogg; ghép vào MP4 với hình ảnh Theora sẽ lỗi — cần chuyển mã (việc còn mở).
- Tìm YouTube bằng yt-dlp không lọc CC được từ phía máy chủ nên phải lấy dư rồi lọc, khá chậm.
