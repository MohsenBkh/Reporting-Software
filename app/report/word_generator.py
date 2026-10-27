# -*- coding: utf-8 -*-
"""مولد فایل Word (DOCX) — فارسی، RTL، سربرگ/پاورقی، فهرست مطالب، جداول و شکل‌ها.

از python-docx + تنظیمات مستقیم OOXML برای راست‌به‌چپ استفاده می‌کند.
"""
from __future__ import annotations

import re as _re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.core.models import Project, REQUEST_INCREASE
from app import APP_VERSION
from app.core.report_types import (REPORT_TYPE_FEEDER_DEV, booklet_title,
                                   header_title, is_protection_report)
from app.core.settings import AppSettings
from app.report.sections import FigureBlock, GeneratedReport, Paragraph, ReportSection, TableSpec
from app.utils.jalali import jalali_month_year
from app.utils.resources import resource_path

HEADER_GRAY = "D9E2F3"
BORDER_COLOR = "7F7F7F"


def default_logo_path() -> Path | None:
    """لوگوی پیش‌فرض همراه برنامه در صورت وجود.

    اولویت با لوگوی دفترچه نمونه (آرم توانیر — ``tavanir_logo.png``) است؛
    در نبود آن ``logo.png`` قدیمی استفاده می‌شود.
    """
    for name in ("tavanir_logo.png", "logo.png"):
        p = resource_path(name)
        if p.exists():
            return p
    return None


def header_logo_path() -> Path | None:
    """لوگوی کوچک سربرگ صفحات (مطابق سربرگ دفترچه نمونه)."""
    for name in ("tavanir_logo_header.png", "tavanir_logo.png", "logo.png"):
        p = resource_path(name)
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# ابزارهای OOXML
# ---------------------------------------------------------------------------
def _el(tag: str, **attrs) -> OxmlElement:
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(f"w:{k}"), str(v))
    return e


def set_rtl(paragraph, rtl: bool = True) -> None:
    """bidi را در جایگاه درست سند OOXML (قبل از jc) درج می‌کند — idempotent."""
    pPr = paragraph._p.get_or_add_pPr()
    if rtl:
        if pPr.find(qn("w:bidi")) is not None:
            return
        bidi = _el("w:bidi")
        jc = pPr.find(qn("w:jc"))
        if jc is not None:
            jc.addprevious(bidi)
        else:
            pPr.append(bidi)


def style_run(run, font_fa: str, size: int, bold: bool = False,
              color: RGBColor | None = None, font_latin: str = "Times New Roman",
              rtl: bool = True) -> None:
    run.font.name = font_latin
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = _el("w:rFonts")
        rPr.insert(0, rFonts)
    # v2.5.0: فونت لاتین صریح روی ascii/hAnsi تا واژه‌های انگلیسی با
    # Times New Roman رندر شوند (نه گلیف لاتین فونت فارسی)
    rFonts.set(qn("w:ascii"), font_latin)
    rFonts.set(qn("w:hAnsi"), font_latin)
    rFonts.set(qn("w:cs"), font_fa)
    # ترتیب فرزندان rPr مطابق اسکیمای OOXML: ... b, bCs, ... sz, szCs, ... rtl
    if rPr.find(qn("w:szCs")) is None:
        szCs = _el("w:szCs", val=str(int(size * 2)))
        sz = rPr.find(qn("w:sz"))
        if sz is not None:
            sz.addnext(szCs)
        else:
            rPr.append(szCs)
    if bold and rPr.find(qn("w:bCs")) is None:
        bCs = _el("w:bCs")
        b = rPr.find(qn("w:b"))
        if b is not None:
            b.addnext(bCs)
        else:
            szCs = rPr.find(qn("w:szCs"))
            if szCs is not None:
                szCs.addprevious(bCs)
            else:
                rPr.append(bCs)
    if rtl:
        if rPr.find(qn("w:rtl")) is None:
            rPr.append(_el("w:rtl"))


