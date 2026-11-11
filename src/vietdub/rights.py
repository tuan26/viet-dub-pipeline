"""Rights gate: the pipeline only runs on content the user declares they may dub."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import VietdubError

ALLOWED = {
    "owned": "Tôi sở hữu video này",
    "licensed": "Tôi có giấy phép/văn bản cho phép dịch và lồng tiếng",
    "public-domain": "Phạm vi công cộng",
    "cc0": "Creative Commons Zero",
    "cc-by": "Creative Commons Attribution",
    "cc-by-sa": "Creative Commons Attribution-ShareAlike",
}
NEEDS_ATTRIBUTION = {"cc-by", "cc-by-sa"}


@dataclass
class Rights:
    license: str
    source: str
    attribution: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def credits(self) -> str:
        lines = [f"Nguồn: {self.source}", f"Giấy phép: {self.license} ({ALLOWED[self.license]})"]
        if self.attribution:
            lines.append(f"Tác giả gốc: {self.attribution}")
        lines.append("Bản lồng tiếng Việt được tạo tự động bằng vietdub; nội dung đã được chỉnh sửa so với bản gốc.")
        return "\n".join(lines) + "\n"


def check_rights(license: str | None, source: str | None, attribution: str | None) -> Rights:
    if not license:
        raise VietdubError(
            "Thiếu --license. Hãy khai báo quyền sử dụng video: " + ", ".join(sorted(ALLOWED))
        )
    key = license.strip().lower()
    if "nc" in key.split("-") or "nd" in key.split("-"):
        raise VietdubError(
            f"Giấy phép '{license}' không cho phép tạo bản phái sinh hoặc dùng thương mại; không thể lồng tiếng."
        )
    if key not in ALLOWED:
        raise VietdubError(
            f"Giấy phép '{license}' không được hỗ trợ. Chọn một trong: " + ", ".join(sorted(ALLOWED))
        )
    if not source or not source.strip():
        raise VietdubError("Thiếu --source (URL hoặc mô tả nguồn gốc video).")
    if key in NEEDS_ATTRIBUTION and not (attribution or "").strip():
        raise VietdubError(f"Giấy phép '{key}' yêu cầu ghi công: thêm --attribution \"Tên tác giả\".")
    return Rights(key, source.strip(), (attribution or "").strip())
