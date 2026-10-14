# -*- coding: utf-8 -*-
"""صفحهٔ «دستیار هوش مصنوعی» — ارسال داده‌ها/تصاویر و دریافت پیشنهاد اصلاح متن بخش‌ها.

جریان کاربر: تنظیم اتصال ← انتخاب بخش‌ها و دادهٔ ارسالی ← (اختیاری) ذخیرهٔ بستهٔ ZIP ← تأیید ارسال
← بررسی پیشنهاد هر بخش (متن اصلی در برابر پیشنهاد، هشدار عددهای ناشناخته) ← پذیرش/ویرایش/رد.
هیچ متنی بدون پذیرش مهندس به گزارش برنمی‌گردد.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTextEdit,
                               QVBoxLayout, QWidget)

from app.ai import keystore
from app.ai.package import AIPackage, build_package
from app.ai.providers import PROVIDERS, AIError
from app.ai.service import (Proposal, SectionProposal, apply_section, check_ready,
                            recommend_provider, request_suggestions)
from app.ai.settings import DEFAULT_INSTRUCTIONS, PROVIDER_CUSTOM
from app.ui.widgets import page_header, scrollable

SKIP_SECTIONS = ("notice_unresolved", "prot_notice")


class _Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, pkg: AIPackage, ai, parent=None) -> None:
        super().__init__(parent)
        self.pkg, self.ai = pkg, ai

    def run(self) -> None:                     # نخ جدا: رابط کاربری قفل نمی‌شود
        try:
            self.done.emit(request_suggestions(self.pkg, self.ai))
        except AIError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"خطای پیش‌بینی‌نشده: {e}")


class AIPage(QWidget):
    changed = Signal()

    def __init__(self, manager, settings, get_workspace: Callable, get_report: Callable[[], Any],
                 get_results: Callable[[], dict], on_applied: Optional[Callable[[], None]] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.manager, self.settings = manager, settings
        self._ws, self._get_report, self._get_results = get_workspace, get_report, get_results
        self._on_applied = on_applied
        self._worker: Optional[_Worker] = None
        self._proposal: Optional[Proposal] = None
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.addWidget(page_header(
            "دستیار هوش مصنوعی",
            "بستهٔ داده‌ها، یافته‌های موتور قواعد و تصاویر به سرویس هوش مصنوعی ارسال می‌شود و پیشنهاد اصلاح "
            "متن هر بخش برمی‌گردد؛ فقط پس از پذیرش شما در گزارش ثبت می‌شود."))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        outer.addWidget(split, 1)

        # ---------------- ستون تنظیمات ----------------
        left = QWidget()
        lv = QVBoxLayout(left)
        g1 = QGroupBox("اتصال به سرویس")
        f1 = QFormLayout(g1)
        self.cb_provider = QComboBox()
        for key, prov in PROVIDERS.items():
            self.cb_provider.addItem(prov.label, key)
        self.ed_model = QLineEdit()
        self.ed_model.setPlaceholderText("نام مدل را از پنل ارائه‌دهنده وارد کنید")
        self.ed_base = QLineEdit()
        self.ed_base.setPlaceholderText("https://.../v1")
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_key.setPlaceholderText("کلید API (خارج از پروژه ذخیره می‌شود)")
        self.btn_save_key = QPushButton("ذخیرهٔ کلید")
        self.lbl_key = QLabel("")
        self.lbl_key.setObjectName("Muted")
        self.lbl_key.setWordWrap(True)
        f1.addRow("ارائه‌دهنده:", self.cb_provider)
        f1.addRow("مدل:", self.ed_model)
        f1.addRow("آدرس پایه:", self.ed_base)
        f1.addRow("کلید API:", self.ed_key)
        f1.addRow("", self.btn_save_key)
        f1.addRow("", self.lbl_key)
        lv.addWidget(g1)

        g2 = QGroupBox("دادهٔ ارسالی (حریم خصوصی)")
        v2 = QVBoxLayout(g2)
        self.chk_images = QCheckBox("ارسال تصاویر پروژه")
        self.chk_anon = QCheckBox("حذف نام متقاضی و کارشناس")
        self.chk_find = QCheckBox("ارسال یافته‌های موتور قواعد")
        self.sp_images = QSpinBox()
        self.sp_images.setRange(0, 30)
        row = QHBoxLayout()
        row.addWidget(QLabel("حداکثر تعداد تصویر:"))
        row.addWidget(self.sp_images)
        row.addStretch(1)
        for w in (self.chk_images, self.chk_anon, self.chk_find):
            v2.addWidget(w)
        v2.addLayout(row)
        lv.addWidget(g2)

        g3 = QGroupBox("بخش‌های گزارش برای اصلاح")
        v3 = QVBoxLayout(g3)
        self.sections = QListWidget()
        self.sections.setMinimumHeight(150)
        v3.addWidget(self.sections)
        self.btn_reload = QPushButton("تازه‌سازی فهرست بخش‌ها")
        v3.addWidget(self.btn_reload)
        lv.addWidget(g3)

        g4 = QGroupBox("دستورالعمل به مدل")
        v4 = QVBoxLayout(g4)
        self.txt_instr = QPlainTextEdit()
        self.txt_instr.setMinimumHeight(120)
        self.btn_reset_instr = QPushButton("بازگشت به دستورالعمل پیش‌فرض")
        v4.addWidget(self.txt_instr)
        v4.addWidget(self.btn_reset_instr)
        lv.addWidget(g4)

        bar = QHBoxLayout()
        self.btn_zip = QPushButton("ذخیرهٔ بستهٔ ZIP…")
        self.btn_send = QPushButton("ارسال به هوش مصنوعی")
        self.btn_send.setObjectName("primary")
        bar.addWidget(self.btn_zip)
        bar.addWidget(self.btn_send)
        lv.addLayout(bar)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("Muted")
        self.lbl_status.setWordWrap(True)
        lv.addWidget(self.lbl_status)
        lv.addStretch(1)
        # ستون تنظیمات داخل ScrollArea: در پنجره‌های کوچک، باکس‌ها فشرده/پنهان
        # نمی‌شوند و نوار اسکرول عمودی ظاهر می‌شود.
        lv.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        left_scroll = scrollable(left)
        left_scroll.setMinimumWidth(300)
        split.addWidget(left_scroll)

        # ---------------- ستون نتایج ----------------
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel("پیشنهادها (هر بخش را بررسی و در صورت تأیید بپذیرید):"))
        self.results = QListWidget()
        self.results.setMaximumHeight(170)
        rv.addWidget(self.results)
        self.lbl_notes = QLabel("")
        self.lbl_notes.setWordWrap(True)
        self.lbl_notes.setObjectName("Muted")
        rv.addWidget(self.lbl_notes)
        self.lbl_warn = QLabel("")
        self.lbl_warn.setObjectName("FieldError")
        self.lbl_warn.setWordWrap(True)
        rv.addWidget(self.lbl_warn)
        texts = QSplitter(Qt.Vertical)
        texts.setChildrenCollapsible(False)
        self.txt_orig = QTextEdit()
        self.txt_orig.setReadOnly(True)
        self.txt_sug = QTextEdit()
        self.txt_sug.setAcceptRichText(False)
        for title, w in (("متن فعلی گزارش", self.txt_orig), ("متن پیشنهادی (قابل ویرایش)", self.txt_sug)):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            w.setMinimumHeight(110)
            bl.addWidget(w)
            texts.addWidget(box)
        rv.addWidget(texts, 1)
        btns = QHBoxLayout()
        self.btn_accept = QPushButton("پذیرفتن این بخش")
        self.btn_accept.setObjectName("primary")
        self.btn_reject = QPushButton("رد پیشنهاد")
        self.btn_accept_all = QPushButton("پذیرفتن همهٔ بخش‌های بدون هشدار عدد")
        for b in (self.btn_accept, self.btn_reject, self.btn_accept_all):
            btns.addWidget(b)
        rv.addLayout(btns)
        # ستون نتایج نیز اسکرول‌پذیر: باکس‌های «متن فعلی/پیشنهادی» در ارتفاع کم
        # به‌جای حذف‌شدن از دید، با اسکرول در دسترس می‌مانند.
        rv.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        right_scroll = scrollable(right)
        right_scroll.setMinimumWidth(340)
        split.addWidget(right_scroll)
        split.setSizes([430, 650])
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        self.cb_provider.currentIndexChanged.connect(self._on_provider)
        for w in (self.ed_model, self.ed_base):
            w.textChanged.connect(self._store_settings)
        for w in (self.chk_images, self.chk_anon, self.chk_find):
            w.toggled.connect(self._store_settings)
        self.sp_images.valueChanged.connect(self._store_settings)
        self.txt_instr.textChanged.connect(self._store_settings)
        self.btn_save_key.clicked.connect(self._save_key)
        self.btn_reload.clicked.connect(self.refresh_sections)
        self.btn_reset_instr.clicked.connect(lambda: self.txt_instr.setPlainText(DEFAULT_INSTRUCTIONS))
        self.btn_zip.clicked.connect(self._save_zip)
        self.btn_send.clicked.connect(self._send)
        self.results.currentRowChanged.connect(self._show_proposal)
        self.btn_accept.clicked.connect(self._accept)
        self.btn_reject.clicked.connect(self._reject)
        self.btn_accept_all.clicked.connect(self._accept_all)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        ai = self.settings.ai
        self._loading = True
        if not keystore.has_key(ai.provider):
            ai.provider = recommend_provider(ai)
        self.cb_provider.setCurrentIndex(max(0, self.cb_provider.findData(ai.provider)))
        self.ed_model.setText(ai.model())
        self.ed_base.setText(ai.custom_base_url)
        self.chk_images.setChecked(ai.send_images)
        self.chk_anon.setChecked(ai.anonymize_people)
        self.chk_find.setChecked(ai.include_findings)
        self.sp_images.setValue(ai.max_images)
        self.txt_instr.setPlainText(ai.instructions)
        self._loading = False
        self._update_provider_ui()
        self.refresh_sections()

    def _update_provider_ui(self) -> None:
        custom = self.settings.ai.provider == PROVIDER_CUSTOM
        self.ed_base.setEnabled(custom)
        key = keystore.get_key(self.settings.ai.provider)
        self.lbl_key.setText((f"کلید موجود است ({keystore.mask(key)})." if key else
                              "کلید ثبت نشده است.") +
                             f" متغیر محیطی پیشنهادی: {keystore.ENV_NAMES[self.settings.ai.provider]}")

    def refresh_sections(self) -> None:
        self.sections.clear()
        report = self._get_report() if self.manager.project else None
        if report is None:
            return
        for sec in report.sections:
            if sec.key in SKIP_SECTIONS:
                continue
            it = QListWidgetItem(sec.title)
            it.setData(Qt.UserRole, sec.key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.sections.addItem(it)

    def _selected_keys(self) -> list[str]:
        return [self.sections.item(i).data(Qt.UserRole) for i in range(self.sections.count())
                if self.sections.item(i).checkState() == Qt.Checked]

    # ------------------------------------------------------------------
    def _store_settings(self, *_a) -> None:
        if self._loading:
            return
        ai = self.settings.ai
        ai.models[ai.provider] = self.ed_model.text().strip()
        ai.custom_base_url = self.ed_base.text().strip()
        ai.send_images, ai.anonymize_people = self.chk_images.isChecked(), self.chk_anon.isChecked()
        ai.include_findings, ai.max_images = self.chk_find.isChecked(), self.sp_images.value()
        ai.instructions = self.txt_instr.toPlainText().strip() or DEFAULT_INSTRUCTIONS

    def _on_provider(self, _i: int) -> None:
        if self._loading:
            return
        self.settings.ai.provider = self.cb_provider.currentData()
        self._loading = True
        self.ed_model.setText(self.settings.ai.model())
        self._loading = False
        self._update_provider_ui()

    def _save_key(self) -> None:
        keystore.set_key(self.settings.ai.provider, self.ed_key.text())
        self.ed_key.clear()
        self._update_provider_ui()
        self._persist()

    def _persist(self) -> None:
        try:
            self.settings.save()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    def _build_package(self) -> Optional[AIPackage]:
        project, ws = self.manager.project, self._ws()
        report = self._get_report()
        if project is None or ws is None or report is None:
            QMessageBox.warning(self, "هوش مصنوعی", "ابتدا گزارش را آماده کنید (پروژه باز و تحلیل انجام شده باشد).")
            return None
        self._store_settings()
        return build_package(project, ws, report, self._get_results(), self.settings.ai,
                             self.manager.image_path, self._selected_keys())

    def _save_zip(self) -> None:
        pkg = self._build_package()
        if pkg is None:
            return
        path = QFileDialog.getSaveFileName(self, "ذخیرهٔ بستهٔ هوش مصنوعی", "ReportForge-AI-package.zip",
                                           "ZIP (*.zip)")[0]
        if path:
            pkg.to_zip(path)
            self.lbl_status.setText(f"بسته ذخیره شد: {path} — {pkg.summary()}")

    def _send(self) -> None:
        if self._worker is not None:
            return
        problem = check_ready(self.settings.ai)
        if problem:
            QMessageBox.warning(self, "هوش مصنوعی", problem)
            return
        pkg = self._build_package()
        if pkg is None:
            return
        ai = self.settings.ai
        ret = QMessageBox.question(
            self, "تأیید ارسال",
            f"داده‌ها به سرور «{PROVIDERS[ai.provider].label}» (مدل {ai.model()}) ارسال می‌شود:\n"
            f"{pkg.summary()}\n"
            f"نام اشخاص: {'حذف می‌شود' if ai.anonymize_people else 'ارسال می‌شود'}\n"
            + ("\n".join(pkg.warnings) + "\n" if pkg.warnings else "")
            + "\nبرای دادهٔ محرمانه از سیاست‌های سازمان خود پیروی کنید. ارسال انجام شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        self._persist()
        self.btn_send.setEnabled(False)
        self.lbl_status.setText("در حال ارسال و انتظار برای پاسخ…")
        self._worker = _Worker(pkg, ai, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self) -> None:
        self._worker = None
        self.btn_send.setEnabled(True)

    def _on_failed(self, msg: str) -> None:
        self.lbl_status.setText("ناموفق")
        QMessageBox.warning(self, "هوش مصنوعی", msg)

    def _on_done(self, proposal: Proposal) -> None:
        self._proposal = proposal
        self.lbl_status.setText(f"{len(proposal.sections)} پیشنهاد دریافت شد.")
        self.lbl_notes.setText(("توضیح مدل: " + proposal.notes) if proposal.notes else "")
        self.results.clear()
        for sp in proposal.sections:
            self.results.addItem(QListWidgetItem(self._row_text(sp)))
        if proposal.sections:
            self.results.setCurrentRow(0)

    @staticmethod
    def _row_text(sp: SectionProposal) -> str:
        mark = "✓ " if sp.accepted else ("⚠ " if sp.unverified else "")
        return f"{mark}{sp.title}" + (f"  (عدد ناشناخته: {len(sp.unverified)})" if sp.unverified else "")

    # ------------------------------------------------------------------
    def _current(self) -> Optional[SectionProposal]:
        row = self.results.currentRow()
        if self._proposal is None or not (0 <= row < len(self._proposal.sections)):
            return None
        return self._proposal.sections[row]

    def _show_proposal(self, _row: int) -> None:
        sp = self._current()
        if sp is None:
            return
        self.txt_orig.setPlainText(sp.original)
        self.txt_sug.setPlainText(sp.suggested)
        self.lbl_warn.setText(("⚠ عددهای زیر در داده‌ها/متن اصلی نبودند و ممکن است توسط مدل ساخته شده باشند — "
                               "پیش از پذیرش بررسی کنید: " + "، ".join(sp.unverified)) if sp.unverified else "")

    def _apply(self, sp: SectionProposal, text: Optional[str] = None) -> None:
        if self.manager.project is None:
            return
        apply_section(self.manager.project, sp, text)
        self.manager.dirty = True
        if self._on_applied:
            self._on_applied()
        self.changed.emit()

    def _accept(self) -> None:
        sp = self._current()
        if sp is None:
            return
        if sp.unverified:
            ret = QMessageBox.question(self, "عدد ناشناخته", "این متن عددهایی دارد که در داده‌ها نیست: "
                                       + "، ".join(sp.unverified) + "\nبا وجود این پذیرفته شود؟",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        self._apply(sp, self.txt_sug.toPlainText())
        self.results.currentItem().setText(self._row_text(sp))

    def _reject(self) -> None:
        sp = self._current()
        if sp is not None:
            self.txt_sug.setPlainText(sp.original)
            self.lbl_status.setText(f"پیشنهاد «{sp.title}» رد شد (متن فعلی حفظ شد).")

    def _accept_all(self) -> None:
        if self._proposal is None:
            return
        n = 0
        for i, sp in enumerate(self._proposal.sections):
            if not sp.unverified and sp.changed and not sp.accepted:
                self._apply(sp)
                self.results.item(i).setText(self._row_text(sp))
                n += 1
        self.lbl_status.setText(f"{n} بخش پذیرفته شد؛ بخش‌های دارای هشدار عدد باید جداگانه بررسی شوند.")
