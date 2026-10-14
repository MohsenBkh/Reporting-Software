# -*- coding: utf-8 -*-
"""ارائه‌دهندگان هوش مصنوعی (HTTP با کتابخانهٔ استاندارد؛ بدون وابستگی اضافه).

هر ارائه‌دهنده دو کار می‌کند: ساخت درخواست (``build``) و استخراج متن پاسخ (``parse``). ارسال واقعی
در ``send_request`` است و برای تست قابل جایگزینی (opener) است.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from app.ai.package import AIPackage
from app.ai.settings import (PROVIDER_ANTHROPIC, PROVIDER_CUSTOM, PROVIDER_GEMINI,
                             PROVIDER_OPENAI, AISettings)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_BASE = "https://api.openai.com/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class AIError(Exception):
    """خطای قابل‌نمایش به کاربر (فارسی)."""


@dataclass
class HttpRequest:
    url: str
    headers: dict[str, str]
    body: bytes


def _user_text(pkg: AIPackage) -> str:
    return ("داده‌های پروژه و متن فعلی بخش‌ها (JSON):\n" + pkg.data_text +
            "\n\nبخش‌های درخواست‌شده: " + "، ".join(pkg.requested) +
            "\nفقط برای همین کلیدها متن اصلاح‌شده را در JSON خروجی برگردان.")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class Provider:
    key = ""
    label = ""
    supports_images = True

    def build(self, pkg: AIPackage, ai: AISettings, api_key: str) -> HttpRequest:
        raise NotImplementedError

    def parse(self, data: dict) -> str:
        raise NotImplementedError


class AnthropicProvider(Provider):
    key, label = PROVIDER_ANTHROPIC, "Anthropic (Claude)"

    def build(self, pkg, ai, api_key):
        content = [{"type": "text", "text": _user_text(pkg)}]
        for name, data, mime, meta in pkg.images:
            content.append({"type": "text", "text": f"تصویر {name}: {meta.get('title') or meta.get('caption') or ''}"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": _b64(data)}})
        body = {"model": ai.model(), "max_tokens": 8000, "system": ai.instructions,
                "messages": [{"role": "user", "content": content}]}
        return HttpRequest(ANTHROPIC_URL, {"x-api-key": api_key, "anthropic-version": "2023-06-01",
                                           "content-type": "application/json"},
                           json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def parse(self, data):
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        if not parts:
            raise AIError("پاسخ ارائه‌دهنده متنی نداشت.")
        return "".join(parts)


class OpenAIProvider(Provider):
    key, label = PROVIDER_OPENAI, "OpenAI"

    def base(self, ai: AISettings) -> str:
        return OPENAI_BASE

    def build(self, pkg, ai, api_key):
        content = [{"type": "text", "text": _user_text(pkg)}]
        for name, data, mime, meta in pkg.images:
            content.append({"type": "text", "text": f"تصویر {name}: {meta.get('title') or ''}"})
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{_b64(data)}"}})
        body = {"model": ai.model(), "temperature": 0.2,
                "messages": [{"role": "system", "content": ai.instructions},
                             {"role": "user", "content": content}]}
        return HttpRequest(self.base(ai).rstrip("/") + "/chat/completions",
                           {"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
                           json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def parse(self, data):
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIError("قالب پاسخ ارائه‌دهنده ناشناخته است.") from None


class CustomProvider(OpenAIProvider):
    key, label = PROVIDER_CUSTOM, "سرویس سازگار با OpenAI (آدرس دلخواه)"

    def base(self, ai):
        if not ai.custom_base_url.strip():
            raise AIError("آدرس پایهٔ سرویس (Base URL) را وارد کنید.")
        return ai.custom_base_url.strip()


class GeminiProvider(Provider):
    key, label = PROVIDER_GEMINI, "Google (Gemini)"

    def build(self, pkg, ai, api_key):
        parts = [{"text": _user_text(pkg)}]
        for name, data, mime, meta in pkg.images:
            parts.append({"text": f"تصویر {name}: {meta.get('title') or ''}"})
            parts.append({"inline_data": {"mime_type": mime, "data": _b64(data)}})
        body = {"systemInstruction": {"parts": [{"text": ai.instructions}]},
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
        return HttpRequest(f"{GEMINI_BASE}/{ai.model()}:generateContent",
                           {"x-goog-api-key": api_key, "content-type": "application/json"},
                           json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def parse(self, data):
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError):
            raise AIError("پاسخ Gemini خالی یا مسدود شده است.") from None


PROVIDERS: dict[str, Provider] = {p.key: p for p in (
    AnthropicProvider(), OpenAIProvider(), GeminiProvider(), CustomProvider())}

_HTTP_MESSAGES = {
    400: "درخواست نامعتبر است (نام مدل یا حجم داده را بررسی کنید).",
    401: "کلید API نامعتبر است.", 403: "دسترسی با این کلید مجاز نیست.",
    404: "مدل یا آدرس یافت نشد (نام مدل را بررسی کنید).",
    413: "حجم داده ارسالی زیاد است؛ تعداد تصاویر/بخش‌ها را کم کنید.",
    429: "سقف تعداد درخواست یا اعتبار حساب تمام شده است.",
}


def send_request(req: HttpRequest, timeout: int = 180, opener: Optional[Callable] = None) -> dict:
    """ارسال درخواست و بازگرداندن JSON پاسخ؛ هر خطا به ``AIError`` فارسی تبدیل می‌شود."""
    request = urllib.request.Request(req.url, data=req.body, headers=req.headers, method="POST")
    try:
        resp = (opener or urllib.request.urlopen)(request, timeout=timeout)
        raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8", "replace")).get("error", "")
            detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        except Exception:  # noqa: BLE001
            pass
        msg = _HTTP_MESSAGES.get(e.code, f"خطای سرور ({e.code}).")
        raise AIError(msg + (f"\nجزئیات: {detail[:300]}" if detail else "")) from None
    except urllib.error.URLError as e:
        raise AIError(f"اتصال به اینترنت/سرویس برقرار نشد: {getattr(e, 'reason', e)}") from None
    except TimeoutError:
        raise AIError("زمان انتظار پاسخ تمام شد.") from None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise AIError("پاسخ سرویس JSON معتبر نیست.") from None
