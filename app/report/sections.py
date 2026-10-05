# -*- coding: utf-8 -*-
"""ساختار بخش‌های گزارش — مشترک بین Preview و Word Generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Paragraph:
    text: str
    style: str = "body"    # body | item | note | bullet


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


@dataclass
class GeneratedReport:
    sections: list[ReportSection] = field(default_factory=list)
    docx_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    findings: list = field(default_factory=list)      # list[app.core.findings.Finding]


# ---------------------------------------------------------------------------
def apply_manual_texts(sections: list[ReportSection], project) -> list[ReportSection]:
    """اعمال ویرایش‌های دستی کارشناس (بخش ۲۱): متن بخش جایگزین پاراگراف‌ها می‌شود
    و جدول‌ها/شکل‌ها حفظ می‌شوند."""
    for sec in sections:
        manual = ((getattr(project, "manual_texts", None) or {}).get(sec.key, "") or "").strip()
        if not manual:
            continue
        new_blocks = []
        inserted = False
        for b in sec.blocks:
            if isinstance(b, Paragraph) and not inserted:
                for part in [x.strip() for x in manual.split("\n\n") if x.strip()]:
                    new_blocks.append(Paragraph(part))
                inserted = True
            elif not isinstance(b, Paragraph):
                new_blocks.append(b)
        if not inserted:
            new_blocks = ([Paragraph(x.strip()) for x in manual.split("\n\n") if x.strip()]
                          + new_blocks)
        sec.blocks = new_blocks
        setattr(sec, "manual", True)
    return sections
