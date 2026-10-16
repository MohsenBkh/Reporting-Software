# -*- coding: utf-8 -*-
"""پنجرهٔ اصلی Engineering Desktop (v2.0.0) — Ribbon + Project Explorer + Workspace تب‌دار + Inspector.

* ``MainWindow`` فقط برای منطق مشترک (پروژه، ذخیره، Auto Save، Validation، Workflow) ارث‌بری
  می‌شود؛ رابط کاربری کاملاً جدید است: نوار ریبونی (جایگزین Menu/Toolbar و Sidebar)،
  درخت Project Explorer (جایگزین نوار مراحل ۱ تا ۷)، Workspace تب‌دار، Property Inspector.
* ستون‌های Explorer/Workspace/Inspector با ``QSplitter`` قابل تغییر عرض‌اند.
* «پیش‌نمایش» و «تولید گزارش» در یک Report Center یکپارچه‌اند.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QLabel, QMessageBox, QProgressBar,
                               QSplitter, QTabWidget, QVBoxLayout, QWidget)

from app import APP_NAME, APP_NAME_FA, APP_VERSION
from app.core import workflow
from app.core.findings import unresolved
from app.core.guided_flow import compute_flow, guide_model, is_route_allowed
from app.core.project_tree import build_project_tree
from app.core.studies import STUDY_LABELS_FA, StudyKind, report_type_for_selection
from app.core.validation import summary_counts, validate_project
from app.core.workspace import Workspace, workspace_from_project
from app.report import pipeline
from app.ui import theme as theme_mod
from app.ui.analysis_page import AnalysisPage
from app.ui.applicant_page import ApplicantPage
from app.ui.feeder_page import FeederPage
from app.ui.generate_page import GeneratePage
from app.ui.home_page import HomePage
from app.ui.images_page import ImagesPage
from app.ui.main_window import MainWindow, STEP_TO_PAGE
from app.ui.preview_page import PreviewPage
from app.ui.project_page import ProjectPage
from app.ui.review_page import ReviewPage
from app.ui.settings_page import SettingsPage
from app.ui.shell.ai_page import AIPage
from app.ui.shell.dashboard_model import dashboard_cards, validation_checklist
from app.ui.shell.dashboard_page import EngineeringDashboard
from app.ui.shell.design import shell_qss
from app.ui.shell.explorer import ProjectExplorer
from app.ui.shell.guide_bar import GuideBar
from app.ui.shell.inspector import PropertyInspector
from app.ui.shell.inspector_model import apply_include_flag, inspector_model
from app.ui.shell.new_project_dialog import NewProjectDialog
from app.ui.shell.report_center import PLAN_TO_REPORT_TYPE, ReportCenter
from app.ui.shell.report_center_page import ReportCenterPage
from app.ui.shell.ribbon import RibbonBar, ribbon_qss
from app.ui.shell.network_editor import NetworkEditor
from app.ui.shell.study_pages import HeavyStudyPage, ProtectionStudyPage
from app.ui.study_page import StudyPage
from app.ui.widgets import StatusBadge, scrollable
from app.utils.errors import handle_error, log_exception

# کلید ناوبری ← (صفحهٔ Workspace، زیرصفحه)
ROUTES: dict[str, tuple[str, Optional[str]]] = {
    "dashboard": ("dashboard", None), "project": ("project", None),
    "applicant": ("heavy", "applicant"), "study": ("heavy", "study"),
    "input": ("heavy", "feeders:input"), "profile": ("heavy", "feeders:profile"),
    "loadflow": ("heavy", "feeders:loadflow"),
    # v2.3.0 — «فیدرهای محدودهٔ مطالعه» صفحهٔ مشترک و جداگانه است (protnet)
    "protnet": ("protnet", None),
    "recloser": ("recloser", "device"), "recloser.network": ("protnet", None),
    "recloser.device": ("recloser", "device"), "recloser.settings": ("recloser", "settings"),
    "sectionalizer": ("sectionalizer", "device"),
    "sectionalizer.network": ("protnet", None),
    "sectionalizer.device": ("sectionalizer", "device"),
    "sectionalizer.settings": ("sectionalizer", "settings"),
    "protection": ("protnet", None),
    "images": ("images", None), "analysis": ("analysis", "metrics"),
    "validation": ("analysis", "validation"),
    "review": ("review", None), "settings": ("settings", None),
    "reportcenter": ("reportcenter", "select"), "preview": ("reportcenter", "preview"),
    "generate": ("reportcenter", "generate"), "ai": ("reportcenter", "ai"),
}
# کلید ناوبری ← گام Guided Flow که آن را قفل می‌کند (بدون ورودی = همیشه آزاد)
ROUTE_STEP = {"project": "project", "applicant": "input", "study": "input", "input": "input",
              "profile": "input", "loadflow": "input", "recloser": "input", "sectionalizer": "input",
              "protnet": "input",
              "recloser.network": "input", "recloser.device": "input", "recloser.settings": "input",
              "sectionalizer.network": "input", "sectionalizer.device": "input",
              "sectionalizer.settings": "input", "protection": "input", "images": "input",
              "validation": "validation", "analysis": "analysis", "review": "review",
              "preview": "preview", "generate": "generate", "ai": "review"}
# گرهٔ Explorer ← کلید ناوبری
NODE_ROUTE = {
    "dashboard": "dashboard", "step.project": "project", "input.heavy": "applicant",
    "heavy.applicant": "applicant", "heavy.feeders": "input", "heavy.study": "study",
    "input.recloser": "recloser.network", "recloser.network": "recloser.network",
    "recloser.device": "recloser.device", "recloser.settings": "recloser.settings",
    "input.sectionalizer": "sectionalizer.network",
    "sectionalizer.network": "sectionalizer.network",
    "sectionalizer.device": "sectionalizer.device",
    "sectionalizer.settings": "sectionalizer.settings",
    "images": "images", "step.validation": "validation", "step.analysis": "analysis",
    "step.review": "review", "step.preview": "preview", "step.generate": "reportcenter",
    "report.select": "reportcenter", "report.generate": "generate", "report.ai": "ai", "settings": "settings",
}
ROUTE_NODE = {v: k for k, v in NODE_ROUTE.items()}
TITLES = {"dashboard": "داشبورد", "home": "خانه", "project": "اطلاعات پروژه",
          "heavy": "متقاضی سنگین", "protnet": "فیدرهای محدوده مطالعه",
          "recloser": "ریکلوزر", "sectionalizer": "سکشنالایزر",
          "images": "تصاویر گزارش", "analysis": "اعتبارسنجی و تحلیل", "review": "بازبینی مهندس",
          "reportcenter": "Report Center", "settings": "تنظیمات"}


class EngineeringWindow(MainWindow):
    # ------------------------------------------------------------------
    # ساخت UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._shell_ready = False
        self._results: dict = {}
        self._gen_queue: list[str] = []
        self._syncing = False
        self._actions: dict[str, QAction] = {}

        # --- صفحه‌ها ---
        self.home_page = HomePage(self.settings.recent_projects, self.settings.theme)
        self.dashboard_page = EngineeringDashboard()
        self.project_page = ProjectPage(self.settings)
        self.applicant_page = ApplicantPage(self.settings)
        self.feeder_page = FeederPage(self.manager, self.settings)
        self.study_page = StudyPage(self.manager, self.settings)
        self.images_page = ImagesPage(self.manager, get_selection=self._selection)
        self.analysis_page = AnalysisPage(self.manager, self.settings, self.analysis)
        self.review_page = ReviewPage(self.manager, self.settings, self.analysis)
        self.preview_page = PreviewPage(self.manager, self.settings, self.analysis)
        self.generate_page = GeneratePage(self.manager, self.settings, self.analysis)
        self.settings_page = SettingsPage(self.settings)
        self.heavy_page = HeavyStudyPage(self.applicant_page, self.feeder_page, self.study_page)
        # v2.3.0 — صفحهٔ مشترک «فیدرهای محدودهٔ مطالعه» (یک‌بار ورود برای هر دو مطالعه)
        self.prot_network_page = NetworkEditor(self.manager, self._ws)
        self.rec_page = ProtectionStudyPage(self.manager, self.settings, StudyKind.RECLOSER,
                                            self._ws, lambda: self.settings.theme)
        self.secz_page = ProtectionStudyPage(self.manager, self.settings, StudyKind.SECTIONALIZER,
                                             self._ws, lambda: self.settings.theme)
        self.selection_page = ReportCenterPage(self.manager, self._ws)
        self.ai_page = AIPage(self.manager, self.settings, self._ws, self._current_report,
                              lambda: self._results, on_applied=self._on_ai_applied)
        self.report_center = ReportCenter(self.selection_page, self.preview_page,
                                          self.generate_page, self.manager, self._ws,
                                          ai_page=self.ai_page)
        self.pages: dict[str, QWidget] = {
            "home": self.home_page, "dashboard": self.dashboard_page, "project": self.project_page,
            "heavy": self.heavy_page, "protnet": self.prot_network_page,
            "recloser": self.rec_page, "sectionalizer": self.secz_page,
            "images": self.images_page, "analysis": self.analysis_page, "review": self.review_page,
            "reportcenter": self.report_center, "settings": self.settings_page}

        # --- ظاهر: Ribbon + Splitter(Explorer | Workspace | Inspector) ---
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.ribbon = RibbonBar()
        root.addWidget(self.ribbon)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.setOpaqueResize(True)
        root.addWidget(self.splitter, 1)
        self.explorer = ProjectExplorer()
        self.explorer.node_selected.connect(self._on_node_selected)
        self.explorer.node_clicked.connect(self._on_node_open)
        self.explorer.node_activated.connect(self._on_node_open)
        self.inspector = PropertyInspector()
        self.inspector.include_toggled.connect(self._on_include_toggled)
        self.explorer_panel = self._side_panel("Project Explorer", self.explorer)
        self.inspector_panel = self._side_panel("Property Inspector", scrollable(self.inspector))
        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkspaceTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setMinimumWidth(320)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.guide_bar = GuideBar()
        self.guide_bar.goto_requested.connect(self.goto)
        self.guide_bar.override_requested.connect(self._override_step)
        self.guide_bar.ack_protection_requested.connect(self._ack_protection)
        workspace_box = QWidget()
        wv = QVBoxLayout(workspace_box)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)
        wv.addWidget(self.guide_bar)
        wv.addWidget(self.tabs, 1)
        self._flow: list = []
        for w, stretch in ((self.explorer_panel, 0), (workspace_box, 1), (self.inspector_panel, 0)):
            self.splitter.addWidget(w)
        for i, stretch in enumerate((0, 1, 0)):
            self.splitter.setStretchFactor(i, stretch)
        self.explorer_panel.setMinimumWidth(170)
        self.inspector_panel.setMinimumWidth(200)
        self.splitter.setSizes([270, 900, 290])
        self.setCentralWidget(central)

        self.badge = StatusBadge("بدون پروژه", "pending")
        self.ribbon.title_layout.addWidget(self.badge)
        self._build_actions()
        self._build_ribbon()

        sb = self.statusBar()
        self.lbl_sb_save = QLabel("")
        self.lbl_sb_val = QLabel("")
        self.lbl_sb_path = QLabel("")
        self.lbl_review = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(150)
        self.progress.hide()
        for w in (self.lbl_review, self.lbl_sb_val, self.lbl_sb_save, self.progress):
            sb.addPermanentWidget(w)
        sb.addWidget(self.lbl_sb_path, 1)
        self.setWindowTitle(self.windowTitle() + " [*]")

        # --- سیگنال‌ها ---
        hp = self.home_page
        hp.new_project_requested.connect(self.new_project)
        hp.open_project_requested.connect(self.open_project_dialog)
        hp.quick_import_requested.connect(self.quick_import)
        hp.open_recent_requested.connect(self.open_project_file)
        hp.settings_requested.connect(lambda: self.navigate("settings"))
        hp.continue_requested.connect(lambda k: self.navigate(STEP_TO_PAGE.get(k, "dashboard")))
        hp.open_file_requested.connect(GeneratePage._open)
        for pg in (self.project_page, self.applicant_page, self.feeder_page, self.images_page,
                   self.study_page, self.prot_network_page, self.rec_page, self.secz_page):
            pg.changed.connect(self._data_changed)
        self.selection_page.changed.connect(self._on_selection_changed)
        self.ai_page.changed.connect(self._data_changed_keep_cache)
        self.study_page.request_generate_scenarios.connect(self._generate_scenarios)
        self.study_page.request_cost_estimate.connect(self._cost_estimate)
        self.review_page.changed.connect(self._data_changed_keep_cache)
        self.preview_page.changed.connect(self._data_changed_keep_cache)
        self.analysis_page.navigate_requested.connect(self.navigate)
        self.analysis_page.goto_requested.connect(self.goto)
        self.rec_page.goto_requested.connect(self.goto)
        self.secz_page.goto_requested.connect(self.goto)
        self.generate_page.navigate_requested.connect(lambda k: self.navigate(STEP_TO_PAGE.get(k, k)))
        self.generate_page.generated.connect(self._on_generated)
        self.generate_page.generated.connect(self._on_generated_queue)
        self.generate_page.busy_changed.connect(self._busy)
        self.settings_page.changed.connect(self._settings_changed)
        self.dashboard_page.open_requested.connect(
            lambda k: self.navigate({"heavy": "applicant"}.get(k, k)))
        self.report_center.plan_changed.connect(self._apply_plan)
        self.report_center.generate_all_requested.connect(self._generate_all)
        self.rec_page.evaluated.connect(self._on_evaluated)
        self.secz_page.evaluated.connect(self._on_evaluated)
        self.heavy_page.currentChanged.connect(lambda _i: self._collect_forms())

        self._shell_ready = True
        self.navigate("home")
        self._update_project_dependent_pages()

    @staticmethod
    def _side_panel(title: str, body: QWidget) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("PanelTitle")
        v.addWidget(head)
        v.addWidget(body, 1)
        return panel

    # ------------------------------------------------------------------
    # Actions و Ribbon
    # ------------------------------------------------------------------
    def _act(self, key: str, text: str, slot, shortcut: str = "", checkable: bool = False,
             tip: str = "") -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.ApplicationShortcut)
        a.setCheckable(checkable)
        a.setToolTip(tip or text)
        a.triggered.connect(lambda _=False, s=slot: s())
        self.addAction(a)                    # میان‌بر حتی بدون نمایش ریبون فعال بماند
        self._actions[key] = a
        return a

    def _nav(self, key: str):
        return lambda: self.navigate(key)

    def _build_actions(self) -> None:
        A = self._act
        A("new", "پروژه جدید", self.new_project, "Ctrl+N")
        A("open", "باز کردن", self.open_project_dialog, "Ctrl+O")
        A("save", "ذخیره", self.save_project, "Ctrl+S")
        A("import", "ورود از Excel", self.quick_import, "Ctrl+I")
        A("settings", "تنظیمات نرم‌افزار", self._nav("settings"))
        A("exit", "خروج", self.close, "Ctrl+Q")
        A("dashboard", "داشبورد", self._nav("dashboard"), "Ctrl+1")
        A("project", "اطلاعات پروژه", self._nav("project"), "Ctrl+2")
        A("applicant", "اطلاعات متقاضی", self._nav("applicant"))
        A("input", "فیدرها", self._nav("input"))
        A("profile", "پروفیل بار", self._nav("profile"))
        A("loadflow", "پخش بار", self._nav("loadflow"))
        A("images", "تصاویر گزارش", self._nav("images"))
        for kind in StudyKind:
            A(f"sel_{kind.value}", STUDY_LABELS_FA[kind],
              lambda k=kind: self._toggle_study(k), checkable=True,
              tip=f"درج مطالعهٔ {STUDY_LABELS_FA[kind]} در پروژه")
        A("study", "مطالعه مصارف سنگین", self._nav("study"))
        A("prot_network", "فیدرهای محدوده", self._nav("protnet"),
          tip="فیدرهای محدودهٔ مطالعه و اطلاعات شبکه — یک‌بار ورود برای ریکلوزر و سکشنالایزر")
        A("recloser", "ریکلوزر", self._nav("recloser"))
        A("sectionalizer", "سکشنالایزر", self._nav("sectionalizer"))
        A("validate", "اعتبارسنجی", self._nav("validation"), "F5")
        A("analysis", "تحلیل مهندسی", self._nav("analysis"))
        A("run", "اجرای قواعد حفاظتی", self._run_protection, "F6")
        A("idmt_tool", "ابزار هماهنگی IDMT", self._open_idmt_tool,
          tip="باز کردن نرم‌افزار «هماهنگی حفاظت فیدر (IDMT Coordination)» در مرورگر — "
              "داده‌ها را یک‌بار آنجا وارد کنید")
        A("idmt_import", "ورود از IDMT", self._import_idmt, "Ctrl+Shift+I",
          tip="ورود تنظیمات نهایی ریکلوزر/سکشنالایزر و نمودارهای TCC، توالی و برگه "
              "تنظیمات از بسته «خروجی گزارش‌ساز» ابزار IDMT")

        A("review", "بازبینی مهندس", self._nav("review"))
        A("rc_select", "انتخاب مطالعات", self._nav("reportcenter"), "Ctrl+R")
        A("rc_preview", "پیش‌نمایش", self._nav("preview"))
        A("rc_generate", "تولید گزارش", self._nav("generate"))
        A("rc_ai", "دستیار هوش مصنوعی", self._nav("ai"), "Ctrl+Shift+A")
        A("theme", "تم روشن/تاریک", self.toggle_theme, "Ctrl+Shift+D")
        A("toggle_explorer", "Project Explorer", self._toggle_explorer, checkable=True)
        A("toggle_inspector", "Property Inspector", self._toggle_inspector, checkable=True)
        A("collapse", "جمع‌کردن ریبون", self._toggle_ribbon, "Ctrl+F1")
        A("reset_layout", "بازنشانی چیدمان", self._reset_layout)
        A("close_tab", "بستن تب", lambda: self._close_tab(self.tabs.currentIndex()), "Ctrl+W")
        A("about", "دربارهٔ برنامه", self._about)
        self._actions["toggle_explorer"].setChecked(True)
        self._actions["toggle_inspector"].setChecked(True)

    def _build_ribbon(self) -> None:
        R, a = self.ribbon, self._actions
        p = R.add_tab("file", "File", file_tab=True)
        g = p.add_group("پروژه")
        g.add_action(a["new"], "plus"); g.add_action(a["open"], "folder"); g.add_action(a["save"], "save")
        p.add_group("ورود").add_action(a["import"], "excel")
        g = p.add_group("برنامه")
        g.add_action(a["settings"], "settings"); g.add_action(a["exit"], "x")

        p = R.add_tab("project", "Project")
        g = p.add_group("اطلاعات")
        g.add_action(a["dashboard"], "dashboard"); g.add_action(a["project"], "project")
        g = p.add_group("ورود داده متقاضی سنگین")
        for k, ic in (("applicant", "project"), ("input", "input"), ("profile", "profile"),
                      ("loadflow", "loadflow")):
            g.add_action(a[k], ic)
        p.add_group("شکل‌ها").add_action(a["images"], "images")

        p = R.add_tab("studies", "Studies")
        g = p.add_group("مطالعات پروژه")
        for kind in StudyKind:
            g.add_action(a[f"sel_{kind.value}"], "study" if kind is StudyKind.HEAVY else "protection")
        g = p.add_group("ورود داده مطالعات")
        g.add_action(a["study"], "study"); g.add_action(a["prot_network"], "input")
        g.add_action(a["recloser"], "protection"); g.add_action(a["sectionalizer"], "protection")
        g = p.add_group("هماهنگی حفاظتی (IDMT)")
        g.add_action(a["idmt_tool"], "analysis"); g.add_action(a["idmt_import"], "input")

        p = R.add_tab("analysis", "Analysis")
        g = p.add_group("اعتبارسنجی و تحلیل")
        g.add_action(a["validate"], "check"); g.add_action(a["analysis"], "analysis")
        g.add_action(a["run"], "play"); g.add_action(a["review"], "review")

        p = R.add_tab("report", "Report")
        g = p.add_group("Report Center")
        g.add_action(a["rc_select"], "generate"); g.add_action(a["rc_preview"], "preview")
        g.add_action(a["rc_generate"], "generate")
        g = p.add_group("هوش مصنوعی")
        g.add_action(a["rc_ai"], "edit")

        p = R.add_tab("view", "View")
        g = p.add_group("نمایش")
        g.add_action(a["theme"], "moon"); g.add_action(a["collapse"], "panel")
        g.add_action(a["reset_layout"], "refresh")
        g.add_column([(a["toggle_explorer"], "panel"), (a["toggle_inspector"], "panel")])
        p.add_group("تب‌ها").add_action(a["close_tab"], "x")

        p = R.add_tab("help", "Help")
        p.add_group("راهنما").add_action(a["about"], "info")
        R.set_titles(f"{APP_NAME_FA}", "")
        R.set_current("file")
        self._project_actions = [a[k] for k in (
            "save", "import", "project", "applicant", "input", "profile", "loadflow", "images",
            "study", "prot_network", "recloser", "sectionalizer", "validate", "analysis", "run", "review",
            "rc_select", "rc_preview", "rc_generate", "rc_ai", "dashboard",
            "sel_heavy", "sel_recloser", "sel_sectionalizer", "idmt_import")]
        a["import"].setEnabled(True)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def apply_theme(self, name: str) -> None:
        self.settings.theme = name if name in theme_mod.THEMES else "light"
        t = theme_mod.tokens(self.settings.theme)
        QApplication.instance().setStyleSheet(
            theme_mod.build_qss(self.settings.theme) + shell_qss(self.settings.theme, t)
            + ribbon_qss(t))
        self.ribbon.apply_theme(self.settings.theme)
        self.home_page.apply_icons(self.settings.theme)
        self.review_page.apply_icons()
        if self.manager.project:
            self._refresh_status()
            self.analysis_page.refresh()
            self.review_page.refresh()

    # ------------------------------------------------------------------
    # Workspace (Common Network) و تب‌ها
    # ------------------------------------------------------------------
    def _ws(self) -> Optional[Workspace]:
        p = self.manager.project
        if p is None:
            return None
        ws = getattr(self.manager, "workspace", None) or getattr(p, "_workspace", None)
        if ws is None:
            ws = workspace_from_project(p)
        p._workspace = ws  # noqa: SLF001
        try:
            self.manager.workspace = ws
        except Exception:  # noqa: BLE001
            pass
        return ws

    def _open_tab(self, page_key: str) -> QWidget:
        page = self.pages[page_key]
        idx = self.tabs.indexOf(page)
        if idx < 0:
            idx = self.tabs.addTab(page, TITLES.get(page_key, page_key))
        self.tabs.setCurrentIndex(idx)
        return page

    def _close_tab(self, index: int) -> None:
        if index >= 0 and self.tabs.count() > 1:
            self.tabs.removeTab(index)           # صفحه حذف نمی‌شود؛ با باز کردن دوباره برمی‌گردد

    def _current_page_key(self) -> str:
        w = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        return next((k for k, v in self.pages.items() if v is w), "")

    # ------------------------------------------------------------------
    # ناوبری
    # ------------------------------------------------------------------
    def navigate(self, key: str) -> None:
        if not getattr(self, "_shell_ready", False):
            return
        if key == "home":
            key = "dashboard" if self.manager.project is not None else "home"
        route = ROUTES.get(key, ("home", None) if key == "home" else ("dashboard", None))
        page_key, sub = route
        if self.manager.project is None and page_key not in ("home", "settings"):
            page_key, sub, key = "home", None, "home"
        self._collect_forms()
        step = ROUTE_STEP.get(key, "")
        if step and self._flow and not is_route_allowed(self._flow, step):
            gm = guide_model(self._flow, self._ws().selection if self._ws() else None)
            self.statusBar().showMessage(
                f"این گام هنوز باز نشده است. {gm.title}: ابتدا موارد ناتمام را کامل کنید.", 6000)
            key = gm.goto or "project"
            page_key, sub = ROUTES.get(key, ("project", None))
        self.current_key = key
        self._open_tab(page_key)
        try:
            self._refresh_page(page_key, sub)
            self._mark_visit(key)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "نمایش صفحه")
        self._sync_explorer(key)
        self._refresh_status()

    def _mark_visit(self, key: str) -> None:
        """گام‌های «مشاهده‌ای» (تحلیل، پیش‌نمایش) با باز شدن صفحه ثبت می‌شوند."""
        ws = self._ws()
        if ws is None:
            return
        if key == "analysis":
            if ws.selection.protection_kinds():
                self._evaluate_protection()
            ws.mark_done("analysis")
        elif key == "preview":
            ws.mark_done("preview")

    # ------------------------------------------------------------------
    # ارجاع دقیق به منبع خطا و کنترل گام‌ها
    # ------------------------------------------------------------------
    def goto(self, route: str, field: str = "") -> None:
        """رفتن به صفحهٔ ورود داده و Focus روی فیلدی که یافته/خطا به آن ارجاع دارد."""
        if not route:
            return
        self.navigate(route)
        if not field or self.current_key != route:       # گام قفل بود → به گام جاری هدایت شد
            return
        page_key, sub = ROUTES.get(route, ("", None))
        if page_key == "project":
            self.project_page.focus_field(field)
        elif page_key == "heavy":
            self.applicant_page.focus_field(field)
        elif page_key == "protnet":
            self.prot_network_page.focus_field(field)
        elif page_key in ("recloser", "sectionalizer"):
            self.pages[page_key].focus_field(sub or "device", field)

    def _current_report(self):
        """گزارش فعلی (متن‌های تولیدشده) برای دستیار هوش مصنوعی؛ None اگر در دسترس نباشد."""
        try:
            return self.analysis.get()
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "گزارش برای هوش مصنوعی")
            return None

    def _on_ai_applied(self) -> None:
        """متن پذیرفته‌شده در manual_texts ثبت شد → نمایش/خروجی باید از نو ساخته شود."""
        self.analysis.invalidate()
        self.preview_page.refresh()
        self._refresh_timer.start()

    def _selection(self):
        ws = self._ws()
        return ws.selection if ws is not None else None

    def _override_step(self, step_key: str) -> None:
        ws = self._ws()
        if ws is None:
            return
        ws.override(step_key)
        self.manager.dirty = True
        self._refresh_status()
        self.statusBar().showMessage("گام بعد با وجود نقص باز شد؛ نقص‌ها در گزارش هشدار داده می‌شود.", 5000)

    def _ack_protection(self) -> None:
        ws = self._ws()
        if ws is not None:
            ws.mark_done("review")
            self.manager.dirty = True
            self._refresh_status()

    def _data_changed(self) -> None:
        """تغییر ورودی → نتایج وابسته (تحلیل/بازبینی/پیش‌نمایش) باید دوباره ثبت شوند."""
        ws = self._ws()
        if ws is not None and getattr(self, "_shell_ready", False):
            ws.clear_done("analysis", "review", "preview")
        super()._data_changed()

    def _refresh_page(self, page_key: str, sub: Optional[str]) -> None:
        project = self.manager.project
        if page_key == "project":
            self.project_page.load_from(project)
        elif page_key == "heavy":
            self.applicant_page.load_from(project)
            self.feeder_page.refresh()
            self.study_page.refresh()
            tab, _, section = (sub or "applicant").partition(":")
            self.heavy_page.show_tab(tab)
            if section:
                self.feeder_page.show_section(section)
        elif page_key == "protnet":
            self.prot_network_page.refresh()
        elif page_key in ("recloser", "sectionalizer"):
            page = self.pages[page_key]
            page.refresh()
            page.show_tab(sub or "device")
        elif page_key == "images":
            self.images_page.refresh()
        elif page_key == "analysis":
            self.analysis_page.refresh()
            self.analysis_page.show_tab(sub or "metrics")
        elif page_key == "review":
            self.review_page.refresh()
        elif page_key == "reportcenter":
            self.selection_page.refresh()
            self.report_center.refresh_plans()
            self._apply_plan(self.report_center.current_plan_key(), refresh=False)
            self.report_center.show_tab(sub or "select")
            if sub == "ai":
                self._evaluate_protection()
                self.ai_page.refresh()
            if sub == "preview":
                self.preview_page.refresh()
            elif sub == "generate":
                self.generate_page.refresh()
        elif page_key == "dashboard":
            self._refresh_dashboard()

    def _sync_explorer(self, key: str) -> None:
        node = ROUTE_NODE.get(key)
        if node and self.explorer.current_key() != node:
            self._syncing = True
            self.explorer.select_key(node)
            self._syncing = False

    def _collect_forms(self) -> None:
        project = self.manager.project
        if project is None or not getattr(self, "_shell_ready", False):
            return
        try:
            page = self._current_page_key()
            if page == "project":
                self.project_page.save_to(project)
            elif page == "heavy":
                self.applicant_page.save_to(project)
                self.study_page.save_to_project()
                self.feeder_page._save_current()  # noqa: SLF001
            elif page == "protnet":
                self.prot_network_page.save_to_project()
            elif page in ("recloser", "sectionalizer"):
                self.pages[page].save_to_project()
        except Exception as exc:  # noqa: BLE001
            log_exception(exc, "collect forms")

    # ------------------------------------------------------------------
    # Explorer / Inspector
    # ------------------------------------------------------------------
    def _on_node_selected(self, key: str) -> None:
        ws = self._ws()
        self.inspector.show_model(inspector_model(self.manager.project, ws, key))

    def _on_node_open(self, key: str) -> None:
        if self._syncing:
            return
        if key == "step.input":
            ws = self._ws()
            sel = ws.selection if ws else None
            key = ("input.heavy" if sel and sel.heavy else "input.recloser" if sel and sel.recloser
                   else "input.sectionalizer" if sel and sel.sectionalizer else "images")
        if key.startswith("feeder:"):
            _, kind, _name = key.split(":", 2)
            key = f"{kind}.network"
        route = NODE_ROUTE.get(key)
        if route:
            self.navigate(route)

    def _on_include_toggled(self, key: str, value: bool) -> None:
        if self.manager.project is not None and apply_include_flag(self.manager.project, key, value):
            self._data_changed_keep_cache()

    def _on_selection_changed(self) -> None:
        self._data_changed_keep_cache()
        ws = self._ws()
        if ws is not None and self.manager.project is not None:
            self.manager.project.report_type = report_type_for_selection(ws.selection)
        self.report_center.refresh_plans()

    def _toggle_study(self, kind: StudyKind) -> None:
        ws = self._ws()
        if ws is None:
            return
        setattr(ws.selection, kind.value, self._actions[f"sel_{kind.value}"].isChecked())
        if ws.selection.is_empty():                      # حداقل یک مطالعه
            setattr(ws.selection, kind.value, True)
            self._actions[f"sel_{kind.value}"].setChecked(True)
        self.manager.project.report_type = report_type_for_selection(ws.selection)
        self._data_changed()

    # ------------------------------------------------------------------
    # حفاظت: ارزیابی و Dashboard
    # ------------------------------------------------------------------
    def _on_evaluated(self, results: dict) -> None:
        self._results.update(results)
        self._refresh_dashboard()

    def _evaluate_protection(self) -> None:
        """ارزیابی بی‌صدای قواعد حفاظتی مطالعات انتخاب‌شده (برای گام تحلیل و داشبورد)."""
        project, ws = self.manager.project, self._ws()
        if project is None or ws is None:
            return
        from app.rules.domains import build_protection_engine, evaluate_study
        engine = build_protection_engine()
        for kind in ws.selection.protection_kinds():
            self._results[kind] = evaluate_study(project, ws, kind, engine)

    def _run_protection(self) -> None:
        project, ws = self.manager.project, self._ws()
        if project is None or ws is None:
            return
        from app.rules.domains import build_protection_engine, evaluate_study
        kinds = ws.selection.protection_kinds()
        if not kinds:
            self.statusBar().showMessage("مطالعهٔ حفاظتی انتخاب نشده است.", 4000)
            return
        self._collect_forms()
        self._busy(True)
        try:
            self._evaluate_protection()
        finally:
            self._busy(False)
        total = sum(len(v) for k, v in self._results.items() if k in kinds)
        review = sum(1 for k in kinds for r in self._results.get(k, []) if r.engineer_review_required)
        self.statusBar().showMessage(f"{total} یافته · {review} مورد نیازمند بازبینی مهندس", 6000)
        self.navigate(f"{kinds[0].value}.settings")

    # ------------------------------------------------------------------
    # پیوند با نرم‌افزار «هماهنگی حفاظت فیدر (IDMT Coordination)»
    # ------------------------------------------------------------------
    def _open_idmt_tool(self) -> None:
        """باز کردن ابزار IDMT همراه برنامه در مرورگر پیش‌فرض."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from app.utils.resources import resource_path
        path = resource_path("idmt_coordination.html")
        if not path.exists():
            QMessageBox.warning(self, "ابزار IDMT",
                                "فایل ابزار هماهنگی (idmt_coordination.html) در پوشه resource یافت نشد.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.statusBar().showMessage(
            "ابزار IDMT در مرورگر باز شد؛ پس از مطالعه، با دکمه «خروجی گزارش‌ساز» بسته JSON بگیرید.", 8000)

    def _import_idmt(self) -> None:
        """ورود بسته «خروجی گزارش‌ساز» ابزار IDMT: داده‌ها + نمودارها، بدون ورود دوباره."""
        if self.manager.project is None:
            QMessageBox.information(self, "ورود از IDMT", "ابتدا یک پروژه باز یا ایجاد کنید.")
            return
        from app.core.idmt_bundle import IdmtBundleError, import_idmt_file
        fname, _ = QFileDialog.getOpenFileName(
            self, "انتخاب بسته خروجی گزارش‌ساز (IDMT)", "",
            "بسته IDMT (*.json);;همه فایل‌ها (*)")
        if not fname:
            return
        try:
            res = import_idmt_file(self.manager, fname)
        except IdmtBundleError as exc:
            QMessageBox.warning(self, "ورود از IDMT", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — خطای غیرمنتظره نباید برنامه را ببندد
            QMessageBox.critical(self, "ورود از IDMT", f"ورود بسته ناموفق بود: {exc}")
            return
        self._data_changed()
        self._refresh_dashboard()
        lines = ["داده‌های زیر از IDMT منتقل شد:"]
        lines += [f"• {a}" for a in res.applied]
        if res.images:
            lines.append(f"• {len(res.images)} تصویر (TCC، توالی عملکرد، برگه تنظیمات) به شکل‌های گزارش افزوده شد.")
        if res.warnings:
            lines.append("")
            lines.append("هشدارها:")
            lines += [f"⚠ {w}" for w in res.warnings]
        if res.failures:
            lines.append("")
            lines.append("قواعد ناموفق در خود IDMT:")
            lines += [f"✗ {f}" for f in res.failures[:8]]
            if len(res.failures) > 8:
                lines.append(f"… و {len(res.failures) - 8} مورد دیگر")
        QMessageBox.information(self, "ورود از IDMT", "\n".join(lines))
        self.statusBar().showMessage(f"ورود از IDMT انجام شد ({res.summary}).", 8000)
        self.navigate("recloser")

    def _refresh_dashboard(self) -> None:
        project, ws = self.manager.project, self._ws()
        if project is None or ws is None:
            self.dashboard_page.set_content([], [])
            self.lbl_review.setText("")
            return
        try:
            errors, warns = summary_counts(validate_project(project, self.settings))
        except Exception:  # noqa: BLE001
            errors = warns = 0
        checks = validation_checklist(project, ws, input_errors=errors, input_warnings=warns,
                                      results_by_kind=self._results or None,
                                      report_generated=self._report_generated)
        self.dashboard_page.set_content(dashboard_cards(project, ws, self._results or None), checks)
        pending = sum(1 for rows in self._results.values() for r in rows
                      if r.engineer_review_required)
        self.lbl_review.setText(f"◆ بازبینی مهندس: {pending}" if self._results else "")

    # ------------------------------------------------------------------
    # Report Center: گزارش جاری و تولید همه
    # ------------------------------------------------------------------
    def _apply_plan(self, key: str, refresh: bool = True) -> None:
        project = self.manager.project
        if project is None or not key:
            return
        new_type = PLAN_TO_REPORT_TYPE.get(key, project.report_type)
        if new_type != project.report_type:              # فقط با تغییر واقعی «ذخیره‌نشده» می‌شود
            project.report_type = new_type
            self.manager.dirty = True
            self._update_save_label()
            self.analysis.invalidate()
        plan = next((p for p in self.report_center.plans() if p.key == key), None)
        if plan is not None and not plan.is_heavy:
            stem = Path(pipeline.docx_filename(project)).stem
            self.generate_page.ed_name.setText(f"{stem} - {plan.filename_stem}.docx")
        elif plan is not None:
            self.generate_page.ed_name.setText(pipeline.docx_filename(project))
        if refresh:
            self.preview_page.refresh()
            self.generate_page.refresh()
        self._refresh_timer.start()

    def _generate_all(self, keys: list) -> None:
        self._gen_queue = list(keys)
        self._run_next()

    def _run_next(self) -> None:
        if not self._gen_queue or self.manager.project is None:
            return
        key = self._gen_queue.pop(0)
        self.navigate("generate")
        idx = self.report_center.cb_plan.findData(key)
        if idx >= 0:
            self.report_center.cb_plan.setCurrentIndex(idx)       # → _apply_plan
        self.generate_page.generate()

    def _on_generated_queue(self, _path: str) -> None:
        if self._gen_queue:
            self._run_next()

    # ------------------------------------------------------------------
    # وضعیت (Workflow در Explorer، نشان وضعیت، نوار وضعیت)
    # ------------------------------------------------------------------
    def _refresh_status(self) -> None:
        if not getattr(self, "_shell_ready", False):
            return
        project = self.manager.project
        self._update_save_label()
        has = project is not None
        for act in getattr(self, "_project_actions", []):
            act.setEnabled(has or act is self._actions.get("import"))
        if not has:
            self.ribbon.set_titles(APP_NAME_FA, "پروژه‌ای باز نیست")
            self.badge.set_state("pending", "بدون پروژه")
            self.lbl_sb_val.setText("")
            self.lbl_sb_path.setText("")
            self.explorer.set_tree(None)
            self._flow = []
            self.guide_bar.set_model(guide_model([], None))
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
        state, text = workflow.overall_status(project, items, findings, self._report_generated)
        ws0 = self._ws()
        heavy_open = (len(unresolved(findings)) if (ws0 and ws0.selection.heavy and findings) else 0)
        self._flow = compute_flow(project, ws0, self.settings, validation_errors=errors,
                                  heavy_unresolved=heavy_open, report_generated=self._report_generated)
        locks = {}
        for prev, cur in zip(self._flow, self._flow[1:]):
            if not cur.unlocked:
                first_open = next(s for s in self._flow if not s.passed)
                locks[cur.key] = f"ابتدا گام «{first_open.title}» را کامل کنید."
        self.guide_bar.set_model(guide_model(self._flow, ws0.selection))
        self.badge.set_state(state, text)
        self.ribbon.set_titles(APP_NAME_FA,
                               f"{project.title_text() or project.name or '(بدون عنوان)'}"
                               f"  ·  {project.report_number or '—'}")
        self.lbl_sb_val.setText(f"{errors} خطا · {warns} هشدار")
        self.lbl_sb_path.setText(str(self.manager.project_dir or ""))
        ws = self._ws()
        self._syncing = True
        try:
            states = {s.key: s.state for s in self._flow}
            self.explorer.set_tree(build_project_tree(project, ws, states, locks))
        finally:
            self._syncing = False
        for kind in StudyKind:
            act = self._actions[f"sel_{kind.value}"]
            act.blockSignals(True)
            act.setChecked(ws.selection.is_selected(kind))
            act.blockSignals(False)
        done = sum(1 for i in steps.values() if i.state == "done")
        nk = workflow.next_step(steps)
        labels = dict(workflow.STEPS)
        reports = ([(project.last_report_path, project.last_report_at)]
                   if project.last_report_path else [])
        self.home_page.update_project({
            "name": project.title_text() or project.name, "applicant": project.applicant_name,
            "type": "افزایش قدرت" if project.request_type == "increase" else "تأمین برق جدید",
            "feeders": len(project.feeders), "state": state, "status_text": text,
            "done": done, "total": len(workflow.STEPS), "next_key": nk,
            "next_label": labels.get(nk, ""), "reports": reports})
        if self._current_page_key() == "dashboard":
            self._refresh_dashboard()

    def _update_save_label(self) -> None:
        if self.manager.project is None:
            self.lbl_sb_save.setText("")
        else:
            self.lbl_sb_save.setText("● ذخیره نشده" if self.manager.dirty else "✓ ذخیره شده")
        if getattr(self, "_shell_ready", False):
            self.setWindowModified(bool(self.manager.project and self.manager.dirty))

    def _busy(self, busy: bool) -> None:
        QApplication.setOverrideCursor(Qt.BusyCursor) if busy else QApplication.restoreOverrideCursor()
        if getattr(self, "_shell_ready", False):
            self.progress.setVisible(busy)
            self.ribbon.setEnabled(not busy)
            if not busy:
                self._update_project_dependent_pages(refresh_pages=False)

    def _update_project_dependent_pages(self, refresh_pages: bool = True) -> None:
        if not getattr(self, "_shell_ready", False):
            return
        if refresh_pages:
            self._results = {}
            self.feeder_page.current = None
            self.feeder_page.refresh()
            self.images_page.refresh()
            self.generate_page.refresh()
            self.home_page.refresh_recent(self.settings.recent_projects)
        self._refresh_status()

    # ------------------------------------------------------------------
    # پروژهٔ جدید (انتخاب نوع مطالعات)
    # ------------------------------------------------------------------
    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        dlg = NewProjectDialog(self)
        if not dlg.exec():                      # QDialog.exec() = 1 (Accepted) / 0 (Rejected)
            return
        selection = dlg.selection()
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
        ws = self._ws()
        ws.selection = selection
        project.report_type = report_type_for_selection(selection)
        project.date_jalali = self._today()
        project.report_number = self._next_report_number()
        project.name = Path(self.manager.project_dir).name
        self.manager.save()
        self._after_project_loaded()
        self.navigate("project")
        self.statusBar().showMessage(f"پروژه جدید ایجاد شد: {self.manager.project_dir}", 5000)

    # ------------------------------------------------------------------
    # نمایش
    # ------------------------------------------------------------------
    def _toggle_explorer(self) -> None:
        self.explorer_panel.setVisible(self._actions["toggle_explorer"].isChecked())

    def _toggle_inspector(self) -> None:
        self.inspector_panel.setVisible(self._actions["toggle_inspector"].isChecked())

    def _toggle_ribbon(self) -> None:
        self.ribbon.set_collapsed(not self.ribbon.is_collapsed())

    def _reset_layout(self) -> None:
        for act, panel in (("toggle_explorer", self.explorer_panel),
                           ("toggle_inspector", self.inspector_panel)):
            self._actions[act].setChecked(True)
            panel.setVisible(True)
        self.splitter.setSizes([270, 900, 290])
        self.ribbon.set_collapsed(False)

    def _about(self) -> None:
        QMessageBox.information(self, "درباره", f"{APP_NAME_FA}\n{APP_NAME} {APP_VERSION}\n"
                                "محیط مطالعات مهندسی شبکه توزیع")
