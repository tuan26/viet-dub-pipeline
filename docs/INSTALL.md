# Cài đặt và khởi động Dashboard

Hướng dẫn cho một máy Linux hoặc macOS (Windows: dùng WSL2). Không cần GPU, không cần API trả phí.

## 1. Yêu cầu

| Thành phần | Ghi chú |
|---|---|
| Python 3.11 trở lên | |
| FFmpeg | `sudo apt install ffmpeg` hoặc `brew install ffmpeg` |
| PostgreSQL 14 trở lên | Khuyên dùng khi chạy thật. Không có thì hệ thống tự dùng SQLite trong thư mục thư viện |
| Ollama (hoặc máy chủ OpenAI-compatible khác) | Để dịch. Model mặc định `gemma3:12b` cần khoảng 14 GB RAM |
| RAM | 16 GB nếu dùng Gemma 12B trên cùng máy; 8 GB nếu dịch bằng model nhỏ hơn hoặc máy khác |
| Ổ đĩa | Khoảng 3 lần dung lượng video gốc cho file làm việc |

## 2. Cài đặt

```bash
git clone https://github.com/tuan26/viet-dub-pipeline
```

```bash
cd viet-dub-pipeline
```

```bash
python3 -m venv .venv && . .venv/bin/activate
```

```bash
pip install -e '.[all]'
```

Model nhận diện người nói (26 MB):

```bash
mkdir -p models && curl -L -o models/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx
```

Model dịch:

```bash
ollama pull gemma3:12b
```

Cơ sở dữ liệu (bỏ qua nếu dùng SQLite):

```bash
sudo -u postgres createuser vietdub -P && sudo -u postgres createdb -O vietdub vietdub
```

## 3. Cấu hình

Chép mẫu rồi sửa:

```bash
cp docs/pipeline.example.toml pipeline.toml
```

Các mục cần xem: `[storage] database`, `[dubbing]` (model dịch, giọng), `[limits]` (dung lượng, RAM, số phút mỗi ngày),
`[server] workers` và `cpu_threads`. Nguồn video có thể để trống trong file và thêm sau trên Dashboard.

## 4. Khởi động

```bash
vietdub serve --config pipeline.toml
```

Mở http://127.0.0.1:8800. Lần đầu, trang sẽ yêu cầu tạo tài khoản quản trị.

`serve` chạy cả web và các worker; worker nào chết sẽ được tự khởi động lại. Dừng bằng Ctrl+C: video đang xử lý
được trả về hàng đợi và làm tiếp ở lần chạy sau.

Chạy như dịch vụ hệ thống (systemd), ví dụ `/etc/systemd/system/vietdub.service`:

```ini
[Unit]
Description=vietdub
After=network.target postgresql.service

[Service]
User=vietdub
WorkingDirectory=/srv/vietdub
ExecStart=/srv/vietdub/.venv/bin/vietdub serve --config /srv/vietdub/pipeline.toml
Restart=on-failure
KillSignal=SIGTERM
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
```

## 5. Dùng hằng ngày (không cần dòng lệnh)

1. **Nguồn** → Thêm nguồn. Nguồn "đã xác minh quyền" cần license `owned` hoặc file bằng chứng (email, hợp đồng).
2. **Tổng quan** cho biết worker đang làm gì, tài nguyên máy, lỗi gần đây.
3. **Video** → video "Chờ xác minh quyền": mở, kiểm tra trang gốc, ghi căn cứ, xác nhận (chỉ quản trị viên).
4. Video "Cần duyệt" / "Đạt kiểm tra": bấm **Duyệt** để mở trang duyệt:
   - xem bản gốc và bản lồng tiếng cạnh nhau, bấm ▶ để nghe từng câu;
   - sửa bản dịch, đổi người nói, chọn giọng cho từng nhân vật, bấm 🔊 để nghe thử;
   - **Lưu và xuất lại video**: worker chỉ làm lại các câu đã sửa (thường dưới một phút);
5. Mở lại video, xem kết quả kiểm tra mới, ghi chú rồi **Duyệt bản cuối**. Tải MP4 và phụ đề ở trang video.

Vai trò tài khoản: *Chỉ xem*; *Người duyệt* (sửa, duyệt bản cuối, thử lại, tạm dừng); *Quản trị* (thêm: nguồn, xác nhận quyền, xoá, tài khoản).

## 6. Sao lưu và nâng cấp

Sao lưu gồm cơ sở dữ liệu, thư mục `library/` và `pipeline.toml`:

```bash
pg_dump -Fc vietdub > vietdub-$(date +%F).dump
```

Nâng cấp: dừng `serve`, sao lưu, cập nhật mã, cài lại, khởi động. Cấu trúc cơ sở dữ liệu được nâng cấp tự động khi khởi động
và không xoá dữ liệu cũ; phiên bản cũ hơn sẽ từ chối mở cơ sở dữ liệu đã được nâng cấp.

```bash
git pull && pip install -e '.[all]'
```

## 7. Bảo mật

- Mặc định chỉ nghe trên 127.0.0.1. Muốn truy cập từ máy khác, đặt sau một reverse proxy có HTTPS (Caddy, Nginx) và đặt
  biến môi trường `VIETDUB_HTTPS_ONLY=1` để cookie chỉ gửi qua HTTPS.
- Mật khẩu lưu dạng băm scrypt; sai 5 lần thì khoá tên đăng nhập 1 phút; mọi thao tác ghi đều có mã chống CSRF.
- Quản trị viên khai báo được đường dẫn thư mục trên máy chủ cho nguồn "Thư mục": chỉ cấp quyền quản trị cho người tin cậy.

## 8. Docker (chưa kiểm chứng)

`Dockerfile` và `docker/compose.yml` có sẵn nhưng **chưa được build hay chạy thử** (máy phát triển không có Docker daemon).

```bash
docker compose -f docker/compose.yml up -d --build
```

## 9. Khi gặp sự cố

| Hiện tượng | Xem ở đâu |
|---|---|
| Worker "mất liên lạc" | Cửa sổ chạy `serve`: worker tự khởi động lại; nếu lặp lại, thường do thiếu RAM |
| Video "Lỗi" | Trang video: dòng lỗi đỏ và nhật ký; sửa nguyên nhân rồi bấm **Thử lại** |
| Video đứng ở "Chờ lồng tiếng" | Hết hạn mức phút trong ngày, RAM/ổ đĩa dưới ngưỡng, hoặc video đang tạm dừng (xem ghi chú lỗi) |
| Không dịch được | Ollama có đang chạy không, `[dubbing] base_url` và `model` |
| Trang báo "Phiên làm việc hết hạn" | Tải lại trang; phiên đăng nhập kéo dài 12 giờ |
