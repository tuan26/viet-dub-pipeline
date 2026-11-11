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
    "ollama": ("http://localhost:11434/v1", "qwen2.5:7b", None),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY"),
}

SYSTEM = (
    "Bạn là biên dịch viên lồng tiếng phim. Dịch từng câu thoại sang tiếng Việt tự nhiên, "
    "đúng xưng hô theo quan hệ nhân vật, ngắn gọn để đọc vừa thời lượng câu gốc. "
    "Giữ nhất quán tên riêng. Chỉ trả về một mảng JSON các chuỗi, đúng số lượng và thứ tự câu được đưa vào."
)

ChatFn = Callable[[str, str], str]


@dataclass
class ChatConfig:
    base_url: str
    model: str
    api_key: str | None = None

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
            "temperature": 0.3,
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


def translate(
    segments: list[Segment],
    chat: ChatFn,
    source_language: str | None = None,
    glossary: str = "",
    batch_size: int = 40,
) -> None:
    """Fill ``translation`` on every segment. Batches keep context between lines;
    a batch whose reply is malformed is retried one line at a time."""
    lang = f" (ngôn ngữ gốc: {source_language})" if source_language else ""
    notes = f"\nBảng tên riêng và xưng hô cần tuân theo:\n{glossary}\n" if glossary.strip() else ""
    for start in range(0, len(segments), batch_size):
        batch = segments[start : start + batch_size]
        prompt = (
            f"Dịch {len(batch)} câu thoại sau{lang}.{notes}\n"
            + json.dumps([s.text for s in batch], ensure_ascii=False)
        )
        result = _parse_list(chat(SYSTEM, prompt), len(batch))
        if result is None:
            result = []
            for seg in batch:
                single = _parse_list(
                    chat(SYSTEM, f"Dịch 1 câu thoại sau{lang}.{notes}\n" + json.dumps([seg.text], ensure_ascii=False)),
                    1,
                )
                if single is None:
                    raise VietdubError(f"Bộ dịch trả về sai định dạng ở câu {seg.index}: {seg.text!r}")
                result.append(single[0])
        for seg, text in zip(batch, result):
            seg.translation = text
