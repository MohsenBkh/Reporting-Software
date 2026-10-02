# -*- coding: utf-8 -*-
"""مدیریت کتابخانه متن — بارگذاری/ذخیره متن‌های قالب از/به JSON (بخش ۱۷ و ۲۱ سند).

قالب کاربر به‌صورت فایل JSON مجزا ذخیره می‌شود (ذخیره قالب گزارش)؛ در نبود آن،
پیش‌فرض‌های همراه برنامه بارگذاری می‌شوند.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

TEXTS_DIR = Path(__file__).resolve().parent / "data" / "texts"


@dataclass
class TextEntry:
    id: str
    title: str
    template: str
    vars: list[str]
    file: str = ""   # نام فایل مبدأ (برای ذخیره)

    def render(self, values: dict[str, str]) -> str:
        """جایگزینی متغیرها؛ متغیر ناموجود با — پر می‌شود."""
        class _Map(dict):
            def __missing__(self, key: str) -> str:  # pragma: no cover
                return "—"
        return self.template.format_map(_Map(values))


class TemplateManager:
    """متن‌ها را از پوشه texts (پیش‌فرض) و در صورت وجود از فایل قالب کاربر بارگذاری می‌کند."""

    def __init__(self, texts_dir: Path | str = TEXTS_DIR,
                 template_file: Path | str | None = None) -> None:
        self.texts_dir = Path(texts_dir)
        self.template_file = Path(template_file) if template_file else None
        self.entries: dict[str, TextEntry] = {}
        self.load()

    @classmethod
    def from_settings(cls, settings) -> "TemplateManager":
        """ساخت مدیر قالب بر اساس تنظیمات (فایل قالب کاربر در صورت وجود)."""
        tf = getattr(settings, "template_file", "") or None
        return cls(template_file=tf)

    def load(self) -> None:
        self.entries = {}
        # ۱) فایل قالب کاربر در صورت تنظیم بودن و موجود بودن — اولویت دارد
        if self.template_file is not None and self.template_file.exists():
            self._load_file(self.template_file)
            if self.entries:
                return
        # ۲) پیش‌فرض‌های همراه برنامه
        if not self.texts_dir.exists():
            return
        for path in sorted(self.texts_dir.glob("*.json")):
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in data.get("texts", []):
            try:
                entry = TextEntry(
                    id=item["id"], title=item.get("title", item["id"]),
                    template=item.get("template", ""),
                    vars=list(item.get("vars", [])),
                    file=path.name)
                self.entries[entry.id] = entry
            except (KeyError, TypeError):
                continue

    def get(self, text_id: str) -> TextEntry | None:
        return self.entries.get(text_id)

    def render(self, text_id: str, values: dict[str, str]) -> str:
        entry = self.get(text_id)
        if entry is None:
            return ""
        return entry.render(values)

    def save_entry(self, text_id: str, new_template: str) -> bool:
        """ذخیره ویرایش کاربر روی یک متن؛ True اگر موفق."""
        entry = self.entries.get(text_id)
        if entry is None or not entry.file:
            return False
        path = self.texts_dir / entry.file
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data.get("texts", []):
                if item.get("id") == text_id:
                    item["template"] = new_template
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            entry.template = new_template
            return True
        except (OSError, ValueError):
            return False

    def save_as_template(self, dest: Path | str) -> Path:
        """ذخیره کل قالب فعلی (متن‌های ویرایش‌شده) به فایل JSON مجزا."""
        dest = Path(dest)
        if dest.suffix.lower() != ".json":
            dest = dest.with_suffix(".json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        titles = {e.id: e.title for e in self.entries.values()}
        payload = {
            "name": dest.stem,
            "texts": [
                {"id": tid, "title": titles.get(tid, tid), "template": e.template,
                 "vars": e.vars}
                for tid, e in sorted(self.entries.items())
            ],
        }
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self.template_file = dest
        return dest

    def load_template_file(self, path: Path | str) -> bool:
        """بارگذاری قالب از فایل JSON مجزا؛ True اگر حداقل یک متن خوانده شود."""
        self.template_file = Path(path)
        self.load()
        return bool(self.entries)

    def restore_defaults(self) -> None:
        """بازگرداندن متن‌ها به پیش‌فرض (حذف نسخه ویرایش‌شده و بارگذاری مجدد)."""
        # نسخه پیش‌فرض داخل پکیج است؛ در این پیاده‌سازی تک‌منبعی است و
        # ویرایش مستقیماً روی همان فایل اعمال می‌شود، بنابراین بازیابی
        # از پشتیبانِ درون‌حافظه انجام می‌شود.
        if self._defaults:
            for tid, template in self._defaults.items():
                if tid in self.entries:
                    self.save_entry(tid, template)
            self.load()

    _defaults: dict[str, str] = {}

    def snapshot_defaults(self) -> None:
        """ثبت نسخه فعلی به‌عنوان پیش‌فرض برای امکان Restore."""
        self._defaults = {tid: e.template for tid, e in self.entries.items()}
