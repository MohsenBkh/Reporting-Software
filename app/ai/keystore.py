# -*- coding: utf-8 -*-
"""نگهداری کلید API — خارج از پروژه و تنظیمات برنامه.

اولویت: متغیر محیطی (ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / REPORTFORGE_AI_KEY_CUSTOM)
← فایل کاربر ``~/.reportforge/ai_keys.json`` (مسیر با REPORTFORGE_AI_KEYS قابل تغییر است).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

ENV_NAMES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
             "gemini": "GEMINI_API_KEY", "custom": "REPORTFORGE_AI_KEY_CUSTOM"}


def keys_file() -> Path:
    override = os.environ.get("REPORTFORGE_AI_KEYS")
    return Path(override) if override else Path.home() / ".reportforge" / "ai_keys.json"


def _read() -> dict:
    try:
        return json.loads(keys_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def get_key(provider: str) -> Optional[str]:
    env = os.environ.get(ENV_NAMES.get(provider, ""), "").strip()
    if env:
        return env
    return (_read().get(provider) or "").strip() or None


def set_key(provider: str, key: str) -> None:
    data = _read()
    if key.strip():
        data[provider] = key.strip()
    else:
        data.pop(provider, None)
    f = keys_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass


def has_key(provider: str) -> bool:
    return get_key(provider) is not None


def mask(key: Optional[str]) -> str:
    return "" if not key else (key[:4] + "…" + key[-3:] if len(key) > 8 else "••••")
