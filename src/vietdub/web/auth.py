"""Accounts, roles and request protection for the dashboard."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from ..models import VietdubError

# viewer: read only. reviewer: edit and approve dubs, retry/pause jobs.
# admin: also sources, rights decisions, deletion, accounts and the system switch.
ROLES = {"viewer": 0, "reviewer": 1, "admin": 2}
ROLE_LABELS = {"viewer": "Chỉ xem", "reviewer": "Người duyệt", "admin": "Quản trị"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        check = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(check.hex(), digest)
    except (ValueError, TypeError):
        return False


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise VietdubError("Mật khẩu cần ít nhất 8 ký tự.")


def allowed(role: str | None, needed: str) -> bool:
    return role in ROLES and ROLES[role] >= ROLES[needed]


class Throttle:
    """Slows down password guessing: after 5 failures a name is locked for a minute."""

    def __init__(self, limit: int = 5, lock_seconds: float = 60):
        self.limit, self.lock_seconds = limit, lock_seconds
        self.failures: dict[str, tuple[int, float]] = {}
        self.lock = threading.Lock()

    def blocked(self, key: str) -> float:
        with self.lock:
            count, until = self.failures.get(key, (0, 0.0))
            return max(0.0, until - time.time()) if count >= self.limit else 0.0

    def fail(self, key: str) -> None:
        with self.lock:
            count, _ = self.failures.get(key, (0, 0.0))
            count += 1
            self.failures[key] = (count, time.time() + self.lock_seconds if count >= self.limit else 0.0)

    def ok(self, key: str) -> None:
        with self.lock:
            self.failures.pop(key, None)
