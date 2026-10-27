# -*- coding: utf-8 -*-
"""صفحه‌های ورود داده به تفکیک هر مطالعه (v2.0.0).

* ``HeavyStudyPage``  — متقاضی سنگین: [اطلاعات متقاضی] [فیدرها و پخش بار] [مطالعه مصارف سنگین]
* ``ProtectionStudyPage`` — ریکلوزر یا سکشنالایزر: [تجهیز مورد مطالعه] [تنظیمات و اعتبارسنجی]
  (فیدرهای محدودهٔ مطالعه از v2.3.0 صفحهٔ مشترک و جداگانه دارند)

هر صفحه یک ``QTabWidget`` است؛ ورودی هر مطالعه از مطالعهٔ دیگر جداست و فرم‌ها فقط
داده را در مدل ذخیره می‌کنند (بدون منطق مهندسی).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QWidget

from app.core.studies import StudyKind
from app.ui.protection_page import PREFIX_OF_KIND, ProtectionPage
from app.ui.shell.protection_settings_page import ProtectionSettingsPage


class HeavyStudyPage(QTabWidget):
    """متقاضی سنگین: تب‌ها بر پایهٔ صفحه‌های موجود (بدون تکرار فرم).

    v2.5.0 — تب چهارم «نیروگاه‌ها و اتوبوستر» (اختیاری) برای ورودی مشترک
    همه مطالعات اضافه شد.
    """

    TAB_KEYS = ("applicant", "feeders", "study", "assets")

    def __init__(self, applicant_page: QWidget, feeder_page: QWidget, study_page: QWidget,
                 assets_page: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        self.applicant_page, self.feeder_page, self.study_page = applicant_page, feeder_page, study_page
        self.assets_page = assets_page
        self.addTab(applicant_page, "اطلاعات متقاضی")
        self.addTab(feeder_page, "فیدرها و پخش بار")
        self.addTab(study_page, "مطالعه مصارف سنگین")
        if assets_page is not None:
            self.addTab(assets_page, "نیروگاه‌ها و اتوبوستر")

    def show_tab(self, key: str) -> None:
        if key in self.TAB_KEYS:
            self.setCurrentIndex(self.TAB_KEYS.index(key))


class ProtectionStudyPage(QTabWidget):
    """یک مطالعهٔ حفاظتی (ریکلوزر یا سکشنالایزر) با ورودی‌های مستقل.

    v2.3.0 — تب «فیدرهای محدوده و شبکه» به صفحهٔ مشترک «فیدرهای محدودهٔ مطالعه»
    منتقل شد تا فیدرها برای هر دو مطالعه فقط یک‌بار وارد شوند.
    """

    changed = Signal()
    evaluated = Signal(object)
    TAB_KEYS = ("device", "settings")

    def __init__(self, manager, settings, kind: StudyKind, get_workspace: Callable,
                 get_theme: Callable[[], str], parent=None) -> None:
        super().__init__(parent)
        self.kind = StudyKind(kind)
        self.device = ProtectionPage(manager, settings, only=PREFIX_OF_KIND[self.kind.value])
        self.settings_page = ProtectionSettingsPage(manager, get_workspace, get_theme, kind=self.kind)
        self.addTab(self.device, "تجهیز مورد مطالعه")
        self.addTab(self.settings_page, "تنظیمات و اعتبارسنجی")
        for w in (self.device, self.settings_page):
            w.changed.connect(self.changed)
        self.settings_page.evaluated.connect(self.evaluated)
        self.goto_requested = self.settings_page.goto_requested
        self.currentChanged.connect(self._on_tab)

    def show_tab(self, key: str) -> None:
        if key in self.TAB_KEYS:
            self.setCurrentIndex(self.TAB_KEYS.index(key))

    def focus_field(self, tab: str, key: str) -> bool:
        """باز کردن تب و Focus روی فیلد دقیق (برای لینک‌های ردیابی خطا)."""
        self.show_tab(tab)
        target = {"device": self.device, "settings": self.settings_page}.get(tab)
        return bool(target and target.focus_field(key))

    def refresh(self) -> None:
        self.device.refresh()
        self.settings_page.refresh()

    def save_to_project(self) -> None:
        self.device.save_to_project()
        self.settings_page.save_to_project()

    def _on_tab(self, _i: int) -> None:
        self.save_to_project()
        self.settings_page.validate()
