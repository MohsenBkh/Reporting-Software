# -*- coding: utf-8 -*-
"""Pipeline تولید گزارش — از پروژه تا DOCX و پیش‌نمایش (بخش ۲۲ و ۲۸ سند)."""
from __future__ import annotations

import html as html_mod
from pathlib import Path
from typing import Optional

from app.core.models import Project
from app.core.report_types import REPORT_SECTIONALIZER, is_heavy
from app.core.settings import AppSettings
from app.core.validation import validate_project
from app.report.sections import FigureBlock, GeneratedReport, Paragraph, TableSpec
from app.report.sectionalizer import SectionalizerTextGenerator
from app.report.template_manager import TemplateManager
from app.report.text_generator import TextGenerator
from app.report.word_generator import WordGenerator
from app.rules.rule_engine import RuleEngine


def build_sections(project: Project, settings: AppSettings,
                   texts: TemplateManager, engine: RuleEngine,
                   charts_dir: Path, image_resolver=None,
                   profile_loader=None) -> GeneratedReport:
    if is_heavy(project.report_type):
        gen = TextGenerator(project, settings, texts, engine, charts_dir,
                            image_resolver, profile_loader)
    elif project.report_type == REPORT_SECTIONALIZER:
        gen = SectionalizerTextGenerator(project, settings, texts)
    else:
        raise ValueError(f"نوع گزارش پشتیبانی‌نشده: {project.report_type}")
    report = GeneratedReport(sections=gen.build_all())
    report.findings = gen.findings
    report.warnings = list(gen.report_warnings)
    return report


def generate_docx(project: Project, settings: AppSettings, report: GeneratedReport,
                  out_path: Path) -> Path:
    wg = WordGenerator(project, settings)
    return wg.generate(report, out_path)


def docx_filename(project: Project) -> str:
    import re
    safe = re.sub(r'[\\/:*?"<>|]', "-", project.name or project.title_text())
    return f"{safe}.docx"


def generate_report_full(project: Project, settings: AppSettings,
                         charts_dir: Path, output_dir: Path,
                         texts: Optional[TemplateManager] = None,
                         engine: Optional[RuleEngine] = None,
                         image_resolver=None,
                         profile_loader=None) -> tuple[GeneratedReport, Path, list]:
    """تولید کامل: بخش‌ها + نمودارها + فایل Word. خروجی: (گزارش، مسیر docx، آیتم‌های اعتبارسنجی)."""
    texts = texts or TemplateManager.from_settings(settings)
    engine = engine or RuleEngine()
    items = validate_project(project, settings)
    charts_dir.mkdir(parents=True, exist_ok=True)
    report = build_sections(project, settings, texts, engine, charts_dir,
                            image_resolver, profile_loader)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / docx_filename(project)
    generate_docx(project, settings, report, out)
    report.docx_path = str(out)
    return report, out, items


# ---------------------------------------------------------------------------
# پیش‌نمایش HTML (برای Preview داخل برنامه)
# ---------------------------------------------------------------------------
def report_to_html(report: GeneratedReport, project: Project,
                   settings: AppSettings) -> str:
    parts: list[str] = []
    esc = html_mod.escape
    parts.append(f"""
    <div style="text-align:center; margin-bottom:18px;">
      <div style="font-size:15pt; font-weight:bold;">{esc(settings.company_name)}</div>
      <div style="font-size:11pt;">{esc(project.booklet_title())}</div>
      <div style="font-size:13pt; font-weight:bold; margin-top:14px; color:#1F4E79;">{esc(project.title_text())}</div>
      <div style="font-size:10pt; margin-top:8px; color:#555;">
        شماره گزارش: {esc(project.report_number)} &nbsp;|&nbsp; تاریخ: {esc(project.date_jalali)}
      </div>
    </div><hr/>""")

    for i, sec in enumerate(report.sections):
        manual = getattr(sec, "manual", False)
        tag = " ✎" if manual else ""
        parts.append(f'<h2 style="color:#1F4E79;">{i + 1}- {esc(sec.title)}{tag}</h2>')
        for block in sec.blocks:
            if isinstance(block, Paragraph):
                if block.style == "bullet":
                    parts.append(f'<p class="bullet">● {esc(block.text)}</p>')
                else:
                    cls = {"item": "item", "note": "note"}.get(block.style, "body")
                    parts.append(f'<p class="{cls}">{esc(block.text)}</p>')
            elif isinstance(block, TableSpec):
                parts.append(_table_html(block))
            elif isinstance(block, FigureBlock):
                src = Path(block.path).resolve().as_uri()
                parts.append(
                    f'<p style="text-align:center;"><img src="{src}" width="620"/></p>'
                    f'<p style="text-align:center; font-weight:bold;">{esc(block.caption)}</p>')
        parts.append("<hr/>")

    body = "\n".join(parts)
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8">
<style>
 body {{ font-family: 'B Nazanin','Tahoma','Segoe UI'; font-size: 12pt; direction: rtl;
        margin: 16px; line-height: 1.9; background:#FFFFFF; color:#111111; }}
 p.body {{ text-align: justify; margin: 6px 0; }}
 p.item {{ font-weight: bold; }}
 p.note {{ color: #B00; }}
 p.bullet {{ margin: 4px 24px 4px 0; }}
 h2 {{ font-size: 14pt; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
 table {{ border-collapse: collapse; margin: 10px auto; direction: rtl; }}
 td, th {{ border: 1px solid #7F7F7F; padding: 5px 10px; font-size: 10.5pt; text-align: center; }}
 th {{ background: #D9E2F3; font-weight: bold; }}
 .cap {{ text-align:center; font-weight:bold; margin: 4px 0 10px; }}
</style></head><body>{body}</body></html>"""


def _table_html(spec: TableSpec) -> str:
    esc = html_mod.escape
    out = []
    if spec.caption:
        out.append(f'<p class="cap">{esc(spec.caption)}</p>')
    out.append("<table>")
    # ادغام سلول‌های سربرگ (colspan)
    spans: dict[int, tuple[int, int]] = {}
    for (ri, c0, c1) in spec.merges:
        spans[ri] = (c0, c1)
    for ri, row in enumerate(spec.header_rows):
        cells = []
        skip_to = -1
        span = spans.get(ri)
        for ci, c in enumerate(row):
            if span is not None and span[0] <= ci <= span[1]:
                if ci == span[0]:
                    cells.append(f'<th colspan="{span[1] - span[0] + 1}">{esc(c)}</th>')
                continue
            cells.append(f"<th>{esc(c)}</th>" if c else "<th></th>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    for row in spec.body_rows:
        out.append("<tr>" + "".join(
            f"<td><b>{esc(c).replace(chr(10), '<br/>')}</b></td>" if i == 0
            else f"<td>{esc(c).replace(chr(10), '<br/>')}</td>"
            for i, c in enumerate(row)) + "</tr>")
    out.append("</table>")
    return "".join(out)
