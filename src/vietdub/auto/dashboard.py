"""A read-only status page written as one local HTML file."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

from .store import STATES, Store

COLOURS = {"QC_PASS": "#1a7f37", "READY": "#1a7f37", "NEEDS_REVIEW": "#9a6700", "AWAITING_RIGHTS": "#9a6700",
           "FAILED": "#cf222e", "REJECTED": "#6e7781", "DUPLICATE": "#6e7781"}


def _when(ts) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""


def render(store: Store) -> str:
    videos, e = store.videos(), html.escape
    counts = {s: sum(1 for v in videos if v["state"] == s) for s in STATES}
    rows = []
    for v in videos:
        qc = json.loads(v["qc"]) if v["qc"] else {}
        note = "; ".join(qc.get("reasons", [])) or v["error"] or v["rights_basis"] or ""
        rows.append(
            f"<tr><td>{e(v['title'] or '')}<br><small>{e(v['id'])}</small></td><td>{e(v['source'])}</td>"
            f"<td>{e(v['license'] or '')}</td><td><b style='color:{COLOURS.get(v['state'], '#0969da')}'>{v['state']}</b></td>"
            f"<td>{(v['duration'] or 0) / 60:.1f}</td><td>{v['attempts']}</td><td>{e(note)}</td><td>{_when(v['updated_at'])}</td></tr>")
    events = "".join(f"<tr><td>{_when(ev['ts'])}</td><td>{e(ev['video_id'] or '')}</td><td>{e(ev['stage'] or '')}</td>"
                     f"<td>{e(ev['level'] or '')}</td><td>{e(ev['message'] or '')}</td></tr>" for ev in store.events(limit=60))
    sources = "".join(f"<tr><td>{e(s['name'])}</td><td>{_when(s['last_checked'])}</td><td>{s['found'] or 0}</td>"
                      f"<td>{e(s['last_error'] or '')}</td></tr>" for s in store.sources())
    tiles = "".join(f"<div class=t><b>{n}</b><span>{s}</span></div>" for s, n in counts.items() if n)
    return f"""<!doctype html><html lang=vi><meta charset=utf-8><title>vietdub — trạng thái</title>
<style>body{{font:14px system-ui,sans-serif;margin:24px;color:#1f2328}}table{{border-collapse:collapse;width:100%;margin:8px 0 28px}}
td,th{{border-bottom:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#f6f8fa}}
.t{{display:inline-block;margin:0 12px 12px 0;padding:10px 14px;border:1px solid #d0d7de;border-radius:6px}}
.t b{{font-size:22px;display:block}}small{{color:#6e7781}}</style>
<h1>vietdub — trạng thái xử lý</h1><p>Cập nhật {_when(time.time())}. {len(videos)} video.</p>{tiles}
<h2>Video</h2><table><tr><th>Video</th><th>Nguồn</th><th>Giấy phép</th><th>Trạng thái</th><th>Phút</th><th>Lần thử</th><th>Ghi chú</th><th>Cập nhật</th></tr>{''.join(rows)}</table>
<h2>Nguồn</h2><table><tr><th>Nguồn</th><th>Kiểm tra lần cuối</th><th>Mới</th><th>Lỗi</th></tr>{sources}</table>
<h2>Nhật ký gần đây</h2><table><tr><th>Lúc</th><th>Video</th><th>Bước</th><th>Mức</th><th>Nội dung</th></tr>{events}</table></html>"""


def write(store: Store, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(store), encoding="utf-8")
    return out