#: قطعه لاتین: واژه‌ای که با حرف انگلیسی شروع می‌شود + ادامه‌های چسبیده
#: (رقم/نقطه/خط تیره/اسلش) و واژه‌های لاتین بعدی با یک فاصله
#: مثال‌ها: «WI150900»، «TAV111-03/00»، «DIgSILENT PowerFactory»، «ACSR-70 mm2»
_LATIN_SEG = _re.compile(r"[A-Za-z][A-Za-z0-9&+./\-]*(?:[ ][A-Za-z0-9][A-Za-z0-9&+./\-]*)*")


def add_text_runs(p, text: str, *, font_fa: str, size: int, bold: bool = False,
                  color: RGBColor | None = None,
                  font_latin: str = "Times New Roman") -> None:
    """نوشتن متن مخلوط فارسی/انگلیسی در چند run.

    v2.5.0 — قطعات انگلیسی در run جداگانه و بدون پرچم ``w:rtl`` نوشته می‌شوند تا
    Word آن‌ها را با فونت لاتین (Times New Roman) رندر کند؛ در run دارای
    ``w:rtl`` تمام متن با فونت فارسی (cs) نمایش داده می‌شود.
    """
    text = "" if text is None else str(text)
    pos = 0
    for m in _LATIN_SEG.finditer(text):
        if m.start() > pos:
            style_run(p.add_run(text[pos:m.start()]), font_fa, size, bold=bold,
                      color=color, font_latin=font_latin)
        style_run(p.add_run(m.group()), font_fa, size, bold=bold, color=color,
                  font_latin=font_latin, rtl=False)
        pos = m.end()
    if pos < len(text) or not text:
        style_run(p.add_run(text[pos:]), font_fa, size, bold=bold, color=color,
                  font_latin=font_latin)


def add_par(doc_or_cell, text: str, *, font_fa: str, size: int,
            bold: bool = False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
            color: RGBColor | None = None, rtl: bool = True,
            space_after: int = 6, font_latin: str = "Times New Roman",
            line_spacing: float = 1.15):
    """افزودن پاراگراف فارسی RTL با استایل کامل (واژه‌های انگلیسی با فونت لاتین)."""
    p = doc_or_cell.add_paragraph()
    p.alignment = align
    set_rtl(p, rtl)
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    add_text_runs(p, text, font_fa=font_fa, size=size, bold=bold, color=color,
                  font_latin=font_latin)
    return p


def add_table_bidi(table) -> None:
    """جدول راست‌به‌چپ + خطوط کامل — با رعایت ترتیب اسکیمای tblPr."""
    tbl = table._tbl
    tblPr = tbl.tblPr
    if tblPr.find(qn("w:bidiVisual")) is None:
        bidi = _el("w:bidiVisual")
        # bidiVisual باید قبل از tblW/tblBorders بیاید — بعد از tblStyle
        tbl_style = tblPr.find(qn("w:tblStyle"))
        if tbl_style is not None:
            tbl_style.addnext(bidi)
        else:
            tblPr.insert(0, bidi)
    if tblPr.find(qn("w:tblBorders")) is None:
        borders = _el("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(_el(f"w:{side}", val="single", sz="4",
                               space="0", color=BORDER_COLOR))
        tblPr.append(borders)


