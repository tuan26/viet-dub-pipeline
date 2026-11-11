"""Translation through any OpenAI-compatible chat endpoint (Ollama, Gemini, Groq, ...)."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from ..models import Segment, VietdubError

PRESETS = {
    # name: (base_url, default model, env var holding the API key or None)
    "ollama": ("http://localhost:11434/v1", "gemma3:12b", None),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY"),
}

SYSTEM = (
    "Bạn là biên dịch viên lồng tiếng phim. Dịch từng câu thoại sang tiếng Việt tự nhiên, "
    "đúng xưng hô theo quan hệ nhân vật, ngắn gọn để đọc vừa thời lượng câu gốc. "
    "Giữ nhất quán tên riêng. Chỉ trả về một mảng JSON các chuỗi, đúng số lượng và thứ tự câu được đưa vào."
)

# Candidate prompt: explicit rules for the error types seen in real runs.
SYSTEM_STRICT = (
    "Bạn là biên dịch viên lồng tiếng phim, dịch hội thoại sang tiếng Việt.\n"
    "Quy tắc bắt buộc:\n"
    "1. Giữ đúng nghĩa phủ định, so sánh (ít hơn/nhiều hơn/chưa đến), con số, giờ giấc, ngày tháng.\n"
    "2. Thành ngữ, tiếng lóng: dịch theo NGHĨA, không dịch từng chữ.\n"
    "3. Không để sót từ nước ngoài; chỉ giữ nguyên tên riêng. Tên người Trung Quốc chuyển sang âm Hán-Việt.\n"
    "4. Xưng hô theo quan hệ nhân vật trong ngữ cảnh (mẹ-con, sếp-nhân viên, bạn bè) và giữ nhất quán.\n"
    "5. Câu ngắn gọn, tự nhiên như lời nói, đọc vừa thời lượng câu gốc.\n"
    "Chỉ trả về một mảng JSON các chuỗi, đúng số lượng và thứ tự câu được đưa vào, không giải thích."
)
PROMPTS = {"basic": SYSTEM, "strict": SYSTEM_STRICT}

ChatFn = Callable[[str, str], str]


@dataclass
class ChatConfig:
    base_url: str
    model: str
    api_key: str | None = None
    temperature: float = 0.0

    @classmethod
    def from_preset(cls, name: str, model: str | None, base_url: str | None) -> "ChatConfig":
        if name not in PRESETS:
            raise VietdubError(f"Bộ dịch '{name}' không có. Chọn: {', '.join(PRESETS)}, none.")
        url, default_model, key_env = PRESETS[name]
        key = os.environ.get(key_env) if key_env else None
        if key_env and not key:
            raise VietdubError(f"Thiếu biến môi trường {key_env} cho bộ dịch '{name}'.")
        return cls(base_url or url, model or default_model, key)

    def chat(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions", body, headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.load(resp)
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, IndexError, ValueError) as exc:
            raise VietdubError(f"Gọi bộ dịch tại {self.base_url} thất bại: {exc}")


def _parse_list(reply: str, expected: int) -> list[str] | None:
    match = re.search(r"\[.*\]", reply, re.S)
    if not match:
        return None
    try:
        items = json.loads(match.group(0))
    except ValueError:
        return None
    if len(items) != expected or not all(isinstance(x, str) and x.strip() for x in items):
        return None
    return [x.strip() for x in items]


_FOREIGN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")  # Chinese, kana, Korean
REMINDER = "\nLưu ý: chỉ viết bằng tiếng Việt, không để lại chữ Trung, Nhật, Hàn hay nguyên văn câu gốc."


def _suspect(source: str, translation: str) -> bool:
    """A line the model failed to translate: foreign script left in, or the source echoed back."""
    return bool(_FOREIGN.search(translation)) or (
        len(source.split()) > 2 and translation.strip().lower() == source.strip().lower())


def _plain_line(reply: str) -> str:
    """Models answer a one-line request as bare text, a JSON array, a JSON object or a
    fenced block; take the first string whichever it is."""
    body = re.sub(r"^```\w*\s*|\s*```$", "", reply.strip())
    try:
        value = json.loads(body)
        while isinstance(value, (list, dict)) and value:
            value = next(iter(value.values())) if isinstance(value, dict) else value[0]
        body = value if isinstance(value, str) else ""
    except ValueError:
        body = body.splitlines()[0] if body else ""
    return body.strip().strip('"“”').strip()


def shorten(seg: Segment, chat: ChatFn, max_words: int) -> str | None:
    """Ask for a tighter wording of a line that does not fit its time slot.
    Returns None when the model does not produce a shorter Vietnamese line."""
    reply = chat(
        "Bạn biên tập lời thoại lồng tiếng. Viết lại câu tiếng Việt cho ngắn hơn, giữ ý chính, "
        "giữ nguyên xưng hô, con số và phủ định. Chỉ trả về đúng câu đã viết lại, không giải thích.",
        f"Câu gốc: {seg.text}\nBản dịch hiện tại: {seg.translation}\nViết lại trong tối đa {max_words} tiếng.",
    )
    text = _plain_line(reply)
    if not text or _suspect(seg.text, text):
        return None
    return text if len(text.split()) < len(seg.translation.split()) else None


def translate(
    segments: list[Segment],
    chat: ChatFn,
    source_language: str | None = None,
    glossary: str = "",
    batch_size: int = 40,
    system: str = SYSTEM_STRICT,
    retries: int = 2,
) -> list[int]:
    """Fill ``translation`` on every segment and return the indexes of lines that are
    still not Vietnamese after retrying. Batches keep context between lines; a malformed
    batch reply, or a line left untranslated, is retried one line at a time."""
    unresolved: list[int] = []

    def one(seg: Segment, extra: str = "") -> str | None:
        for _ in range(retries + 1):
            single = _parse_list(
                chat(system, f"Dịch 1 câu thoại sau{lang}.{notes}{extra}\n" + json.dumps([seg.text], ensure_ascii=False)), 1)
            if single is not None and not _suspect(seg.text, single[0]):
                return single[0]
        return single[0] if single is not None else None

    lang = f" (ngôn ngữ gốc: {source_language})" if source_language else ""
    notes = f"\nBảng tên riêng và xưng hô cần tuân theo:\n{glossary}\n" if glossary.strip() else ""
    for start in range(0, len(segments), batch_size):
        batch = segments[start : start + batch_size]
        prompt = (
            f"Dịch {len(batch)} câu thoại sau{lang}.{notes}\n"
            + json.dumps([s.text for s in batch], ensure_ascii=False)
        )
        result = _parse_list(chat(system, prompt), len(batch))
        if result is None:
            result = []
            for seg in batch:
                text = one(seg)
                if text is None:
                    raise VietdubError(f"Bộ dịch trả về sai định dạng ở câu {seg.index}: {seg.text!r}")
                result.append(text)
        for seg, text in zip(batch, result):
            if _suspect(seg.text, text):
                text = one(seg, REMINDER) or text
                if _suspect(seg.text, text):
                    unresolved.append(seg.index)
            seg.translation = text
    return unresolved
