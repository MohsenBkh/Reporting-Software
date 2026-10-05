# -*- coding: utf-8 -*-
"""آزمون خودکار بالا آمدن برنامه (Self-check) — مخصوص فایل اجرایی (exe).

کاربرد برای کاربر نهایی (Windows):

    ReportForge.exe --smoke-test

خروجی: کد ۰ اگر برنامه سالم بالا بیاید؛ در غیر این صورت کد ۱ و متن خطا.
گزارش هم روی صفحه (اگر کنسول باشد) و هم در فایل ``ReportForge-smoke.txt``
کنار فایل اجرایی نوشته می‌شود تا در حالت پنجره‌ای هم قابل بررسی باشد.

این ابزار برای تشخیص سریع خطاهای بسته‌بندی (مثل کرش six/shiboken) اضافه شده است.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _report_path() -> Path:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / "ReportForge-smoke.txt"


def _write_report(text: str) -> None:
    try:
        _report_path().write_text(text, encoding="utf-8")
    except Exception:  # noqa: BLE001 — نوشتن گزارش نباید خودش خطا بدهد
        pass


def run_smoke_test(argv: list[str] | None = None) -> int:
    """بررسی گام‌به‌گام شروع برنامه؛ ۰ = سالم."""
    argv = list(sys.argv if argv is None else argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    lines: list[str] = []
    code = 0
    lines.append("ReportForge self-check")
    lines.append("frozen       : %s" % bool(getattr(sys, "frozen", False)))
    lines.append("executable   : %s" % sys.executable)
    lines.append("python       : %s" % sys.version.replace("\n", " "))
    lines.append("meipass      : %s" % getattr(sys, "_MEIPASS", "-"))

    try:
        from app import APP_VERSION
        from app.utils.import_guard import apply_frozen_guards, frozen_guard_report

        lines.append("app version  : %s" % APP_VERSION)

        # پیش از PySide6 (شبیه‌سازی دقیق ترتیب اجرای واقعی)
        apply_frozen_guards()
        for key, value in frozen_guard_report().items():
            lines.append("guard.pre.%-9s: %s" % (key, value))
    except Exception:  # noqa: BLE001
        code = 1
        lines.append("ERROR during guards:\n" + traceback.format_exc())

    if code == 0:
        try:
            import PySide6
            from PySide6.QtCore import QTimer, qVersion
            from PySide6.QtWidgets import QApplication

            lines.append("qt           : %s (PySide6 %s)" % (qVersion(), PySide6.__version__))

            # پس از PySide6: هوک shiboken باید بی‌اثر شده باشد
            from app.utils.import_guard import apply_frozen_guards, frozen_guard_report

            apply_frozen_guards()
            for key, value in frozen_guard_report().items():
                lines.append("guard.post.%-9s: %s" % (key, value))

            # اگر QApplication از قبل ساخته شده باشد (مثلاً در تست‌ها) دوباره ساخته نمی‌شود
            app = QApplication.instance() or QApplication(argv)
            try:
                from app.ui.fonts import apply_ui_font

                apply_ui_font(app)
                lines.append("ui font      : OK")
            except Exception:  # noqa: BLE001
                lines.append("ui font      : skipped (%s)" % traceback.format_exc(limit=0).strip())

            from app.ui.main_window import MainWindow

            window = MainWindow()
            window.show()
            lines.append("main window  : OK")
            lines.append("pages        : %d" % len(window.findChildren(object)))
            QTimer.singleShot(250, app.quit)
            app.exec()
            lines.append("event loop   : OK")
        except Exception:  # noqa: BLE001
            code = 1
            lines.append("ERROR during UI startup:\n" + traceback.format_exc())

    lines.append("RESULT       : %s" % ("OK" if code == 0 else "FAILED"))
    text = "\n".join(lines)
    print(text)
    _write_report(text)
    return code