def shade_cell(cell, hex_color: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(_el("w:shd", val="clear", color="auto", fill=hex_color))


def cell_text(cell, text: str, *, font_fa: str, size: int, bold=False,
              align=WD_ALIGN_PARAGRAPH.CENTER, color: RGBColor | None = None,
              font_latin: str = "Times New Roman") -> None:
    """نوشتن متن در یک خانه جدول — با پشتیبانی از چند خط (\n).

    جدول‌های دفترچه مطالعات (مثل «پیک بار خط») چند مقدار را در یک خانه دارند
    (MVA / MW / A)؛ این تابع هر خط را در یک پاراگراف جداگانه می‌نویسد.
    """
    cell.text = ""
    lines = [ln for ln in str(text).split("\n")] or [""]
    for idx, line in enumerate(lines):
        p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
        p.alignment = align
        set_rtl(p)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(1)
        add_text_runs(p, line, font_fa=font_fa, size=size, bold=bold, color=color,
                      font_latin=font_latin)


def _field(paragraph, instr: str) -> None:
    """درج فیلد Word (مثل TOC یا PAGE)."""
    r1 = paragraph.add_run()
    fld = _el("w:fldChar", fldCharType="begin")
    r1._r.append(fld)
    r2 = paragraph.add_run()
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = instr
    r2._r.append(instrText)
    r3 = paragraph.add_run()
    r3._r.append(_el("w:fldChar", fldCharType="separate"))
    r4 = paragraph.add_run("…")
    style_run(r4, "B Nazanin", 12)
    r5 = paragraph.add_run()
    r5._r.append(_el("w:fldChar", fldCharType="end"))


# ---------------------------------------------------------------------------
# مولد اصلی
# ---------------------------------------------------------------------------
class WordGenerator:
    def __init__(self, project: Project, settings: AppSettings) -> None:
        self.project = project
        self.settings = settings
        self.f = settings.fonts
        # قالب‌های حفاظتی (ریکلوزر/سکشنالایزر/ترکیبی): چیدمان جلد و سربرگ
        # دقیقاً مطابق «نمونه دفترچه مطالعه ریکلوزر و سکشنالایزر».
        # v2.4.0 — دفترچه «توسعه و اصلاح فیدر» هم از همین قالب دفترچه (جلد با
        # عنوان سری + شماره گزارش و سربرگ سه‌ستونه با شماره/تاریخ) استفاده می‌کند.
        rt = getattr(project, "report_type", "")
        self.protection = is_protection_report(rt) or rt == REPORT_TYPE_FEEDER_DEV

    @property
    def _caption_size(self) -> int:
        """اندازه عنوان شکل/جدول — دفترچه نمونه حفاظتی: ۱۱ پوینت."""
        return 11 if self.protection else self.f.body_size - 1

    # ------------------------------------------------------------------
    # بخش‌هایی که در Word به‌صورت افقی (Landscape) صفحه‌بندی می‌شوند —
    # برگه تنظیمات هماهنگی (خروجی A4 افقی ابزار IDMT) در پیوست پایانی.
    LANDSCAPE_SECTIONS = {"prot_settings_sheet"}

    def generate(self, report: GeneratedReport, out_path: str | Path) -> Path:
        doc = Document()
        self._landscape = False
        self._setup_styles(doc)
        self._setup_page(doc)
        self._cover(doc)
        self._toc(doc, [self._heading_text(sec, i + 1) for i, sec in enumerate(report.sections)])
        for i, sec in enumerate(report.sections):
            self._set_orientation(doc, sec.key in self.LANDSCAPE_SECTIONS)
            self._section(doc, sec, number=i + 1)
        self._set_properties(doc)
        self._update_fields_on_open(doc)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out_path)
        return out_path

    # ------------------------------------------------------------------
    @staticmethod
    def _is_appendix(sec: ReportSection) -> bool:
        return sec.key.startswith("appendix")

    def _heading_text(self, sec: ReportSection, number: int) -> str:
        return sec.title if self._is_appendix(sec) else f"{number}- {sec.title}"

    def _setup_styles(self, doc: Document) -> None:
        """فونت فارسی و زبان bidi در استایل‌های پایه (Normal / Heading / Caption)."""
        f = self.f
        for name in ("Normal", "Heading 1", "Heading 2", "Caption"):
            try:
                st = doc.styles[name]
            except KeyError:
                continue
            rPr = st.element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = _el("w:rFonts")
                rPr.insert(0, rFonts)
            fa = f.heading_font if name.startswith("Heading") else f.body_font
            for attr in ("ascii", "hAnsi", "eastAsia"):
                rFonts.set(qn(f"w:{attr}"), f.latin_font)
            rFonts.set(qn("w:cs"), fa)
            if rPr.find(qn("w:lang")) is None:
                rPr.append(_el("w:lang", val="en-US", bidi="fa-IR"))
        h1 = doc.styles["Heading 1"]
        h1.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        h1.paragraph_format.keep_with_next = True
        h1.paragraph_format.space_before = Pt(12)

    def _set_properties(self, doc: Document) -> None:
        cp = doc.core_properties
        cp.title = self.project.title_text()
        cp.subject = booklet_title(getattr(self.project, "report_type", ""))
        cp.author = self.project.expert_name or self.settings.company_name
        cp.language = "fa-IR"
        cp.keywords = f"ReportForge {APP_VERSION}"

    @staticmethod
    def _update_fields_on_open(doc: Document) -> None:
        """Word هنگام بازشدن فهرست مطالب و شماره صفحات را به‌روز می‌کند."""
        settings = doc.settings.element
        if settings.find(qn("w:updateFields")) is None:
            settings.append(_el("w:updateFields", val="true"))

    # ------------------------------------------------------------------
    def _setup_page(self, doc: Document) -> None:
        sec = doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.top_margin = sec.bottom_margin = Cm(2.0)
        sec.left_margin = sec.right_margin = Cm(2.0)
        self._header_footer(sec)

    def _set_orientation(self, doc: Document, landscape: bool) -> None:
        """شروع Section جدید Word با جهت صفحه خواسته‌شده (A4 عمودی/افقی).

        سربرگ و پاورقی به‌صورت «پیوند به قبلی» حفظ می‌شوند؛ حاشیه‌ها ۲ سانتی‌متر.
        """
        if landscape == self._landscape:
            return
        sec = doc.add_section(WD_SECTION.NEW_PAGE)
        if landscape:
            sec.orientation = WD_ORIENT.LANDSCAPE
            sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
        else:
            sec.orientation = WD_ORIENT.PORTRAIT
            sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.top_margin = sec.bottom_margin = Cm(2.0)
        sec.left_margin = sec.right_margin = Cm(2.0)
        self._landscape = landscape

    def _header_footer(self, sec) -> None:
        if self.protection:
            self._protection_header(sec)
        else:
            self._heavy_header(sec)
        self._footer(sec)
        # صفحه جلد بدون سربرگ/پاورقی
        sec.different_first_page_header_footer = True

    def _protection_header(self, sec) -> None:
        """سربرگ دفترچه نمونه: [لوگو + نام شرکت | عنوان گزارش | شماره و تاریخ] + خط ممتد.

        جدول سه‌ستونه بدون حاشیه و راست‌به‌چپ — ستون اول (راست): آرم توانیر و نام
        شرکت؛ ستون میانی: عنوان سری گزارش؛ ستون چپ: شماره گزارش و تاریخ.
        """
        f = self.f
        p = self.project
        header = sec.header
        hp0 = header.paragraphs[0]
        ht = header.add_table(rows=1, cols=3, width=Cm(17.0))
        ht.alignment = WD_TABLE_ALIGNMENT.CENTER
        ht.autofit = False
        tblPr = ht._tbl.tblPr
        tblPr.append(_el("w:bidiVisual"))
        tblPr.append(_el("w:tblLayout", type="fixed"))
        tblPr.append(_el("w:tblW", w="9638", type="dxa"))
        borders = _el("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(_el(f"w:{side}", val="none", sz="0", space="0", color="auto"))
        tblPr.append(borders)
        logo_cell, mid_cell, info_cell = ht.rows[0].cells   # bidiVisual: اولی سمت راست
        logo_cell.width, mid_cell.width, info_cell.width = Cm(3.55), Cm(9.62), Cm(3.85)
        hp0._p.getparent().remove(hp0._p)
        # ستون راست: لوگوی کوچک + نام شرکت (مطابق نمونه: آرم ۰٫۳ اینچ و متن ریز)
        lp = logo_cell.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_rtl(lp)
        lp.paragraph_format.space_after = Pt(0)
        logo = header_logo_path()
        if logo is not None:
            try:
                lp.add_run().add_picture(str(logo), height=Cm(0.76))
                lp.add_run().add_break()
            except Exception:  # noqa: BLE001
                pass
        r = lp.add_run(self.settings.company_name)
        style_run(r, f.body_font, 6, bold=True)
        # ستون میانی: عنوان سری گزارش (دفترچه نمونه)
        mp = mid_cell.paragraphs[0]
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_rtl(mp)
        mv = mid_cell._tc.get_or_add_tcPr()
        mv.append(_el("w:vAlign", val="center"))
        r = mp.add_run(header_title(getattr(p, "report_type", "")))
        style_run(r, f.body_font, 10, bold=True)
        # ستون چپ: شماره گزارش و تاریخ (دو سطر)
        ip = info_cell.paragraphs[0]
        ip.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_rtl(ip)
        ip.paragraph_format.space_after = Pt(0)
        add_text_runs(ip, f"شماره گزارش: {p.report_number}", font_fa=f.body_font,
                      size=10, bold=True)
        ip2 = info_cell.add_paragraph()
        ip2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_rtl(ip2)
        r = ip2.add_run(f"تاریخ: {jalali_month_year(p.date_jalali)}")
        style_run(r, f.body_font, 10, bold=True)
        self._header_rule(header)

    @staticmethod
    def _header_rule(header) -> None:
        """خط ممتد زیر سربرگ (پاراگراف جدا با حاشیه پایین)."""
        hline = header.add_paragraph()
        hline.paragraph_format.space_before = Pt(0)
        hline.paragraph_format.space_after = Pt(0)
        pPr = hline._p.get_or_add_pPr()
        pBdr = _el("w:pBdr")
        pBdr.append(_el("w:bottom", val="single", sz="8", space="1",
                        color=BORDER_COLOR))
        pPr.append(pBdr)

    def _heavy_header(self, sec) -> None:
        f = self.f
        p = self.project
        # --- سربرگ صفحات ۲ به بعد: «دفترچه…» راست | «شماره گزارش / تاریخ» چپ + خط ممتد ---
        header = sec.header
        hp0 = header.paragraphs[0]
        # جدول نامرئی دوستونه (RTL): ستون اول = راست (عنوان دفترچه)، ستون دوم = چپ (شماره/تاریخ)
        ht = header.add_table(rows=1, cols=2, width=Cm(17.0))
        ht.alignment = WD_TABLE_ALIGNMENT.CENTER
        ht.autofit = False
        tblPr = ht._tbl.tblPr
        tblPr.append(_el("w:bidiVisual"))
        # چیدمان ثابت + عرض کل، تا Word عرض ستون‌ها را بازتنظیم نکند
        tblPr.append(_el("w:tblLayout", type="fixed"))
        tblPr.append(_el("w:tblW", w="9639", type="dxa"))
        # بدون حاشیه (جدول نامرئی)
        borders = _el("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(_el(f"w:{side}", val="none", sz="0", space="0", color="auto"))
        tblPr.append(borders)
        right_cell, left_cell = ht.rows[0].cells  # در bidiVisual: اولین سلول سمت راست نمایش داده می‌شود
        right_cell.width = Cm(9.5)
        left_cell.width = Cm(7.5)
        # حذف پاراگراف خالی پیش‌فرض بالای جدول (ارتفاع اضافی سربرگ نمی‌گیرد)
        hp0._p.getparent().remove(hp0._p)
        cp = right_cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_rtl(cp)
        r = cp.add_run(booklet_title(getattr(self.project, "report_type", "")))
        style_run(r, f.body_font, 10, bold=True)
        cp2 = left_cell.paragraphs[0]
        cp2.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_rtl(cp2)
        add_text_runs(cp2, f"شماره گزارش: {p.report_number}        تاریخ: {jalali_month_year(p.date_jalali)}",
                      font_fa=f.body_font, size=10, bold=True)
        self._header_rule(header)

    def _footer(self, sec) -> None:
        # --- پاورقی: «صفحه X از Y» ---
        f = self.f
        footer = sec.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_rtl(fp)
        r = fp.add_run("صفحه ")
        style_run(r, f.body_font, 10)
        self._simple_field(fp, " PAGE ", f.body_font)
        r = fp.add_run(" از ")
        style_run(r, f.body_font, 10)
        self._simple_field(fp, " NUMPAGES ", f.body_font)

    @staticmethod
    def _simple_field(paragraph, instr: str, font: str) -> None:
        r1 = paragraph.add_run()
        style_run(r1, font, 10)
        r1._r.append(_el("w:fldChar", fldCharType="begin"))
        r2 = paragraph.add_run()
        style_run(r2, font, 10)
        it = OxmlElement("w:instrText")
        it.set(qn("xml:space"), "preserve")
        it.text = instr
        r2._r.append(it)
        r3 = paragraph.add_run()
        style_run(r3, font, 10)
        r3._r.append(_el("w:fldChar", fldCharType="separate"))
        r4 = paragraph.add_run("1")
        style_run(r4, font, 10)
        r5 = paragraph.add_run()
        style_run(r5, font, 10)
        r5._r.append(_el("w:fldChar", fldCharType="end"))

    def _logo_path(self) -> Path | None:
        """لوگوی جلد: اولویت با تنظیم کاربر، سپس لوگوی همراه برنامه."""
        custom = self.settings.company_logo
        if custom:
            p = Path(custom)
            if p.exists():
                return p
        return default_logo_path()

    # ------------------------------------------------------------------
    def _cover(self, doc: Document) -> None:
        f = self.f
        p = self.project
        # لوگوی شرکت بالای نام شرکت
        logo = self._logo_path()
        if logo is not None:
            try:
                lp = doc.add_paragraph()
                lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                lp.paragraph_format.space_after = Pt(8)
                lp.add_run().add_picture(str(logo), height=Cm(3.2))
            except Exception:  # noqa: BLE001 — لوگوی خراب نباید گزارش را متوقف کند
                pass
        add_par(doc, self.settings.company_name, font_fa=f.heading_font,
                size=18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
        add_par(doc, self.settings.unit_name, font_fa=f.body_font,
                size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
        add_par(doc, self.settings.office_name, font_fa=f.body_font,
                size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

        add_par(doc, booklet_title(getattr(self.project, "report_type", "")),
                font_fa=f.heading_font, size=22, bold=True,
                align=WD_ALIGN_PARAGRAPH.CENTER, space_after=30,
                color=RGBColor(0x1F, 0x4E, 0x79))

        if self.protection:
            # جلد دفترچه نمونه: عنوان پروژه ۱۸pt، سپس ماه/سال و شماره گزارش —
            # بدون سطر جداگانه «تاریخ:» (تاریخ کامل فقط در سربرگ صفحات می‌آید)
            add_par(doc, p.title_text(), font_fa=f.heading_font, size=18, bold=True,
                    align=WD_ALIGN_PARAGRAPH.CENTER, space_after=60)
            add_par(doc, jalali_month_year(p.date_jalali), font_fa=f.heading_font,
                    size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=60)
            add_par(doc, f"شماره گزارش: {p.report_number}", font_fa=f.body_font,
                    size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
            if p.expert_name:
                add_par(doc, f"کارشناس مطالعات: {p.expert_name}", font_fa=f.body_font,
                        size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        else:
            add_par(doc, p.title_text(), font_fa=f.heading_font, size=16, bold=True,
                    align=WD_ALIGN_PARAGRAPH.CENTER, space_after=40)

            add_par(doc, jalali_month_year(p.date_jalali), font_fa=f.heading_font,
                    size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=60)

            add_par(doc, f"شماره گزارش: {p.report_number}", font_fa=f.body_font,
                    size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
            add_par(doc, f"تاریخ: {p.date_jalali}", font_fa=f.body_font,
                    size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
            if p.expert_name:
                add_par(doc, f"کارشناس مطالعات: {p.expert_name}", font_fa=f.body_font,
                        size=12, align=WD_ALIGN_PARAGRAPH.CENTER)

        pb = doc.add_paragraph()
        pb.add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------------
    def _toc(self, doc: Document, titles: list[str]) -> None:
        f = self.f
        add_par(doc, "فهرست مطالب", font_fa=f.heading_font, size=f.heading1_size,
                bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)
        p = doc.add_paragraph()
        set_rtl(p)
        # فیلد TOC با نتیجه اولیه (عناوین) — Word هنگام بازشدن شماره صفحات را کامل می‌کند
        p.add_run()._r.append(_el("w:fldChar", fldCharType="begin"))
        r2 = p.add_run()
        it = OxmlElement("w:instrText")
        it.set(qn("xml:space"), "preserve")
        it.text = ' TOC \\o "1-2" \\h \\z \\u '
        r2._r.append(it)
        p.add_run()._r.append(_el("w:fldChar", fldCharType="separate"))
        for i, t in enumerate(titles):
            r = p.add_run(t)
            style_run(r, f.body_font, f.body_size)
            if i < len(titles) - 1:
                r.add_break()
        p.add_run()._r.append(_el("w:fldChar", fldCharType="end"))
        pb = doc.add_paragraph()
        pb.add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------------
    def _section(self, doc: Document, sec: ReportSection, number: int) -> None:
        f = self.f
        # عنوان با استایل Heading 1 — تا فیلد TOC پس از F9 در Word پر شود
        hp = doc.add_paragraph(style="Heading 1")
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_rtl(hp)
        hp.paragraph_format.space_after = Pt(10)
        run = hp.add_run(self._heading_text(sec, number))
        style_run(run, f.heading_font, f.heading1_size, bold=True,
                  color=RGBColor(0x1F, 0x4E, 0x79), font_latin=f.latin_font)
        for block in sec.blocks:
            if isinstance(block, Paragraph):
                style = ("item" if block.style == "item" else "body")
                for line in str(block.text).split("\n"):
                    if not line.strip():
                        continue
                    add_par(doc, line, font_fa=f.body_font, size=f.body_size,
                            bold=(style == "item"),
                            align=WD_ALIGN_PARAGRAPH.JUSTIFY)
            elif isinstance(block, TableSpec):
                self._table(doc, block)
            elif isinstance(block, FigureBlock):
                self._figure(doc, block)

    # ------------------------------------------------------------------
    def _table(self, doc: Document, spec: TableSpec) -> None:
        f = self.f
        # عنوان جدول — بالای جدول (مطابق نمونه‌ها)؛ خالی = جدول بدون عنوان
        if spec.caption:
            cap = add_par(doc, spec.caption, font_fa=f.body_font, size=self._caption_size,
                          bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4,
                          color=RGBColor(0, 0, 0))
            cap.style = doc.styles["Caption"]
            cap.paragraph_format.keep_with_next = True

        n_cols = max((len(r) for r in spec.header_rows + spec.body_rows), default=1)
        n_head = len(spec.header_rows)
        table = doc.add_table(rows=n_head + len(spec.body_rows), cols=n_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        add_table_bidi(table)

        for ri, row in enumerate(spec.header_rows):
            for ci in range(n_cols):
                text = row[ci] if ci < len(row) else ""
                cell_text(table.cell(ri, ci), text, font_fa=f.body_font,
                          size=f.body_size - 1, bold=True)
                shade_cell(table.cell(ri, ci), HEADER_GRAY)

        for ri, row in enumerate(table.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(_el("w:cantSplit"))
            if ri < n_head:
                trPr.append(_el("w:tblHeader"))
        for (ri, c0, c1) in spec.merges:
            if c1 > c0 and c1 < n_cols:
                table.cell(ri, c0).merge(table.cell(ri, c1))

        for ri, row in enumerate(spec.body_rows):
            for ci in range(n_cols):
                text = row[ci] if ci < len(row) else ""
                cell = table.cell(n_head + ri, ci)
                cell_text(cell, text, font_fa=f.body_font, size=f.body_size - 1,
                          bold=(ci == 0))
                if ci == 0:
                    shade_cell(cell, HEADER_GRAY)

        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # ------------------------------------------------------------------
    def _figure(self, doc: Document, fig: FigureBlock) -> None:
        f = self.f
        path = Path(fig.path)
        if not path.exists():
            return
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            run = p.add_run()
            pic = run.add_picture(str(path))
            # بزرگ‌ترین اندازهٔ ممکن در محدودهٔ حاشیه‌ها (A4 با حاشیه ۲cm):
            # عمودی → عرض ۱۷cm؛ افقی → عرض ۲۵٫۷cm — با حفظ نسبت و سقف ارتفاع صفحه.
            if getattr(self, "_landscape", False):
                max_w, max_h = Cm(25.7), Cm(16.2)
            else:
                max_w, max_h = Cm(17.0), Cm(23.5)
            scale = min(max_w / pic.width, max_h / pic.height)
            pic.width = int(pic.width * scale)
            pic.height = int(pic.height * scale)
        except Exception:  # noqa: BLE001 — تصویر خراب نباید کل گزارش را متوقف کند
            return
        p.paragraph_format.keep_with_next = True
        cap = add_par(doc, fig.caption, font_fa=f.body_font, size=self._caption_size,
                      bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10,
                      color=RGBColor(0, 0, 0))
        cap.style = doc.styles["Caption"]
