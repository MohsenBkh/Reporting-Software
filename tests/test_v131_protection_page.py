# -*- coding: utf-8 -*-
"""v1.4.0 — تب مجزا «سکشنالایزر و ریکلوزر» (جدا از مطالعه مصارف سنگین).

این تست‌ها نیازمند رابط گرافیکی (PySide6/QtWidgets) هستند و در محیط بدون
کتابخانه گرافیک اجرا نمی‌شوند؛ روی دستگاه هدف کامل سبز می‌شوند.
"""
from __future__ import annotations

import pytest

from sample_projects import make_feeder, make_project  # noqa: E402

from app.core.models import RecloserInfo, SectionalizerInfo
from app.core.report_types import REPORT_TYPE_HEAVY, REPORT_TYPE_SECTIONALIZER


@pytest.fixture(scope="module")
def app():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    a.setLayoutDirection(Qt.RightToLeft)
    return a


@pytest.fixture()
def win(app, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTFORGE_HOME", str(tmp_path / "home"))
    from app.ui.main_window import MainWindow
    w = MainWindow()
    p = make_project()
    p.feeders = [make_feeder()]
    w.manager.new_project(tmp_path / "proj", p)
    w._after_project_loaded()
    yield w
    w.manager.dirty = False
    w.close()


# ---------------------------------------------------------------------------
# تب مجزا در ناوبری
# ---------------------------------------------------------------------------
def test_protection_is_a_separate_nav_tab(app, win):
    from app.ui.main_window import NAV
    keys = [k for k, _c, _i, _r in NAV]
    assert "protection" in keys
    # جدا از «مطالعه مصارف سنگین» و بعد از آن می‌آید
    assert keys.index("protection") == keys.index("study") + 1
    assert "protection" in win.pages


def test_protection_nav_blocked_without_project(app, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTFORGE_HOME", str(tmp_path / "home2"))
    from app.ui.main_window import MainWindow
    w = MainWindow()
    w.navigate("protection")
    assert w.current_key == "home"        # بدون پروژه اجازه ورود نیست
    assert not w.nav_buttons["protection"].isEnabled()
    w.close()


def test_navigate_to_protection_loads_and_shows(app, win):
    win.navigate("protection")
    assert win.current_key == "protection"
    page = win.protection_page
    assert page.tabs.count() == 2
    assert page.tabs.tabText(0) == "سکشنالایزر"
    assert page.tabs.tabText(1) == "ریکلوزر"


# ---------------------------------------------------------------------------
# ذخیره/بازیابی داده‌های هر دو تب در پروژه
# ---------------------------------------------------------------------------
def test_sectionalizer_fields_save_to_project(app, win):
    win.navigate("protection")
    page = win.protection_page
    f = page.secz_fields
    f["feeder_name"].setText("فیدر ۲۰کیلوولت نمونه")
    f["installation_location"].setText("تیر ۱۲۳")
    f["fault_current_ka"].setValue(4.5)
    f["pickup_current_a"].setValue(280.0)
    f["tms"].setValue(0.15)
    page.save_to_project()

    p = win.manager.project
    assert p.sectionalizer.feeder_name == "فیدر ۲۰کیلوولت نمونه"
    assert p.sectionalizer.installation_location == "تیر ۱۲۳"
    assert p.sectionalizer.fault_current_ka == 4.5
    assert p.sectionalizer.pickup_current_a == 280.0
    assert p.sectionalizer.tms == 0.15
    assert p.sectionalizer.is_complete()


def test_recloser_fields_save_separately(app, win):
    win.navigate("protection")
    page = win.protection_page
    page.tabs.setCurrentIndex(1)           # تب ریکلوزر
    f = page.rcls_fields
    f["feeder_name"].setText("فیدر ریکلوزری")
    f["fault_current_ka"].setValue(6.0)
    page.save_to_project()

    p = win.manager.project
    assert p.recloser.feeder_name == "فیدر ریکلوزری"
    assert p.recloser.fault_current_ka == 6.0
    # داده‌های سکشنالایزر دست‌نخورده باقی می‌مانند
    assert p.sectionalizer.feeder_name == ""


def test_load_from_project_fills_both_tabs(app, win):
    p = win.manager.project
    p.sectionalizer = SectionalizerInfo(feeder_name="فیدر س", fault_current_ka=3.0)
    p.recloser = RecloserInfo(feeder_name="فیدر ر", tms=0.2)
    win.navigate("protection")
    page = win.protection_page
    assert page.secz_fields["feeder_name"].text() == "فیدر س"
    assert page.secz_fields["fault_current_ka"].value() == 3.0
    assert page.rcls_fields["feeder_name"].text() == "فیدر ر"
    assert page.rcls_fields["tms"].value() == 0.2


# ---------------------------------------------------------------------------
# v2.0.0 — نوع گزارش از Report Center تنظیم می‌شود؛ صفحه فقط یک تجهیز را هم نشان می‌دهد
# ---------------------------------------------------------------------------
def test_protection_page_has_no_report_type_bar(app, win):
    page = win.protection_page
    assert "secz_type_btn" not in vars(page) and "rcls_type_btn" not in vars(page)


def test_protection_page_single_device_mode(app, win):
    from app.ui.protection_page import ProtectionPage
    page = ProtectionPage(win.manager, win.settings, only="rcls")
    assert page.tabs.count() == 1 and hasattr(page, "rcls_fields")
    assert not hasattr(page, "secz_fields")
    win.manager.project.recloser = RecloserInfo(feeder_name="فیدر ر", tms=0.2)
    page.refresh()
    assert page.rcls_fields["feeder_name"].text() == "فیدر ر"
    page.rcls_fields["feeder_name"].setText("فیدر جدید")
    page.save_to_project()
    assert win.manager.project.recloser.feeder_name == "فیدر جدید"


def test_collect_forms_saves_active_protection_page(app, win):
    win.navigate("protection")
    page = win.protection_page
    page.secz_fields["feeder_name"].setText("فیدر جمع‌آوری")
    win._collect_forms()
    assert win.manager.project.sectionalizer.feeder_name == "فیدر جمع‌آوری"
