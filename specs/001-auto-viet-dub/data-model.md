# Data Model

**Segment** — `index:int`, `start:float` (giây), `end:float`, `text:str`, `translation:str`.
Lưu ở `work/segments.json`; người dùng được sửa `translation`.

**Rights** — `license` ∈ {owned, licensed, public-domain, cc0, cc-by, cc-by-sa}, `source` (bắt buộc),
`attribution` (bắt buộc với cc-by, cc-by-sa).

**Placement** — `index`, `start`, `speed` (≥ 1.0, ≤ max_speed), `length`, `truncated`.
Bất biến: `start + length ≤ start của câu kế − 0,05s`.

**Report** (`report.json`) — `video`, `output`, `rights`, `duration_seconds`, `segments`, `sped_up`,
`max_speed_used`, `truncated[]`, `background`, `elapsed_seconds`.
