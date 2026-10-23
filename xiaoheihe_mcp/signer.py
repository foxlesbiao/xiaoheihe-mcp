"""小黑盒 Web 请求签名，算法来自公开的非官方接口研究。"""

from __future__ import annotations

import hashlib
import hmac
import random
import time

R_CHARSET = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"
RND_KEY = "Z7mFG4tQp9Ws2LxB8H"
NONCE_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _tw(s: str, charset: str, n: int) -> str:
    sub = charset[:n]
    return "".join(sub[ord(char) % len(sub)] for char in s)


def _rw(s: str, charset: str) -> str:
    return "".join(charset[ord(char) % len(charset)] for char in s)


def _interleave(values: list[str]) -> str:
    max_len = max(len(value) for value in values)
    return "".join(value[i] for i in range(max_len) for value in values if i < len(value))


def _ty(value: int) -> int:
    return ((value << 1) ^ 27) & 255 if value & 128 else value << 1


def _da(value: int) -> int:
    return _ty(value) ^ value


def _vs(value: int) -> int:
    return _da(_ty(value))


def _dol_c(value: int) -> int:
    return _vs(_da(_ty(value)))


def _dl(value: int) -> int:
    return _dol_c(value) ^ _vs(value) ^ _da(value)


def _mix_columns(values: list[int]) -> list[int]:
    result = [
        _dl(values[0]) ^ _dol_c(values[1]) ^ _vs(values[2]) ^ _da(values[3]),
        _da(values[0]) ^ _dl(values[1]) ^ _dol_c(values[2]) ^ _vs(values[3]),
        _vs(values[0]) ^ _da(values[1]) ^ _dl(values[2]) ^ _dol_c(values[3]),
        _dol_c(values[0]) ^ _vs(values[1]) ^ _da(values[2]) ^ _dl(values[3]),
    ]
    values[:4] = result
    return values


def clean_path(path: str) -> str:
    return "/" + "/".join(part for part in path.split("/") if part) + "/"


def calc_hkey(path: str, timestamp: int, nonce: str) -> str:
    normalized = clean_path(path)
    part_time = _tw(str(timestamp + 1), R_CHARSET, -2)
    part_path = _rw(normalized, R_CHARSET)
    part_nonce = _rw(nonce, R_CHARSET)
    digest = hashlib.md5(_interleave([part_time, part_path, part_nonce])[:20].encode("utf-8")).hexdigest()
    transformed = _mix_columns([ord(char) for char in digest[-6:]])
    upper = f"{sum(transformed) % 100:02d}"
    lower = _tw(digest[:5], R_CHARSET, -4)
    return lower + upper


def calc_rnd(nonce: str, timestamp: int) -> str:
    message = (RND_KEY + nonce + f"{timestamp}:{nonce}").encode("utf-8")
    return "15:" + hmac.new(RND_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_web_request(path: str, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    now = int(timestamp if timestamp is not None else time.time())
    nonce = nonce or "".join(random.choice(NONCE_CHARS) for _ in range(32))
    return {
        "_time": str(now),
        "nonce": nonce,
        "hkey": calc_hkey(path, now, nonce),
        "_rnd": calc_rnd(nonce, now),
        "version": "999.0.4",
    }
