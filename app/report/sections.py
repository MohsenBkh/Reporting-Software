# -*- coding: utf-8 -*-
"""ساختار بخش‌های گزارش — مشترک بین Preview و Word Generator."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Paragraph:
    text: str
    style: str = "body"    # body | item | note


@dataclass
class TableSpec:
    caption: str
    header_rows: list[list[str]]
    body_rows: list[list[str]]
    merges: list[tuple[int, int, int]] = field(default_factory=list)  # (row, col_start, col_end)
    first_col_header: str = ""


@dataclass
class FigureBlock:
    path: str
    caption: str


@dataclass
class ReportSection:
    key: str
    title: str
    blocks: list = field(default_factory=list)

    def paragraphs(self) -> list[Paragraph]:
        return [b for b in self.blocks if isinstance(b, Paragraph)]

    def has_override_marker(self) -> bool:
        return getattr(self, "manual", False)


# پیشوند شماره‌گذاری قبلی شکل (برای جلوگیری از «شکل ۲: شکل ۱: ...» در تولید مجدد)
_FIG_NUM_RE = re.compile(r"^\s*شکل\s*[\d۰-۹]+\s*[:：\-–—]\s*")


def number_figures(sections: list) -> int:
    """شماره‌گذاری سراسری شکل‌ها مانند جدول‌ها: «شکل n: <عنوان>».

    روی همهٔ بخش‌ها به ترتیب ظهور اعمال می‌شود؛ پیشوند شمارهٔ قبلی (در صورت
    وجود) حذف و با شمارهٔ جدید جایگزین می‌شود. تعداد شکل‌ها را برمی‌گرداند.
    """
    n = 0
    for sec in sections:
        for block in getattr(sec, "blocks", []):
            if isinstance(block, FigureBlock):
                n += 1
                base = _FIG_NUM_RE.sub("", (block.caption or "").strip())
                block.caption = f"شکل {n}: {base}" if base else f"شکل {n}"
    return n


@dataclass
class GeneratedReport:
    sections: list[ReportSection] = field(default_factory=list)
    docx_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    findings: list = field(default_factory=list)      # list[app.core.findings.Finding]
