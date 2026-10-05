# -*- coding: utf-8 -*-
"""بررسی اجرای واقعی ReportForge v1.2.0 — «تغییرات آرنا».

این اسکریپت بدون نیاز به نمایشگر (QT_QPA_PLATFORM=offscreen) کل اپلیکیشن را
راه می‌اندازد، یک پروژه نمونه مطالعه مصارف سنگین می‌سازد، همه صفحات را می‌گردد و
درستی بخش‌های جدید (اطلاعات تقاضا، ایستگاه‌ها، خطوط، متقاضیان همزمان، نکات تحلیلی،
سناریوها، بررسی اقتصادی) را در «تحلیل مهندسی» و «پیش‌نمایش گزارش» بررسی می‌کند.

اجرا:
    python tools/ui_check_study.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt                                      # noqa: E402
from PySide6.QtWidgets import QApplication                        # noqa: E402
from PySide6 import QtWidgets                                     # noqa: E402

from app.core.settings import AppSettings                          # noqa: E402
from app.core.study import collect_study_results                   # noqa: E402
from app.core.validation import validate_project                   # noqa: E402
from app.report.sections import ReportSection                      # noqa: E402
from app.ui import theme                                           # noqa: E402
from app.ui.main_window import MainWindow                          # noqa: E402
from sample_projects import make_feeder, make_study_project        # noqa: E402

STUDY_SECTIONS = {
    "study_loading": "کنترل بارگذاری فیدر و راهکارهای تعدیل بار",
    "study_conclusion": "نتیجه‌گیری و پیشنهادات",
    "study_demand": "اطلاعات تقاضا",
    "study_substations": "ایستگاه‌های نزدیک به محل تقاضا",
    "study_lines": "خطوط نزدیک به محل تقاضا",
    "study_coincident": "متقاضیان و تقاضاهای همزمان محدوده",
    "study_analysis": "نکات تحلیلی",
    "study_scenarios": "سناریوهای پیشنهادی تأمین برق",
    "study_economics": "بررسی اقتصادی سناریوها",
}


def main() -> int:
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    theme.apply_theme(app, "light")
    win = MainWindow()

    # ---- پروژه نمونه با داده مطالعه مصارف سنگین (+ یک فیدر برای بخش‌های کلاسیک)
    tmp = Path(tempfile.mkdtemp()) / "پروژه_مطالعه_نمونه"
    win.manager.new_project(tmp)
    project = win.manager.project
    project.feeders = [make_feeder()]
    sample = make_study_project()
    # داده نمونه واقعی: افزایش قدرت از ۱۰۰۰ به ۱۲۰۰ کیلووات
    sample.existing_power_kw = 1000.0
    sample.demand.existing_demand_kw = 1000.0
    for field in ("demand", "nearby_substations", "nearby_lines", "coincident_demands",
                  "network_voltage_kv", "reported_total_additional_load_kw",
                  "demand_used_in_analysis_kw", "applicant_name", "name",
                  "report_number", "date_jalali", "requested_power_kw",
                  "existing_power_kw", "request_type"):
        setattr(project, field, getattr(sample, field))
    # فرم‌ها باید با مدل هم‌گام شوند؛ در غیر این صورت _collect_forms هنگام ناوبری
    # مقادیر خالی فرم را روی پروژه می‌نویسد (رفتار عادی برنامه).
    win.project_page.load_from(project)
    win.feeder_page.refresh()
    win.manager.save()
    win._update_project_dependent_pages()

    # ---- گردش در همه صفحات (همان مسیر کاربر واقعی)
    visited = []
    for key in list(win.nav_buttons):
        win.navigate(key)
        visited.append(key)
    assert "analysis" in visited and "preview" in visited and "generate" in visited
    assert "study" in visited, "صفحه مطالعه مصارف سنگین در Sidebar نیست"

    # ---- صفحه «مطالعه مصارف سنگین»: ۶ تب، ستون «در گزارش (On/Off)» و رفت‌وبرگشت داده
    win.navigate("study")
    sp = win.study_page
    assert sp.tabs.count() == 6, f"تعداد تب‌ها: {sp.tabs.count()}"
    assert sp.tbl_substations.rowCount() == 2 and sp.tbl_lines.rowCount() == 2
    assert sp.tbl_coincident.rowCount() == 3
    for tbl in (sp.tbl_substations, sp.tbl_lines, sp.tbl_coincident, sp.tbl_scenarios,
                sp.tbl_neighbors):
        assert tbl.horizontalHeaderItem(0).text() == "در گزارش (On/Off)", tbl.objectName()
    # ویرایش یک خانه و بررسی ذخیره در مدل پروژه (Round-trip)
    sp.tbl_substations.setItem(0, 5, QtWidgets.QTableWidgetItem("61.05"))
    sp.save_to_project()
    assert sp.manager.project.nearby_substations[0].t1_loading_percent == 61.05
    # ثبت آستانه از تنظیمات و بررسی اثر آن روی Rule Engine
    win.settings.study.substation_loading_tolerance_pct = 1.0
    res = [r for r in collect_study_results(win.manager.project, win.settings,
                                            win.analysis.engine)
           if r.rule_id == "SS-LOADING-MISMATCH"]
    assert res, "با تعریف تلورانس، Rule سازگاری بارگیری ایستگاه باید اجرا شود"
    print(f"صفحه مطالعه مصارف سنگین: ۶ تب، ۷ ردیف داده، Rule سازگاری ایستگاه فعال "
          f"({len(res)} مورد) ✅")

    # ---- اصلاحات v1.1.1: ارتفاع دینامیکی جدول متقاضیان، حذف ستون، اسکرول تولید ----
    from PySide6.QtWidgets import QScrollArea, QMessageBox
    from app.ui.study_page import SUBSTATION_COLS
    win.navigate("study")
    sp.tabs.setCurrentIndex(3)
    for _ in range(5):
        QApplication.processEvents()
    tbl = sp.tbl_coincident
    assert tbl.height() >= 220 and tbl.viewport().height() >= 150, \
        f"ارتفاع جدول متقاضیان کافی نیست ({tbl.height()}/{tbl.viewport().height()})"
    before_rows = tbl.rowCount()
    sp._add_row(tbl)
    QApplication.processEvents()
    assert tbl.rowCount() == before_rows + 1 and tbl.rowHeight(tbl.rowCount() - 1) > 0
    print(f"تب متقاضیان: ارتفاع جدول {tbl.height()}px، {tbl.rowCount()} ردیف دیده می‌شود ✅")

    st = sp.tbl_substations
    original = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    try:
        cols_before = st.columnCount()
        sp._del_column(st, "substations", 2)          # ستون ۰ = کلید «در گزارش»
        sp.save_to_project()
        assert st.columnCount() == cols_before - 1
        sp._restore_columns(st, SUBSTATION_COLS)
        assert st.columnCount() == cols_before
    finally:
        QMessageBox.question = original
    print("حذف ستون و بازگرداندن ستون‌ها ✅")

    # ---- صفحه تولید گزارش: اسکرول و نبود فشردگی پس از تولید ----
    win.navigate("generate")
    gp = win.generate_page
    gp.settings.open_folder_after = False
    gp._on_done({"path": tmp / "پیش‌نمایش.docx", "seconds": 1.1,
                 "report": win.analysis.get(), "items": []})
    for _ in range(5):
        QApplication.processEvents()
    inner = gp.result.parentWidget()
    area = inner.parentWidget().parentWidget()
    assert isinstance(area, QScrollArea), "صفحه تولید گزارش اسکرول‌دار نیست"
    assert gp.grp_ready.height() >= gp.grp_ready.minimumHeight()
    assert gp.result.height() >= gp.result.minimumHeight()
    if inner.sizeHint().height() > area.viewport().height():
        assert area.verticalScrollBar().maximum() > 0
    print(f"صفحه تولید گزارش: کارت نتیجه دیده شد، بخش‌ها فشرده نشدند "
          f"(محتوا {inner.sizeHint().height()}px / دید {area.viewport().height()}px) ✅")

    # ---- پروفیل و پیش‌بینی: دو بخش مستقل ----
    win.navigate("profile")
    fp = win.feeder_page
    assert not fp.grp_profile.isHidden() and not fp.grp_forecast.isHidden()
    # در این پروژهٔ نمونه، پیک سال‌های گذشته در جدول «داده واقعی» قابل ورود/ویرایش است
    fp.tbl_peaks.setRowCount(0)
    # ستون‌ها: ۰ = «در گزارش (On/Off)»، ۱ = سال، ۲ = پیک، ۳ = منبع
    for _y, _v in ((1401, 2.2), (1402, 2.4), (1403, 2.6)):
        _r = fp.tbl_peaks.rowCount()
        fp.tbl_peaks.insertRow(_r)
        fp.tbl_peaks.setItem(_r, 0, QtWidgets.QTableWidgetItem(""))
        fp._set_onoff(fp.tbl_peaks, _r, True)
        fp.tbl_peaks.setItem(_r, 1, QtWidgets.QTableWidgetItem(str(_y)))
        fp.tbl_peaks.setItem(_r, 2, QtWidgets.QTableWidgetItem(str(_v)))
        fp.tbl_peaks.setItem(_r, 3, QtWidgets.QTableWidgetItem("MANUAL"))
    fp._peaks_changed()
    assert fp.current.annual_peaks and len(fp.current.annual_peaks) == 3, \
        "پیک‌های واردشده در «داده واقعی» ذخیره نشدند"
    assert fp.tbl_fc_points.columnCount() == 3, "جدول پیش‌بینی باید ستون «در گزارش (On/Off)» داشته باشد"
    print(f"پروفیل و پیش‌بینی جدا شد: داده واقعی {fp.tbl_peaks.rowCount()} سال | "
          f"پیش‌بینی {fp.tbl_fc_points.rowCount()} سال ✅")

    # ---- بررسی صفحه تحلیل: جدول Findings و اعتبارسنجی
    win.navigate("analysis")
    rows = win.analysis_page.tbl_find.rowCount()
    assert rows > 0, "جدول Findings خالی است"
    errs = [i for i in validate_project(win.manager.project, win.settings)
            if i.status == "error"]
    assert not errs, f"خطای اعتبارسنجی: {[i.message for i in errs]}"
    print(f"صفحه تحلیل مهندسی: {rows} Finding در جدول ثبت شد (OK)")

    # ---- بررسی صفحه پیش‌نمایش: وجود بخش‌های مطالعه
    win.navigate("preview")
    report = win.analysis.get()
    assert report is not None, "گزارش ساخته نشد"
    keys = [s.key for s in report.sections]
    missing = [k for k in STUDY_SECTIONS if k not in keys]
    print("بخش‌های گزارش:", " | ".join(keys))
    assert not missing, f"بخش‌های جاافتاده: {missing}"

    # ---- همین بخش‌ها باید در HTML پیش‌نمایش هم دیده شوند
    html = win.preview_page.browser.toHtml()
    absent = [title for title in STUDY_SECTIONS.values() if title not in html]
    assert not absent, f"عناوین دیده‌نشده در پیش‌نمایش: {absent}"
    print(f"پیش‌نمایش HTML: {len(html)} کاراکتر — همه {len(STUDY_SECTIONS)} بخش جدید دیده شد")

    # ---- Findings مطالعه باید در فهرست بازبینی مهندس باشند
    review_findings = [f for f in report.findings if f.domain.startswith("study_")]
    assert review_findings, "هیچ Finding مطالعه‌ای برای بازبینی ثبت نشد"
    win.navigate("review")
    review_rows = win.review_page.list.count()
    assert review_rows >= len(report.findings), "فهرست بازبینی ناقص است"
    print(f"بازبینی مهندس: {review_rows} مورد در فهرست (OK)")

    # ---- تولید فایل Word از همین مسیر برنامه
    from app.report.pipeline import generate_report_full
    out_dir = tmp / "output"
    rep, docx, _items = generate_report_full(
        project, win.settings, tmp / "charts", out_dir,
        engine=win.analysis.engine)
    assert docx.exists() and docx.stat().st_size > 20_000
    print(f"تولید Word: {docx.name} ({docx.stat().st_size / 1024:.0f} کیلوبایت)")

    # ---- جدول‌های مرجع (ایستگاه‌ها، خطوط، نتیجه‌گیری و پیشنهادات)
    from app.report.sections import TableSpec
    tables = {s.key: [b for b in s.blocks if isinstance(b, TableSpec)]
              for s in rep.sections}
    assert tables.get("study_substations"), "جدول ایستگاه‌های نزدیک در گزارش نیست"
    assert tables.get("study_lines"), "جدول خطوط نزدیک در گزارش نیست"
    assert "study_conclusion" in tables, "جدول نتیجه‌گیری و پیشنهادات در گزارش نیست"
    concl = tables["study_conclusion"][0]
    assert [r[0] for r in concl.body_rows] == ["نکات تحلیلی", "سناریوهای پیشنهادی",
                                               "بررسی اقتصادی سناریوها"], \
        [r[0] for r in concl.body_rows]
    line_tbl = tables["study_lines"][0]
    labels = [r[0] for r in line_tbl.body_rows]
    assert any("پیک بار خط در سال" in x for x in labels)
    assert any("افت ولتاژ انتهای خط قبل از اتصال بار جدید" in x for x in labels)
    print("جدول‌های مرجع گزارش: ایستگاه‌ها ✅ | خطوط ✅ | نتیجه‌گیری و پیشنهادات ✅")

    # ---- بررسی نبود متغیر پرنشده در متن‌های تولیدی
    text = "\n".join(p.text for s in rep.sections for p in s.paragraphs())
    assert "{" not in text and "}" not in text, "متغیر پرنشده در متن گزارش"
    print("کیفیت متن: هیچ متغیر پرنشده‌ای وجود ندارد")

    print("\nنتیجه: اجرای کامل برنامه و جریان مطالعه مصارف سنگین بدون خطا انجام شد ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
