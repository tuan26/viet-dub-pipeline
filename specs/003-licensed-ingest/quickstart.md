# Quickstart

```bash
pip install -e '.[asr,tts,ingest]'
```

## Hướng 1: nguồn giấy phép mở

```bash
vietdub ingest search archive "short film" --limit 10
```

Mở trang gốc của từng mục để chắc giấy phép là thật, rồi duyệt:

```bash
vietdub ingest approve archive:<mã>
```

```bash
vietdub ingest fetch
```

```bash
vietdub batch --lang en
```

## Hướng 2: kênh đã cấp phép

1. Gửi thư theo mẫu `docs/outreach/permission-request.md`.
2. Lưu thư đồng ý vào `permissions/`, chép `docs/sources.example.toml` thành `sources.toml` và điền.

```bash
vietdub ingest sync
```

```bash
vietdub ingest fetch
```

```bash
vietdub batch --lang zh
```

Xem thư viện bất cứ lúc nào bằng `vietdub ingest list`.
