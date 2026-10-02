# -*- coding: utf-8 -*-
"""ساختار بخش‌های گزارش — مشترک بین Preview و Word Generator."""
from __future__ import annotations

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


@dataclass
class GeneratedReport:
    sections: list[ReportSection] = field(default_factory=list)
    docx_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    findings: list = field(default_factory=list)      # list[app.core.findings.Finding]
