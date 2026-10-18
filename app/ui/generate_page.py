# -*- coding: utf-8 -*-
"""صفحه «تولید گزارش» — آمادگی، تنظیمات خروجی، تولید Word در Background با Progress (v1.0.3)."""
from __future__ import annotations

import copy
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QVBoxLayout, QWidget)

from app.core.findings import unresolved
from app.core.validation import has_errors, summary_counts, validate_project
from app.report import pipeline
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine
from app.ui.widgets import StatusBadge, page_header, scrollable
from app.utils.errors import friendly_error, log_exception

TEMPLATES = {"standard": "قالب استاندارد دفترچه مطالعات (TAV111-10/00 — اردبیل)"}


class GenerateWorker(QObject):
    """تولید گزارش در Thread جدا تا UI قفل نشود."""
    progress = Signal(int, str)
    finished = Signal(object)     # dict نتیجه
    failed = Signal(object)       # Exception

    def __init__(self, project, settings, charts_dir: Path, out_path: Path,
                 texts, engine, image_resolver, profile_loader) -> None:
        super().__init__()
        self.args = (project, settings, charts_dir, out_path, texts, engine,
                     image_resolver, profile_loader)

    @Slot()
    def run(self) -> None:
        project, settings, charts_dir, out_path, texts, engine, resolver, loader = self.args
        t0 = time.time()
        try:
            self.progress.emit(10, "اعتبارسنجی نهایی ورودی‌ها…")
            items = validate_project(project, settings)
            if has_errors(items):
                raise ValueError("اعتبارسنجی ناموفق است.")
            self.progress.emit(30, "تولید متن، جدول‌ها و نمودارها…")
            Path(charts_dir).mkdir(parents=True, exist_ok=True)
            report = pipeline.build_sections(project, settings, texts, engine, charts_dir,
                                             resolver, loader)
            self.progress.emit(70, "ساخت فایل Word (RTL، فهرست مطالب، سربرگ/پاورقی)…")
            pipeline.generate_docx(project, settings, report, out_path)
            self.progress.emit(100, "پایان")
            self.finished.emit({"path": out_path, "seconds": time.time() - t0,
                                "report": report, "items": items})
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "تولید گزارش Word")
            self.failed.emit(exc)


