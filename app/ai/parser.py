# -*- coding: utf-8 -*-
"""استخراج پیشنهاد متن هر بخش از پاسخ مدل + نگهبان عددهای جدید."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.ai.providers import AIError

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)
_NUM = re.compile(r"\d+(?:[.,٫]\d+)?")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")


@dataclass
class AIResult:
    sections: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    raw: str = ""


def parse_response(text: str, allowed_keys: list[str]) -> AIResult:
    """JSON پاسخ را (حتی با ``` یا متن اضافی) می‌خواند؛ فقط کلیدهای درخواست‌شده پذیرفته می‌شود."""
    raw = text or ""
    body = _FENCE.sub("", raw.strip())
    if not body.startswith("{"):
        i, j = body.find("{"), body.rfind("}")
        body = body[i:j + 1] if 0 <= i < j else body
    try:
        data = json.loads(body)
    except ValueError:
        raise AIError("پاسخ مدل JSON معتبر نبود؛ دوباره تلاش کنید.") from None
    secs = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(secs, dict):
        raise AIError("پاسخ مدل کلید «sections» ندارد.")
    ok = {k: str(v).strip() for k, v in secs.items() if k in allowed_keys and str(v).strip()}
    if not ok:
        raise AIError("مدل متنی برای بخش‌های درخواست‌شده برنگرداند.")
    return AIResult(sections=ok, notes=str(data.get("notes", "")).strip(), raw=raw)


def numbers_in(text: str) -> set[str]:
    out = set()
    for m in _NUM.findall((text or "").translate(_DIGITS)):
        out.add(m.replace(",", ".").rstrip("0").rstrip(".") if "." in m.replace(",", ".") else m)
    return out


def unverified_numbers(suggested: str, *corpus: str) -> list[str]:
    """عددهایی در متن پیشنهادی که در داده‌ها/متن اصلی نیستند (احتمال ساخته‌شدن توسط مدل)."""
    known: set[str] = set()
    for c in corpus:
        known |= numbers_in(c)
    return sorted(numbers_in(suggested) - known, key=lambda x: (len(x), x))
