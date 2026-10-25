# -*- coding: utf-8 -*-
"""آزمون‌های v2.4.1 — ورود پاسخ هوش مصنوعی از فایل (مسیر آفلاین).

کاربر بسته ZIP را در هر ابزار هوش مصنوعی بارگذاری می‌کند، پاسخ JSON را در فایلی
مانند ReportForge_AI_revised.json ذخیره می‌کند و با دکمهٔ «بارگذاری پاسخ از فایل…»
وارد برنامه می‌کند. باید دقیقاً همان مسیر بررسی مسیر API طی شود: اعتبارسنجی JSON،
فیلتر کلیدهای درخواست‌شده و نگهبان عددهای ناشناخته.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

os.environ.setdefault("REPORTFORGE_HOME", tempfile.mkdtemp(prefix="rf_home_v241_"))

from app import pyside_compat  # noqa: F401
from PySide6.QtWidgets import QApplication, QFileDialog

QApplication.instance() or QApplication([])

from app.ai.package import AIPackage, SectionText
from app.ai.providers import AIError
from app.ai.service import proposal_from_text
from app.core.settings import AppSettings


def _pkg() -> AIPackage:
    pkg = AIPackage()
    pkg.sections = [SectionText("intro", "مقدمه", "متن قدیمی با عدد 400"),
                    SectionText("concl", "نتیجه‌گیری", "جمع‌بندی")]
    pkg.requested = ["intro", "concl"]
    pkg.data_text = "400 آمپر"
    return pkg


# ---------------------------------------------------------------------------
# ۱) منطق مشترک: proposal_from_text همان خروجی مسیر API را می‌سازد
# ---------------------------------------------------------------------------
def test_proposal_from_text_parses_fenced_json_and_flags_numbers():
    raw = ('```json\n{"sections": {"intro": "متن نو با عدد 400 و عدد جدید 630",'
           ' "concl": "جمع‌بندی بهتر"}, "notes": "اصلاح نگارش"}\n```')
    p = proposal_from_text(raw, _pkg())
    assert p.notes == "اصلاح نگارش"
    assert [s.key for s in p.sections] == ["intro", "concl"]
    intro = p.sections[0]
    assert intro.original == "متن قدیمی با عدد 400"
    assert "630" in intro.unverified and "400" not in intro.unverified
    assert p.sections[1].unverified == []


def test_proposal_from_text_ignores_unrequested_keys():
    raw = json.dumps({"sections": {"intro": "الف", "hacker_key": "ب"}, "notes": ""},
                     ensure_ascii=False)
    p = proposal_from_text(raw, _pkg())
    assert [s.key for s in p.sections] == ["intro"]


def test_proposal_from_text_rejects_invalid_file():
    with pytest.raises(AIError):
        proposal_from_text("این JSON نیست", _pkg())
    with pytest.raises(AIError):
        proposal_from_text('{"no_sections": 1}', _pkg())


# ---------------------------------------------------------------------------
# ۲) صفحهٔ دستیار: دکمهٔ «بارگذاری پاسخ از فایل…» پیشنهادها را وارد رابط بررسی می‌کند
# ---------------------------------------------------------------------------
class _Mgr:
    project = None
    image_path = staticmethod(lambda i: None)


def _page(monkeypatch):
    from app.ui.shell.ai_page import AIPage
    s = AppSettings()
    monkeypatch.setattr(s, "save", lambda: None)
    page = AIPage(_Mgr(), s, lambda: None, lambda: None, lambda: {})
    page.refresh()
    return page


def test_ai_page_has_load_response_button(monkeypatch):
    page = _page(monkeypatch)
    assert page.btn_load_resp.text() == "بارگذاری پاسخ از فایل…"


def test_ai_page_load_response_populates_review_ui(tmp_path, monkeypatch):
    page = _page(monkeypatch)
    pkg = _pkg()
    monkeypatch.setattr(page, "_build_package", lambda: pkg)
    f = tmp_path / "ReportForge_AI_revised.json"
    f.write_text(json.dumps({"sections": {"intro": "متن اصلاح‌شده", "concl": "پایان"},
                             "notes": "ok"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(f), "")))
    page._load_response()
    assert page.results.count() == 2
    assert page._proposal.sections[0].suggested == "متن اصلاح‌شده"
    assert "پاسخ از فایل وارد شد" in page.lbl_status.text()


def test_ai_page_load_response_warns_on_bad_file(tmp_path, monkeypatch):
    page = _page(monkeypatch)
    monkeypatch.setattr(page, "_build_package", lambda: _pkg())
    f = tmp_path / "bad.json"
    f.write_text("خروجی بدون JSON", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(f), "")))
    warned = []
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a)))
    page._load_response()
    assert warned and page.results.count() == 0


def test_ai_page_load_response_cancel_is_noop(monkeypatch):
    page = _page(monkeypatch)
    monkeypatch.setattr(page, "_build_package", lambda: _pkg())
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    page._load_response()                      # انصراف کاربر: بدون خطا و بدون تغییر
    assert page.results.count() == 0


# ---------------------------------------------------------------------------
# ۳) راهنمای بازگرداندن پاسخ داخل task.md بسته ZIP
# ---------------------------------------------------------------------------
def test_task_md_mentions_round_trip(monkeypatch, tmp_path):
    import io
    import zipfile

    from app.ai.package import build_package
    from app.core.models import Project
    from app.core.workspace import workspace_from_project

    proj = Project()
    ws = workspace_from_project(proj)

    class _Report:
        sections = []

    pkg = build_package(proj, ws, _Report(), None, AppSettings().ai,
                        lambda i: None, [])
    task = pkg.files["task.md"].decode("utf-8")
    assert "ReportForge_AI_revised.json" in task
    assert "بارگذاری پاسخ از فایل" in task
    zf = zipfile.ZipFile(io.BytesIO(pkg.to_zip_bytes()))
    assert "task.md" in zf.namelist()