class GeneratePage(QWidget):
    changed = Signal()
    generated = Signal(str)
    navigate_requested = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, manager, settings, analysis, parent=None) -> None:
        super().__init__(parent)
        self.manager, self.settings, self.analysis = manager, settings, analysis
        self._thread: QThread | None = None
        self._worker: GenerateWorker | None = None
        self.last_path: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        outer.addWidget(scrollable(inner))
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header("تولید گزارش",
                                   "پس از بررسی آمادگی پروژه و تنظیمات خروجی، فایل Word نهایی تولید می‌شود."))

        # --- آمادگی ---
        self.grp_ready = QGroupBox("آمادگی برای تولید")
        gl = QVBoxLayout(self.grp_ready)
        self.ready_rows: dict[str, tuple[StatusBadge, QLabel]] = {}
        for key, title, step in (("val", "اعتبارسنجی ورودی‌ها", "analysis"),
                                 ("review", "بازبینی مهندس", "review"),
                                 ("manual", "ویرایش‌های دستی متن", "preview")):
            row = QHBoxLayout()
            badge = StatusBadge("—", "pending")
            badge.setMinimumWidth(110)
            lbl = QLabel(title)
            msg = QLabel("")
            msg.setObjectName("Muted")
            btn = QPushButton("مشاهده")
            btn.setObjectName("ghost")
            btn.clicked.connect(lambda _=False, s=step: self.navigate_requested.emit(s))
            row.addWidget(badge)
            row.addWidget(lbl)
            row.addWidget(msg, 1)
            row.addWidget(btn)
            gl.addLayout(row)
            self.ready_rows[key] = (badge, msg)
        self.grp_ready.setMinimumHeight(150)
        root.addWidget(self.grp_ready)

        # --- تنظیمات خروجی ---
        grp = QGroupBox("تنظیمات خروجی")
        f = QFormLayout(grp)
        self.cb_template = QComboBox()
        for k, v in TEMPLATES.items():
            self.cb_template.addItem(v, k)
        f.addRow("قالب (Template):", self.cb_template)
        self.ed_dir = QLineEdit()
        btn_dir = QPushButton("…")
        btn_dir.setFixedWidth(36)
        btn_dir.setToolTip("انتخاب پوشه خروجی")
        btn_dir.clicked.connect(self._pick_dir)
        row = QHBoxLayout()
        row.addWidget(self.ed_dir)
        row.addWidget(btn_dir)
        f.addRow("پوشه خروجی:", row)
        self.ed_name = QLineEdit()
        f.addRow("نام فایل:", self.ed_name)
        self.chk_app = QCheckBox("درج پیوست‌ها (ردیابی منبع داده‌ها و تصمیمات مهندس)")
        self.chk_open = QCheckBox("پس از تولید، پوشه خروجی باز شود")
        f.addRow(self.chk_app)
        f.addRow(self.chk_open)
        root.addWidget(grp)

        # --- قالب گزارش (ذخیره/بارگذاری فایل مجزا) ---
        grp_t = QGroupBox("قالب گزارش — ذخیره و بارگذاری مجزا")
        tl = QVBoxLayout(grp_t)
        trow = QHBoxLayout()
        btn_tsave = QPushButton("ذخیره قالب در فایل…")
        btn_tsave.setToolTip("ذخیره متن‌های قالب جاری در فایل JSON مجزا برای استفاده مجدد یا انتقال")
        btn_tload = QPushButton("بارگذاری قالب از فایل…")
        btn_treset = QPushButton("بازگشت به پیش‌فرض")
        trow.addWidget(btn_tsave)
        trow.addWidget(btn_tload)
        trow.addWidget(btn_treset)
        trow.addStretch(1)
        tl.addLayout(trow)
        self.lbl_template = QLabel("")
        self.lbl_template.setObjectName("Muted")
        self.lbl_template.setWordWrap(True)
        tl.addWidget(self.lbl_template)
        root.addWidget(grp_t)
        btn_tsave.clicked.connect(self._save_template)
        btn_tload.clicked.connect(self._load_template)
        btn_treset.clicked.connect(self._reset_template)

        # --- اجرا ---
        run = QHBoxLayout()
        self.btn_generate = QPushButton("تولید گزارش Word")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setMinimumHeight(38)
        self.btn_open_dir = QPushButton("باز کردن پوشه خروجی")
        self.btn_open_file = QPushButton("باز کردن فایل")
        self.btn_open_file.setEnabled(False)
        run.addWidget(self.btn_generate)
        run.addWidget(self.btn_open_file)
        run.addWidget(self.btn_open_dir)
        run.addStretch(1)
        root.addLayout(run)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.lbl_progress = QLabel("")
        self.lbl_progress.setObjectName("Muted")
        root.addWidget(self.lbl_progress)

        # --- نتیجه ---
        self.result = QFrame()
        self.result.setObjectName("Card")
        rl = QVBoxLayout(self.result)
        head = QHBoxLayout()
        self.res_badge = StatusBadge("", "completed")
        self.res_title = QLabel("")
        self.res_title.setObjectName("SectionTitle")
        head.addWidget(self.res_badge)
        head.addWidget(self.res_title, 1)
        rl.addLayout(head)
        self.res_text = QLabel("")
        self.res_text.setWordWrap(True)
        self.res_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rl.addWidget(self.res_text)
        self.result.setVisible(False)
        self.result.setMinimumHeight(96)
        root.addWidget(self.result)
        root.addStretch(1)

        self.btn_generate.clicked.connect(self.generate)
        self.btn_open_dir.clicked.connect(self.open_output_dir)
        self.btn_open_file.clicked.connect(lambda: self._open(self.last_path))
        self.chk_app.toggled.connect(self._opts_changed)
        self.chk_open.toggled.connect(self._opts_changed)

    # ------------------------------------------------------------------
    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "پوشه خروجی", self.ed_dir.text())
        if d:
            self.ed_dir.setText(d)

    def _opts_changed(self) -> None:
        self.settings.include_appendices = self.chk_app.isChecked()
        self.settings.open_folder_after = self.chk_open.isChecked()
        self.settings.save()
        self.analysis.invalidate()

    # ------------------------------------------------------------------
    # قالب گزارش (فایل مجزا)
    # ------------------------------------------------------------------
    def _update_template_label(self) -> None:
        tf = getattr(self.settings, "template_file", "") or ""
        if tf:
            self.lbl_template.setText(f"قالب فعال: {Path(tf).name}")
        else:
            self.lbl_template.setText("قالب فعال: پیش‌فرض‌های همراه برنامه (بدون فایل قالب)")

    def _save_template(self) -> None:
        suggested = self.settings.template_file or "قالب-گزارش.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره قالب گزارش", suggested, "قالب گزارش (*.json)")
        if not path:
            return
        try:
            dest = self.analysis.texts.save_as_template(path)
            self.settings.template_file = str(dest)
            self.settings.save()
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "ذخیره قالب گزارش")
            QMessageBox.critical(self, "ذخیره قالب", f"ذخیره قالب ناموفق بود:\n{exc}")
            return
        self._update_template_label()
        self.analysis.invalidate()
        self.statusBar_msg(f"قالب گزارش ذخیره شد: {dest}")

    def _load_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "بارگذاری قالب گزارش", "", "قالب گزارش (*.json)")
        if not path:
            return
        if not self.analysis.texts.load_template_file(path):
            QMessageBox.warning(self, "بارگذاری قالب",
                                "فایل انتخاب‌شده قالب معتبری نیست (هیچ متنی در آن یافت نشد).")
            return
        self.settings.template_file = path
        self.settings.save()
        self._update_template_label()
        self.analysis.invalidate()
        self.statusBar_msg(f"قالب گزارش بارگذاری شد: {Path(path).name}")

    def _reset_template(self) -> None:
        self.settings.template_file = ""
        self.settings.save()
        self.analysis.texts = TemplateManager.from_settings(self.settings)
        self._update_template_label()
        self.analysis.invalidate()
        self.statusBar_msg("قالب گزارش به پیش‌فرض بازگشت.")

    def statusBar_msg(self, text: str) -> None:
        """پیام کوتاه در StatusBar پنجره اصلی (در صورت اتصال از بیرون)."""
        try:
            from PySide6.QtWidgets import QApplication
            w = QApplication.instance().activeWindow()
            if w is not None and hasattr(w, "statusBar"):
                w.statusBar().showMessage(text, 5000)
        except Exception:  # noqa: BLE001
            pass

    def reset_for_project(self) -> None:
        self.ed_dir.clear()
        self.ed_name.clear()
        self.result.setVisible(False)
        self.last_path = None
        self.btn_open_file.setEnabled(False)

    def refresh(self) -> None:
        project = self.manager.project
        self._update_template_label()
        self.chk_app.blockSignals(True)
        self.chk_open.blockSignals(True)
        self.chk_app.setChecked(self.settings.include_appendices)
        self.chk_open.setChecked(self.settings.open_folder_after)
        self.chk_app.blockSignals(False)
        self.chk_open.blockSignals(False)
        if project is None:
            self.btn_generate.setEnabled(False)
            return
        if not self.ed_dir.text():
            self.ed_dir.setText(str(self.manager.output_dir))
        if not self.ed_name.text():
            self.ed_name.setText(pipeline.docx_filename(project))
        items = validate_project(project, self.settings)
        errors, warns = summary_counts(items)
        b, m = self.ready_rows["val"]
        if errors:
            b.set_state("error", "Error")
            m.setText(f"{errors} خطا و {warns} هشدار — ابتدا خطاها را برطرف کنید.")
        elif warns:
            b.set_state("warning", "Warning")
            m.setText(f"{warns} هشدار (تولید مجاز است).")
        else:
            b.set_state("normal", "Normal")
            m.setText("همه ورودی‌ها معتبر است.")
        b, m = self.ready_rows["review"]
        pending = []
        if not errors:
            report = self.analysis.get()
            pending = unresolved(report.findings) if report else []
        if errors:
            b.set_state("pending", "—")
            m.setText("پس از رفع خطاهای ورودی بررسی می‌شود.")
        elif pending:
            b.set_state("review", "Requires Review")
            m.setText(f"{len(pending)} مورد هنوز بازبینی نشده است.")
        else:
            b.set_state("completed", "Completed")
            m.setText("همه نتیجه‌گیری‌ها بازبینی شده است.")
        b, m = self.ready_rows["manual"]
        n_manual = len([k for k, v in (project.manual_texts or {}).items() if v.strip()])
        n_rev = len([d for d in project.reviews.values() if d.status != "pending"])
        b.set_state("info" if (n_manual or n_rev) else "pending", "ثبت شده" if (n_manual or n_rev) else "—")
        m.setText(f"{n_manual} بخش با متن دستی، {n_rev} تصمیم مهندس — با تولید مجدد حفظ می‌شود.")
        self.btn_generate.setEnabled(not errors and self._thread is None)

    # ------------------------------------------------------------------
    def generate(self) -> None:
        project = self.manager.project
        if not project or self._thread is not None:
            return
        items = validate_project(project, self.settings)
        if has_errors(items):
            QMessageBox.warning(self, "تولید گزارش", "ابتدا خطاهای اعتبارسنجی را برطرف کنید.")
            return
        report = self.analysis.get()
        pending = unresolved(report.findings) if report else []
        if pending:
            ret = QMessageBox.question(
                self, "موارد بازبینی‌نشده",
                f"{len(pending)} نتیجه‌گیری هنوز توسط مهندس بازبینی نشده است.\n"
                "با این حال گزارش تولید شود؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                self.navigate_requested.emit("review")
                return
        out_dir = Path(self.ed_dir.text().strip() or self.manager.output_dir)
        name = self.ed_name.text().strip() or pipeline.docx_filename(project)
        if not name.lower().endswith(".docx"):
            name += ".docx"
        out_path = out_dir / name
        if out_path.exists():
            ret = QMessageBox.question(self, "فایل موجود است",
                                       f"فایل «{name}» از قبل وجود دارد. جایگزین شود؟",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            self.manager.save()
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return
        # کپی مستقل از پروژه تا ویرایش همزمان UI روی خروجی اثر نگذارد
        self._worker = GenerateWorker(
            copy.deepcopy(project), self.settings, self.manager.charts_dir(), out_path,
            TemplateManager.from_settings(self.settings), RuleEngine(),
            self.manager.image_path, self.manager.get_profile)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self.result.setVisible(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.btn_generate.setEnabled(False)
        self.busy_changed.emit(True)
        self._thread.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress.setValue(pct)
        self.lbl_progress.setText(msg)

    def _end(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None
        self.progress.setVisible(False)
        self.lbl_progress.setText("")
        self.busy_changed.emit(False)
        self.refresh()

    def _on_done(self, res: dict) -> None:
        path = Path(res["path"])
        self._end()
        self.last_path = path
        self.btn_open_file.setEnabled(True)
        proj = self.manager.project
        if proj:
            proj.last_report_path = str(path)
            proj.last_report_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                self.manager.save()
            except Exception:  # noqa: BLE001
                pass
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        rep = res["report"]
        n_tbl = sum(1 for s in rep.sections for b in s.blocks if type(b).__name__ == "TableSpec")
        n_fig = sum(1 for s in rep.sections for b in s.blocks if type(b).__name__ == "FigureBlock")
        self.res_badge.set_state("completed", "Completed")
        self.res_title.setText("گزارش با موفقیت تولید شد")
        warn = ("\n⚠ " + "\n⚠ ".join(rep.warnings)) if rep.warnings else ""
        self.res_text.setText(
            f"{path}\n{size_kb:,.0f} KB · {len(rep.sections)} بخش · {n_tbl} جدول · {n_fig} شکل · "
            f"{res['seconds']:.1f} ثانیه\nبرای تکمیل فهرست مطالب هنگام باز شدن فایل در Word گزینه «Yes» را بزنید." + warn)
        self.result.setVisible(True)
        self.generated.emit(str(path))
        if self.settings.open_folder_after:
            self.open_output_dir()

    def _on_failed(self, exc: Exception) -> None:
        self._end()
        self._show_error(exc)

    def _show_error(self, exc: Exception) -> None:
        ue = friendly_error(exc, "تولید گزارش")
        self.res_badge.set_state("error", "Error")
        self.res_title.setText("تولید گزارش ناموفق بود")
        self.res_text.setText(ue.text())
        self.result.setVisible(True)

    # ------------------------------------------------------------------
    def open_output_dir(self) -> None:
        d = Path(self.ed_dir.text().strip() or self.manager.output_dir)
        d.mkdir(parents=True, exist_ok=True)
        self._open(d)

    @staticmethod
    def _open(path) -> None:
        if not path:
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])  # noqa: S603, S607
            else:
                subprocess.Popen(["xdg-open", str(path)])  # noqa: S603, S607
        except Exception:  # noqa: BLE001 — باز کردن ناموفق نباید خطا بدهد
            pass
