# -*- coding: utf-8 -*-
"""Engineering Desktop Application — رابط حرفه‌ای مطالعات شبکه توزیع.

این ماژول پنجره اصلی جدید را با ساختار زیر پیاده‌سازی می‌کند:
- Menu Bar
- Toolbar
- Project Explorer (Tree View)
- Workspace (Tab-based)
- Property Inspector
- Dashboard
- Report Center
- Status Bar
- Dark/Light Theme
- RTL Support
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                               QVBoxLayout, QSplitter, QTreeView, QTabWidget,
                               QStatusBar, QMenuBar, QMenu, QToolBar, QLabel,
                               QFrame, QScrollArea, QStackedWidget, QMessageBox,
                               QFileDialog)
from PySide6.QtGui import QAction, QIcon, QDragDropEvent

from app import APP_NAME, APP_NAME_FA, APP_VERSION
from app.ui.theme import tokens, build_qss, THEMES


# کلیدهای صفحات Workspace
PAGE_PROJECT = "project"
PAGE_FEEDER = "feeder"
PAGE_RECLOSER = "recloser"
PAGE_SECTIONALIZER = "sectionalizer"
PAGE_ANALYSIS = "analysis"
PAGE_REPORT_PREVIEW = "report_preview"
PAGE_SETTINGS = "settings"
PAGE_HOME = "home"

ALL_PAGES = [
    PAGE_HOME,
    PAGE_PROJECT,
    PAGE_FEEDER,
    PAGE_RECLOSER,
    PAGE_SECTIONALIZER,
    PAGE_ANALYSIS,
    PAGE_REPORT_PREVIEW,
    PAGE_SETTINGS,
]


class EngineeringDesktop(QMainWindow):
    """پنجره اصلی Application حرفه‌ای مطالعات شبکه توزیع."""

    # سیگنال‌ها
    project_loaded = Signal(object)
    project_saved = Signal()
    study_changed = Signal(str)
    report_generated = Signal(str)

    def __init__(self, settings, manager, analysis_service):
        super().__init__()
        self.settings = settings
        self.manager = manager
        self.analysis = analysis_service

        self.current_theme = settings.theme or "light"
        self.current_page = PAGE_HOME
        self.selected_object = None  # شیء انتخاب‌شده در Project Explorer
        self._init_ui()
        self._apply_theme(self.current_theme)

    def _init_ui(self):
        """ساخت رابط کاربری اصلی."""
        self.setWindowTitle(f"{APP_NAME_FA} — {APP_NAME} {APP_VERSION}")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        # نمایشگرaskan central
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Menu Bar ---
        self._create_menu_bar()

        # --- Toolbar ---
        self._create_toolbar()

        # --- Main Splitter (Project Explorer | Workspace | Inspector) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizes([250, 600, 300])

        # پروژه اکسپلورر (چپ)
        project_explorer = self._create_project_explorer()
        splitter.addWidget(project_explorer)

        # Workspace (وسط)
        workspace = self._create_workspace()
        splitter.addWidget(workspace)

        # Property Inspector (راست)
        inspector = self._create_property_inspector()
        splitter.addWidget(inspector)

        main_layout.addWidget(splitter, 1)

        # --- Status Bar ---
        self._create_status_bar()

        # --- آیکون‌ها ---
        self._setup_icons()

    # ------------------------------------------------------------------
    # Menu Bar
    # ------------------------------------------------------------------
    def _create_menu_bar(self):
        """ایجاد Menu Bar با منوهای File, Project, Studies, Analysis, Report, View, Help."""
        menubar = self.menuBar()

        # File менیو
        file_menu = menubar.addMenu("فایل")
        file_menu.addAction("جدید", self._new_project, "Ctrl+N")
        file_menu.addAction("باز کردن", self._open_project, "Ctrl+O")
        file_menu.addAction("ذخیره", self._save_project, "Ctrl+S")
        file_menu.addAction("ذخیره به‌عنوان...", self._save_as)
        file_menu.addSeparator()
        file_menu.addAction("ورود از Excel", self._import_excel)
        file_menu.addSeparator()
        file_menu.addAction("خروج", self.close, "Ctrl+Q")

        # Project менیو
        project_menu = menubar.addMenu("پروژه")
        project_menu.addAction("مشخصات پروژه", self._show_project_info)
        project_menu.addAction("اعتبارسنجی", self._validate_project)
        project_menu.addSeparator()
        project_menu.addAction("مطالعات", self._show_studies)
        project_menu.addAction("گزارش‌ها", self._show_reports)

        # Studies менیو
        studies_menu = menubar.addMenu("مطالعات")
        studies_menu.addAction("متقاضی سنگین", self._navigate_to_study, 
                               "Ctrl+1")
        studies_menu.addAction("ریکلوزر", self._navigate_to_study,
                               "Ctrl+2")
        studies_menu.addAction("سکشنالایزر", self._navigate_to_study,
                               "Ctrl+3")

        # Analysis менیو
        analysis_menu = menubar.addMenu("تحلیل")
        analysis_menu.addAction("تحلیل مهندسی", self._navigate_to_analysis)
        analysis_menu.addAction("بازبینی مهندس", self._navigate_to_review)
        analysis_menu.addSeparator()
        analysis_menu.addAction("رارد数据的完整性", self._validate_integrity)

        # Report менیو
        report_menu = menubar.addMenu("گزارش")
        report_menu.addAction("Report Center", self._show_report_center,
                              "Ctrl+R")
        report_menu.addAction("پیش‌نمایش گزارش", self._show_report_preview)
        report_menu.addAction("تولید گزارش", self._generate_report)
        report_menu.addSeparator()
        report_menu.addAction("تنظیمات گزارش", self._show_report_settings)

        # View менیو
        view_menu = menubar.addMenu("نمایش")
        view_menu.addAction("بار منو", self._toggle_menu_bar, 
                            None, True)
        view_menu.addAction("نوار ابزار", self._toggle_toolbar,
                            None, True)
        view_menu.addAction("پانل اکسپلورر", self._toggle_project_explorer,
                            None, True)
        view_menu.addAction("مالکیت‌نظر", self._toggle_inspector,
                            None, True)
        view_menu.addSeparator()
        view_menu.addAction("تغییر Theme", self._toggle_theme)

        # Help менیو
        help_menu = menubar.addMenu("راهنما")
        help_menu.addAction("مستندات", self._show_docs)
        help_menu.addAction("درباره", self._show_about)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _create_toolbar(self):
        """ایجاد Toolbar با دکمه‌های سریع."""
        toolbar = QToolBar("ابزارها")
        toolbar.setIconSize(24)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        # دکمه‌های اصلی
        toolbar.addAction("جدید", self._new_project)
        toolbar.addAction("باز کردن", self._open_project)
        toolbar.addAction("ذخیره", self._save_project)
        toolbar.addSeparator()
        toolbar.addAction("ورود از Excel", self._import_excel)
        toolbar.addAction("اعتبارسنجی", self._validate_project)
        toolbar.addSeparator()
        toolbar.addAction("تحلیل", self._navigate_to_analysis)
        toolbar.addAction("گزارش", self._generate_report)

    # ------------------------------------------------------------------
    # Project Explorer (Tree View)
    # ------------------------------------------------------------------
    def _create_project_explorer(self):
        """ایجاد Project Explorer با Tree View."""
        container = QFrame()
        container.setObjectName("ProjectExplorer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # عنوان
        title = QLabel("پروژه")
        title.setObjectName("ExplorerTitle")
        layout.addWidget(title)

        # Tree View
        self.tree = QTreeView()
        self.tree.setObjectName("ProjectTree")
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.clicked.connect(self._on_tree_clicked)
        self.tree.expanded.connect(self._on_tree_expanded)
        layout.addWidget(self.tree, 1)

        # مشترک‌ها
        self._model = None  # TreeModel ساخته می‌شود هنگام 로드 پروژه

        return container

    def _setup_tree_model(self, project):
        """تنظیم Tree Model برای Project Explorer."""
        from PySide6.QtGui import QStandardItemModel, QStandardItem

        model = QStandardItemModel()
        model.setHorizontalHeaderItem(0, QStandardItem("پروژه"))

        root = QStandardItem("پروژه")
        root.setEditable(False)

        # پروژه Informationen
        info_item = QStandardItem("مشخصات پروژه")
        info_item.setEditable(False)
        info_item.setIcon(self._icon("info"))
        root.appendRow(info_item)

        # Network Studies
        network_item = QStandardItem("مطالعات شبکه")
        network_item.setEditable(False)
        network_item.setIcon(self._icon("network"))

        # فیدرها
        for feeder in project.feeders:
            feeder_item = QStandardItem(feeder.name or "فیدر بدون نام")
            feeder_item.setEditable(False)
            feeder_item.setIcon(self._icon("feeder"))
            network_item.appendRow(feeder_item)

        # Load Profile
        profile_item = QStandardItem("پروفیل بار")
        profile_item.setEditable(False)
        profile_item.setIcon(self._icon("profile"))
        network_item.appendRow(profile_item)

        # Forecast
        forecast_item = QStandardItem("پیش‌بینی")
        forecast_item.setEditable(False)
        forecast_item.setIcon(self._icon("forecast"))
        network_item.appendRow(forecast_item)

        # Power Flow
        loadflow_item = QStandardItem("پخش بار")
        loadflow_item.setEditable(False)
        loadflow_item.setIcon(self._icon("loadflow"))
        network_item.appendRow(loadflow_item)

        root.appendRow(network_item)

        # Protection Studies
        protection_item = QStandardItem("مطالعات حفاظت")
        protection_item.setEditable(False)
        protection_item.setIcon(self._icon("protection"))

        # Recloser
        if project.report_center.studies.get("recloser", {}).get("enabled"):
            recloser_item = QStandardItem("ریکلوزر")
            recloser_item.setEditable(False)
            recloser_item.setIcon(self._icon("recloser"))
            protection_item.appendRow(recloser_item)

        # Sectionalizer
        if project.report_center.studies.get("sectionalizer", {}).get("enabled"):
            secz_item = QStandardItem("سکشنالایزر")
            secz_item.setEditable(False)
            secz_item.setIcon(self._icon("sectionalizer"))
            protection_item.appendRow(secz_item)

        root.appendRow(protection_item)

        # Reports
        reports_item = QStandardItem("گزارش‌ها")
        reports_item.setEditable(False)
        reports_item.setIcon(self._icon("report"))

        # Heavy Applicant Report
        if project.report_center.studies.get("heavy", {}).get("include_in_report"):
            heavy_item = QStandardItem("گزارش متقاضی سنگین")
            heavy_item.setEditable(False)
            heavy_item.setIcon(self._icon("report"))
            reports_item.appendRow(heavy_item)

        # Protection Reports
        if project.report_center.studies.get("recloser", {}).get("include_in_report"):
            recloser_report_item = QStandardItem("گزارش ریکلوزر")
            recloser_report_item.setEditable(False)
            recloser_report_item.setIcon(self._icon("report"))
            reports_item.appendRow(recloser_report_item)

        if project.report_center.studies.get("sectionalizer", {}).get("include_in_report"):
            secz_report_item = QStandardItem("گزارش سکشنالایزر")
            secz_report_item.setEditable(False)
            secz_report_item.setIcon(self._icon("report"))
            reports_item.appendRow(secz_report_item)

        # Combined Report
        if (project.report_center.both_protection_enabled() and
                project.report_center.protection_report.combined):
            combined_item = QStandardItem("گزارش ترکیبی")
            combined_item.setEditable(False)
            combined_item.setIcon(self._icon("report"))
            reports_item.appendRow(combined_item)

        root.appendRow(reports_item)

        model.appendRow(root)
        self.tree.setModel(model)
        self._model = model

    # ------------------------------------------------------------------
    # Workspace (Tab-based)
    # ------------------------------------------------------------------
    def _create_workspace(self):
        """ایجاد Workspace با QTabWidget."""
        container = QFrame()
        container.setObjectName("Workspace")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # تب‌ها
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setTabBarAutoHide(False)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        # صفحه home
        self.home_page = self._create_home_page()
        self.tabs.addTab(self.home_page, "داشبورد")

        # Stack برای صفحات دیگر
        self.page_stack = QStackedWidget()
        self.tabs.addTab(self.page_stack, "صفحات")

        layout.addWidget(self.tabs, 1)

        return container

    def _create_home_page(self):
        """ایجاد Dashboard (صفحه اصلی)."""
        from app.ui.home_page import HomePage
        return HomePage(self.manager.recent_projects, self.current_theme)

    def _add_page(self, page_key: str, page_widget: QWidget, page_title: str):
        """اضافه کردن صفحه به Workspace."""
        # ذخیره صفحه در stack
        index = self.page_stack.addWidget(page_widget)
        # اگر تب مربوط به این صفحه وجود ندارد، ایجاد کن
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == self.page_stack:
                self.tabs.setTabText(i, f"✱ {page_title}")
                break
        # Activate the page
        self.page_stack.setCurrentIndex(index)

    def _close_tab(self, index):
        """بستن تب."""
        if index == 0:
            return  # نمی‌توان تب اصلی را بست
        if index == 1:
            # تب page_stack - نمی‌توان بست
            return
        self.tabs.removeTab(index)

    # ------------------------------------------------------------------
    # Property Inspector
    # ------------------------------------------------------------------
    def _create_property_inspector(self):
        """ایجاد Property Inspector."""
        container = QFrame()
        container.setObjectName("Inspector")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # عنوان
        title = QLabel("ویژگی‌ها")
        title.setObjectName("InspectorTitle")
        layout.addWidget(title)

        # بین여 separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Stack برای نمایش‌دهنده properties
        self.inspector_stack = QStackedWidget()

        # صفحه empty (وقتی هیچ شیء انتخاب نشده)
        empty_page = self._create_empty_inspector()
        self.inspector_stack.addWidget(empty_page)

        layout.addWidget(self.inspector_stack, 1)

        return container

    def _create_empty_inspector(self):
        """ایجاد صفحه empty برای Inspector."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        icon = QLabel()
        icon.setPixmap(self._icon_pixmap("empty", 64, 64))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        label = QLabel("هیچ شیء انتخاب نشده است.\nیک آیتم از پروژه انتخاب کنید.")
        label.setObjectName("EmptyInspectorText")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)

        return page

    # ------------------------------------------------------------------
    # Status Bar
    # ------------------------------------------------------------------
    def _create_status_bar(self):
        """ایجاد Status Bar."""
        status = QStatusBar()
        self.setStatusBar(status)

        # عناصر Status Bar
        self.lbl_project = QLabel("")
        self.lbl_save = QLabel("")
        self.lbl_validation = QLabel("")
        self.lbl_status = QLabel("")

        status.addPermanentWidget(self.lbl_validation, 0)
        status.addPermanentWidget(self.lbl_save, 0)
        status.addWidget(self.lbl_project, 0)
        status.addWidget(self.lbl_status, 1)

    # ------------------------------------------------------------------
    # آیکون‌ها
    # ------------------------------------------------------------------
    def _icon(self, name: str):
        """دریافت آیکون با نام."""
        from app.ui.icons import icon
        return icon(name, self._token("sidebar_text"), 16)

    def _icon_pixmap(self, name: str, width: int = 32, height: int = 32):
        """دریافت Pixmap آیکون."""
        from app.ui.icons import icon_pixmap
        return icon_pixmap(name, width, height, self._token("text"))

    def _token(self, key: str) -> str:
        """دریافت token از theme."""
        return tokens(self.current_theme).get(key, "#000000")

    # ------------------------------------------------------------------
    # اعمال Theme
    # ------------------------------------------------------------------
    def _apply_theme(self, theme_name: str):
        """اعمال Theme."""
        self.current_theme = theme_name
        self.setStyleSheet(build_qss(theme_name))
        # به‌روزرسانی آیکون‌ها
        self._update_icons()

    def _update_icons(self):
        """به‌روزرسانی آیکون‌ها بر اساس Theme."""
        # آیکون‌های menu
        for action in self.menuBar().actions():
            if hasattr(action, 'icon'):
                pass  # آیکون‌های استاندارد
        # آیکون‌های toolbar
        # TODO: به‌روزرسانی آیکون‌ها

    # ------------------------------------------------------------------
    # اقدامات
    # ------------------------------------------------------------------
    def _new_project(self):
        """ایجاد پروژه جدید."""
        path, _ = QFileDialog.getSaveFileName(
            self, "ایجاد پروژه جدید", "", "پروژه Reports (*.json)")
        if path:
            self.manager.new_project(path)
            self._after_project_loaded()
            self.statusBar().showMessage(f"پروژه جدید ایجاد شد: {path}", 3000)

    def _open_project(self):
        """باز کردن پروژه."""
        path, _ = QFileDialog.getOpenFileName(
            self, "باز کردن پروژه", "", "پروژه (*.json)")
        if path:
            self.manager.open_project(path)
            self._after_project_loaded()
            self.statusBar().showMessage(f"پروژه باز شد: {path}", 3000)

    def _save_project(self):
        """ذخیره پروژه."""
        if self.manager.project:
            self.manager.save()
            self.statusBar().showMessage("پروژه ذخیره شد.", 3000)

    def _save_as(self):
        """ذخیره به‌عنوان."""
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره به‌عنوان", "", "پروژه (*.json)")
        if path:
            self.manager.save(path)
            self.statusBar().showMessage(f"پروژه ذخیره شد: {path}", 3000)

    def _import_excel(self):
        """ورود از Excel."""
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل Excel", "", "Excel (*.xlsx *.xlsm)")
        if path:
            # TODO: Implement Excel import
            QMessageBox.information(self, "ورود از Excel",
                                    "import از Excel در حال پیشرفت است.")

    def _validate_project(self):
        """اعتبارسنجی پروژه."""
        if self.manager.project:
            items = self.analysis.validate()
            errors = [i for i in items if i.status == "error"]
            warnings = [i for i in items if i.status == "warning"]
            if errors:
                QMessageBox.critical(self, "اعتبارسنجی",
                                     f"خطاها:\n\n" + "\n".join(errors))
            else:
                QMessageBox.information(self, "اعتبارسنجی",
                                        f"هیچ خطایی وجود ندارد.\n"
                                        f"هشدارها: {len(warnings)}")

    def _show_project_info(self):
        """نمایش اطلاعات پروژه."""
        if self.manager.project:
            info = self.manager.project
            QMessageBox.information(self, "مشخصات پروژه",
                                    f"نام: {info.name}\n"
                                    f"شماره گزارش: {info.report_number}\n"
                                    f"تاریخ: {info.date_jalali}")

    def _show_studies(self):
        """نمایش مطالعات."""
        if self.manager.project:
            rc = self.manager.project.report_center
            studies = rc.active_studies()
            QMessageBox.information(self, "مطالعات",
                                    f"مطالعات فعال:\n\n" + "\n".join(studies))

    def _show_reports(self):
        """نمایش گزارش‌ها."""
        if self.manager.project:
            rc = self.manager.project.report_center
            QMessageBox.information(self, "گزارش‌ها",
                                    f"گزارش‌های فعال:\n\n"
                                    f"مطالعات: {rc.report_studies()}")

    def _navigate_to_study(self):
        """ Następ到 مطالعه."""
        # TODO: Implement
        pass

    def _navigate_to_analysis(self):
        """ Następ到 تحلیل."""
        # TODO: Implement
        pass

    def _navigate_to_review(self):
        """ Następ到 بازبینی."""
        # TODO: Implement
        pass

    def _show_report_center(self):
        """نمایش Report Center."""
        # TODO: Implement
        pass

    def _show_report_preview(self):
        """نمایش پیش‌نمایش گزارش."""
        # TODO: Implement
        pass

    def _generate_report(self):
        """تولید گزارش."""
        # TODO: Implement
        pass

    def _show_report_settings(self):
        """نمایش تنظیمات گزارش."""
        # TODO: Implement
        pass

    def _toggle_menu_bar(self, checked: bool):
        """تغییر/show/hide Menu Bar."""
        self.menuBar().setVisible(checked)

    def _toggle_toolbar(self, checked: bool):
        """تغییر/show/hide Toolbar."""
        self.toolBar().setVisible(checked)

    def _toggle_project_explorer(self, checked: bool):
        """تغییر/show/hide Project Explorer."""
        if self.centralWidget():
            splitter = self.centralWidget().layout().itemAt(0).widget()
            if splitter:
                splitter.widget(0).setVisible(checked)

    def _toggle_inspector(self, checked: bool):
        """تغییر/show/hide Inspector."""
        if self.centralWidget():
            splitter = self.centralWidget().layout().itemAt(0).widget()
            if splitter:
                splitter.widget(2).setVisible(checked)

    def _toggle_theme(self):
        """تغییر Theme."""
        new_theme = "dark" if self.current_theme == "light" else "light"
        self._apply_theme(new_theme)
        self.settings.theme = new_theme
        self.settings.save()

    def _show_docs(self):
        """نمایش مستندات."""
        QMessageBox.information(self, "مستندات",
                                "مستندات در حال آماده‌سازی است.")

    def _show_about(self):
        """نمایش درباره."""
        QMessageBox.about(self, "درباره",
                           f"{APP_NAME_FA} {APP_VERSION}\n\n"
                           f"نرم‌افزار حرفه‌ای مطالعات مهندسی شبکه توزیع.")

    # ------------------------------------------------------------------
    # د 회의에서 clicked
    # ------------------------------------------------------------------
    def _on_tree_clicked(self, index):
        """클릭된 Tree Item."""
        item = self._model.itemFromIndex(index)
        if item:
            self.selected_object = item.text()
            self._show_inspector(item)

    def _on_tree_expanded(self, index):
        """Tree Item باز شده."""
        pass

    def _show_inspector(self, item):
        """نمایش Inspector برای آیتم انتخاب‌شده."""
        # TODO: Implement context-sensitive inspector
        pass

    # ------------------------------------------------------------------
    # پس از 로드 پروژه
    # ------------------------------------------------------------------
    def _after_project_loaded(self):
        """بعد از 로드 پروژه."""
        project = self.manager.project
        if project:
            self._setup_tree_model(project)
            self.lbl_project.setText(project.name or "پروژه")
            self.lbl_save.setText("● ذخیره نشده" if self.manager.dirty else "✓ ذخیره شده")
            self.project_loaded.emit(project)

    def _update_status(self):
        """به‌روزرسانی Status Bar."""
        project = self.manager.project
        if project:
            self.lbl_project.setText(project.name or "پروژه")
            self.lbl_save.setText("● ذخیره نشده" if self.manager.dirty else "✓ ذخیره شده")
        else:
            self.lbl_project.setText("")
            self.lbl_save.setText("")
