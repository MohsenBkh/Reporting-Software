# -*- coding: utf-8 -*-
"""پنجره اصلی — Sidebar، هدر پروژه با وضعیت، نوار مراحل Workflow، StatusBar، Auto Save (v1.0.3)."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from app import APP_NAME, APP_NAME_FA, APP_VERSION
from app.core import workflow
from app.core.project_manager import ProjectManager
from app.core.settings import AppSettings
from app.core.validation import summary_counts, validate_project
from app.excel import importer as excel_importer
from app.report.analysis import AnalysisService
from app.ui import theme as theme_mod
from app.ui.analysis_page import AnalysisPage
from app.ui.feeder_page import FeederPage
from app.ui.generate_page import GeneratePage
from app.ui.home_page import HomePage
from app.ui.icons import icon
from app.ui.images_page import ImagesPage
from app.ui.preview_page import PreviewPage
from app.ui.project_page import ProjectPage
from app.ui.review_page import ReviewPage
from app.ui.settings_page import SettingsPage
from app.ui.study_page import StudyPage
from app.ui.widgets import StatusBadge, StepBar
from app.utils.errors import handle_error, log_exception

# (کلید ناوبری، عنوان، آیکن، نیازمند پروژه؟)
NAV = [
    ("home", "داشبورد", "dashboard", False),
    ("project", "اطلاعات پروژه", "project", True),
    ("input", "ورود داده", "input", True),
    ("profile", "پروفیل و پیش‌بینی", "profile", True),
    ("loadflow", "نتایج پخش بار", "loadflow", True),
    ("study", "مطالعه مصارف سنگین", "study", True),
    ("images", "تصاویر", "images", True),
    ("analysis", "تحلیل مهندسی", "analysis", True),
    ("review", "بازبینی مهندس", "review", True),
    ("preview", "پیش‌نمایش گزارش", "preview", True),
    ("generate", "تولید گزارش", "generate", True),
    ("settings", "تنظیمات", "settings", False),
]
GROUPS = {"project": "مراحل کار", "settings": "سیستم"}
# مرحله Workflow → صفحه
STEP_TO_PAGE = {"project": "project", "input": "input", "validation": "analysis",
                "analysis": "analysis", "review": "review", "preview": "preview",
                "generate": "generate", "loadflow": "loadflow", "profile": "profile"}
FEEDER_SECTIONS = {"input", "profile", "loadflow"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings.load()
        self.manager = ProjectManager(self.settings)
        self.analysis = AnalysisService(self.manager, self.settings)
        self.current_key = "home"
        self._report_generated = False

        self.setWindowTitle(f"{APP_NAME_FA} — {APP_NAME} {APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 640)
        self._build_ui()
        self.apply_theme(self.settings.theme)

        self._autosave = QTimer(self)
        self._autosave.setInterval(60_000)
        self._autosave.timeout.connect(self._autosave_tick)
        self._autosave.start()
        self._refresh_timer = QTimer(self)      # به‌روزرسانی هدر با تأخیر تا UI سنگین نشود
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(350)
        self._refresh_timer.timeout.connect(self._refresh_status)

    # ------------------------------------------------------------------
    def apply_theme(self, name: str) -> None:
        self.settings.theme = name if name in theme_mod.THEMES else "light"
        QApplication.instance().setStyleSheet(theme_mod.build_qss(self.settings.theme))
        t = theme_mod.tokens(self.settings.theme)
        for key, _cap, ic, _req in NAV:
            self.nav_buttons[key].setIcon(icon(ic, t["sidebar_text"], 20))
        self.btn_save.setIcon(icon("save", t["on_primary"], 18))
        self.btn_theme.setIcon(icon("moon", t["text"], 18))
        self.btn_theme.setToolTip("تعویض Theme روشن/تاریک")
        self.home_page.apply_icons(self.settings.theme)
        self.review_page.apply_icons()
        if self.manager.project:
            self._refresh_status()
            self.analysis_page.refresh()
            self.review_page.refresh()

    def toggle_theme(self) -> None:
        self.apply_theme("dark" if self.settings.theme == "light" else "light")
        self.settings.save()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(214)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(10, 16, 10, 12)
        sv.setSpacing(2)
        t = QLabel(APP_NAME_FA)
        t.setObjectName("SidebarTitle")
        s = QLabel(f"{APP_NAME} {APP_VERSION}")
        s.setObjectName("SidebarSub")
        sv.addWidget(t)
        sv.addWidget(s)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, caption, _ic, _req in NAV:
            if key in GROUPS:
                g = QLabel(GROUPS[key])
                g.setObjectName("SidebarGroup")
                sv.addWidget(g)
            b = QPushButton(f"  {caption}")
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(b.iconSize().expandedTo(b.iconSize()))
            b.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self.nav_buttons[key] = b
            sv.addWidget(b)
        sv.addStretch(1)
        self.lbl_side = QLabel("")
        self.lbl_side.setObjectName("SidebarFooter")
        self.lbl_side.setWordWrap(True)
        sv.addWidget(self.lbl_side)
        root.addWidget(sidebar)

        # --- ناحیه اصلی ---
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)
        root.addWidget(main, 1)

        header = QFrame()
        header.setObjectName("HeaderBar")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 8, 20, 8)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.lbl_proj = QLabel("پروژه‌ای باز نیست")
        self.lbl_proj.setObjectName("ProjectName")
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("ProjectMeta")
        names.addWidget(self.lbl_proj)
        names.addWidget(self.lbl_meta)
        hl.addLayout(names, 1)
        self.badge = StatusBadge("بدون پروژه", "pending")
        hl.addWidget(self.badge)
        self.btn_save = QPushButton(" ذخیره")
        self.btn_save.setObjectName("primary")
        self.btn_save.setToolTip("ذخیره پروژه (Ctrl+S)")
        self.btn_save.setShortcut("Ctrl+S")
        self.btn_save.clicked.connect(self.save_project)
        hl.addWidget(self.btn_save)
        self.btn_theme = QPushButton("")
        self.btn_theme.setFixedWidth(40)
        self.btn_theme.clicked.connect(self.toggle_theme)
        hl.addWidget(self.btn_theme)
        mv.addWidget(header)

        self.stepbar = StepBar(workflow.STEPS)
        self.stepbar.step_clicked.connect(lambda k: self.navigate(STEP_TO_PAGE.get(k, "home")))
        mv.addWidget(self.stepbar)

        self.stack = QStackedWidget()
        mv.addWidget(self.stack, 1)

        # --- صفحات ---
        self.home_page = HomePage(self.settings.recent_projects, self.settings.theme)
        self.project_page = ProjectPage(self.settings)
        self.feeder_page = FeederPage(self.manager, self.settings)
        self.study_page = StudyPage(self.manager, self.settings)
        self.images_page = ImagesPage(self.manager)
        self.analysis_page = AnalysisPage(self.manager, self.settings, self.analysis)
        self.review_page = ReviewPage(self.manager, self.settings, self.analysis)
        self.preview_page = PreviewPage(self.manager, self.settings, self.analysis)
        self.generate_page = GeneratePage(self.manager, self.settings, self.analysis)
        self.settings_page = SettingsPage(self.settings)
        self.pages = {
            "home": self.home_page, "project": self.project_page, "input": self.feeder_page,
            "profile": self.feeder_page, "loadflow": self.feeder_page,
            "study": self.study_page, "images": self.images_page,
            "analysis": self.analysis_page, "review": self.review_page,
            "preview": self.preview_page, "generate": self.generate_page,
            "settings": self.settings_page}
        for w in (self.home_page, self.project_page, self.feeder_page, self.images_page,
                  self.study_page,
                  self.analysis_page, self.review_page, self.preview_page,
                  self.generate_page, self.settings_page):
            self.stack.addWidget(w)

        # --- StatusBar ---
        sb = self.statusBar()
        self.lbl_sb_save = QLabel("")
        self.lbl_sb_val = QLabel("")
        self.lbl_sb_path = QLabel("")
        sb.addPermanentWidget(self.lbl_sb_val)
        sb.addPermanentWidget(self.lbl_sb_save)
        sb.addWidget(self.lbl_sb_path, 1)

        # --- سیگنال‌ها ---
        hp = self.home_page
        hp.new_project_requested.connect(self.new_project)
        hp.open_project_requested.connect(self.open_project_dialog)
        hp.quick_import_requested.connect(self.quick_import)
        hp.open_recent_requested.connect(self.open_project_file)
        hp.settings_requested.connect(lambda: self.navigate("settings"))
        hp.continue_requested.connect(lambda k: self.navigate(STEP_TO_PAGE.get(k, "home")))
        hp.open_file_requested.connect(GeneratePage._open)
        for pg in (self.project_page, self.feeder_page, self.images_page, self.study_page):
            pg.changed.connect(self._data_changed)
        self.study_page.request_generate_scenarios.connect(self._generate_scenarios)
        self.study_page.request_cost_estimate.connect(self._cost_estimate)
        self.review_page.changed.connect(self._data_changed_keep_cache)
        self.preview_page.changed.connect(self._data_changed_keep_cache)
        self.analysis_page.navigate_requested.connect(self.navigate)
        self.generate_page.navigate_requested.connect(
            lambda k: self.navigate(STEP_TO_PAGE.get(k, k)))
        self.generate_page.generated.connect(self._on_generated)
        self.generate_page.busy_changed.connect(self._busy)
        self.settings_page.changed.connect(self._settings_changed)

        self.navigate("home")
        self._update_project_dependent_pages()

    # ------------------------------------------------------------------
    # ناوبری
    # ------------------------------------------------------------------
    def navigate(self, key: str) -> None:
        if key not in self.pages:
            key = "home"
        if key != "home" and key != "settings" and self.manager.project is None:
            key = "home"
        self._collect_forms()
        self.current_key = key
        self.stack.setCurrentWidget(self.pages[key])
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
        try:
            if key == "project":
                self.project_page.load_from(self.manager.project)
            elif key in FEEDER_SECTIONS:
                self.feeder_page.refresh()
                self.feeder_page.show_section(key)
            elif key == "study":
                self.study_page.refresh()
            elif key == "images":
                self.images_page.refresh()
            elif key == "analysis":
                self.analysis_page.refresh()
            elif key == "review":
                self.review_page.refresh()
            elif key == "preview":
                self.preview_page.refresh()
            elif key == "generate":
                self.generate_page.refresh()
            elif key == "home":
                self._refresh_status()
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "نمایش صفحه")
        self._refresh_status()

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    def _data_changed(self) -> None:
        self.manager.dirty = True
        self.analysis.invalidate()
        self._refresh_timer.start()
        self._update_save_label()

    def _data_changed_keep_cache(self) -> None:
        self.manager.dirty = True
        self._refresh_timer.start()
        self._update_save_label()

    def _update_save_label(self) -> None:
        if self.manager.project is None:
            self.lbl_sb_save.setText("")
        else:
            self.lbl_sb_save.setText("● ذخیره نشده" if self.manager.dirty else "✓ ذخیره شده")

    def _refresh_status(self) -> None:
        project = self.manager.project
        self._update_save_label()
        if project is None:
            self.lbl_proj.setText("پروژه‌ای باز نیست")
            self.lbl_meta.setText("")
            self.badge.set_state("pending", "بدون پروژه")
            self.lbl_sb_val.setText("")
            self.lbl_sb_path.setText("")
            for k in workflow.STEP_KEYS:
                self.stepbar.set_state(k, "todo")
            self.home_page.update_project(None)
            return
        try:
            items = validate_project(project, self.settings)
            errors, warns = summary_counts(items)
            findings = self.analysis.findings() if not errors else []
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "refresh status")
            return
        steps = workflow.compute_steps(project, items, findings, self._report_generated)
        for k, info in steps.items():
            self.stepbar.set_state(k, info.state, info.tip)
        state, text = workflow.overall_status(project, items, findings, self._report_generated)
        self.badge.set_state(state, text)
        self.lbl_proj.setText(project.title_text() or project.name or "(بدون عنوان)")
        self.lbl_meta.setText(f"شماره گزارش: {project.report_number or '—'}  ·  تاریخ: {project.date_jalali or '—'}"
                              f"  ·  {len(project.feeders)} فیدر")
        self.lbl_sb_val.setText(f"{errors} خطا · {warns} هشدار")
        self.lbl_sb_path.setText(str(self.manager.project_dir or ""))
        done = sum(1 for i in steps.values() if i.state == "done")
        nk = workflow.next_step(steps)
        labels = dict(workflow.STEPS)
        reports = []
        if project.last_report_path:
            reports.append((project.last_report_path, project.last_report_at))
        self.home_page.update_project({
            "name": project.title_text() or project.name, "applicant": project.applicant_name,
            "type": "افزایش قدرت" if project.request_type == "increase" else "تأمین برق جدید",
            "feeders": len(project.feeders), "state": state, "status_text": text,
            "done": done, "total": len(workflow.STEPS), "next_key": nk,
            "next_label": labels.get(nk, ""), "reports": reports})

    def _on_generated(self, path: str) -> None:
        self._report_generated = True
        self._refresh_status()
        self.statusBar().showMessage(f"گزارش تولید شد: {path}", 8000)

    def _busy(self, busy: bool) -> None:
        QApplication.setOverrideCursor(Qt.BusyCursor) if busy else QApplication.restoreOverrideCursor()
        for b in self.nav_buttons.values():
            b.setEnabled(not busy and (b is not None))
        if not busy:
            self._update_project_dependent_pages(refresh_pages=False)

    # ------------------------------------------------------------------
    # مدیریت پروژه
    # ------------------------------------------------------------------
    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        path = QFileDialog.getSaveFileName(
            self, "ایجاد پروژه جدید — انتخاب پوشه پروژه", "پروژه_مطالعه")[0]
        if not path:
            return
        target = Path(path)
        if target.suffix == ".json":
            target = target.parent / target.stem
        try:
            self.manager.new_project(target)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "ایجاد پروژه جدید")
            return
        project = self.manager.project
        project.date_jalali = self._today()
        project.report_number = self._next_report_number()
        project.name = Path(self.manager.project_dir).name
        self.manager.save()
        self._after_project_loaded()
        self.navigate("project")
        self.statusBar().showMessage(f"پروژه جدید ایجاد شد: {self.manager.project_dir}", 5000)

    def open_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "باز کردن پروژه", "", "پروژه گزارش‌یار (project.json)")
        if path:
            self.open_project_file(path)

    def open_project_file(self, path: str) -> None:
        if not self._confirm_discard():
            return
        try:
            self.manager.open_project(path)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "باز کردن پروژه")
            return
        self._after_project_loaded()
        self.navigate("home")
        self.statusBar().showMessage(f"پروژه باز شد: {self.manager.project_dir}", 5000)

    def _after_project_loaded(self) -> None:
        self._report_generated = bool(self.manager.project and self.manager.project.last_report_path
                                      and Path(self.manager.project.last_report_path).exists())
        self.analysis.invalidate()
        self.generate_page.reset_for_project()
        self._update_project_dependent_pages()

    def save_project(self) -> None:
        if self.manager.project is None:
            return
        try:
            self._collect_forms()
            self.manager.save()
            self.statusBar().showMessage("پروژه ذخیره شد.", 3000)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "ذخیره پروژه")
        self._update_save_label()

    def _update_project_dependent_pages(self, refresh_pages: bool = True) -> None:
        has = self.manager.project is not None
        for key, _c, _i, req in NAV:
            self.nav_buttons[key].setEnabled(has or not req)
        name = self.manager.project_dir.name if self.manager.project_dir else ""
        self.lbl_side.setText(f"پروژه جاری:\n{name}" if has else "پروژه‌ای باز نیست")
        if refresh_pages:
            self.feeder_page.current = None
            self.feeder_page.refresh()
            self.images_page.refresh()
            self.generate_page.refresh()
            self.home_page.refresh_recent(self.settings.recent_projects)
        self._refresh_status()

    # ------------------------------------------------------------------
    # Save / Auto Save / بستن
    # ------------------------------------------------------------------
    def _collect_forms(self) -> None:
        if self.manager.project is None:
            return
        try:
            if self.current_key == "project":
                self.project_page.save_to(self.manager.project)
            elif self.current_key == "study":
                self.study_page.save_to_project()
            elif self.current_key in FEEDER_SECTIONS:
                self.feeder_page._save_current()  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "collect forms")

    # ------------------------------------------------------------------
    # عملیات صفحه مطالعه مصارف سنگین
    # ------------------------------------------------------------------
    def _generate_scenarios(self) -> None:
        """تولید/بازتولید سناریوها از Rule Engine (بدون هیچ توصیه‌ای)."""
        if self.manager.project is None:
            return
        from app.core import scenarios as scenario_mod
        self.study_page.save_to_project()
        scenario_mod.ensure_scenarios(self.manager.project, self.settings,
                                      self.analysis.engine, regenerate=True)
        self.study_page.refresh()
        self._data_changed()
        self.statusBar().showMessage(
            f"{len(self.manager.project.scenarios)} سناریو از Rule Engine تولید شد؛ "
            "انتخاب نهایی با مهندس مطالعات است.", 6000)

    def _cost_estimate(self) -> None:
        """محاسبه برآورد پارامتریک هزینه سناریوها (در نبود پارامتر ⇒ MISSING_DATA)."""
        project = self.manager.project
        if project is None:
            return
        self.study_page.save_to_project()
        from app.core.study import cost_estimate
        missing_all = []
        for s in project.scenarios:
            est = cost_estimate(s, project, self.settings)
            if est["estimated_total"] is None:
                missing_all.append(s.display_title)
        self.study_page.refresh()
        if missing_all:
            QMessageBox.information(
                self, "برآورد هزینه",
                "پارامترهای هزینه در «تنظیمات → مطالعه و هزینه» تعریف نشده‌اند؛ "
                "بنابراین برای این سناریوها برآوردی ساخته نشد (MISSING_DATA):\n"
                + "\n".join(missing_all))
        else:
            self.statusBar().showMessage("برآورد پارامتریک هزینه سناریوها به‌روزرسانی شد.", 5000)

    def _autosave_tick(self) -> None:
        if self.manager.dirty and self.manager.project:
            self._collect_forms()
            try:
                self.manager.save()
                self.statusBar().showMessage("ذخیره خودکار انجام شد.", 3000)
                self._update_save_label()
            except Exception as exc:  # noqa: BLE001
                log_exception(exc, "autosave")

    def _confirm_discard(self) -> bool:
        if not self.manager.dirty:
            return True
        ret = QMessageBox.question(
            self, "تغییرات ذخیره نشده است", "تغییرات ذخیره نشده است. ذخیره شود؟",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if ret == QMessageBox.Yes:
            self._collect_forms()
            try:
                self.manager.save()
            except Exception as exc:  # noqa: BLE001
                handle_error(self, exc, "ذخیره پروژه")
                return False
            return True
        return ret == QMessageBox.No

    # ------------------------------------------------------------------
    # تولید سریع از Excel
    # ------------------------------------------------------------------
    def quick_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل Excel استاندارد", "", "Excel (*.xlsx *.xlsm)")
        if not path:
            return
        try:
            project, errors, warnings = excel_importer.build_project_from_excel(path, self.settings)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "خواندن فایل Excel")
            return
        if errors:
            QMessageBox.critical(
                self, "خطای فایل Excel",
                "فایل قابل قبول نیست:\n\n" + "\n".join(errors) +
                "\n\nراهنمایی: از داشبورد گزینه «قالب Excel ورودی» را بگیرید و ساختار شیت‌ها را با آن تطبیق دهید.")
            return
        if not self._confirm_discard():
            return
        base = Path(self.settings.output_dir) if self.settings.output_dir else Path.cwd() / "Projects"
        base.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[\\/:*?"<>|]', "-", project.name or project.title_text() or "پروژه").strip()
        name = safe_name[:60] or "پروژه"
        target = base / name
        k = 2
        while target.exists():
            target = base / f"{name} ({k})"
            k += 1
        try:
            self.manager.new_project(target, project)
            self.manager.save()
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "ایجاد پروژه از Excel")
            return
        self._after_project_loaded()
        msg = f"پروژه از Excel وارد شد: {len(project.feeders)} فیدر."
        if warnings:
            msg += "\n\nهشدارها:\n" + "\n".join(warnings)
        QMessageBox.information(self, "تولید سریع", msg + "\n\nاکنون اعتبارسنجی و بازبینی را انجام دهید.")
        self.navigate("analysis")

    # ------------------------------------------------------------------
    @staticmethod
    def _today() -> str:
        from app.utils.jalali import today_jalali
        return today_jalali()

    def _next_report_number(self) -> str:
        return f"{self.settings.report_prefix or ''}001"

    def _settings_changed(self) -> None:
        self.settings.save()
        self.feeder_page.settings = self.settings
        self.analysis.invalidate()
        if self.settings.theme != getattr(self, "_applied_theme", None):
            self._applied_theme = self.settings.theme
            self.apply_theme(self.settings.theme)
        self._refresh_status()

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
