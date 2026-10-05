# -*- coding: utf-8 -*-
"""v1.0.3 — تست‌های UI (offscreen): ناوبری، Theme، وضعیت Workflow، بازبینی، تولید."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from sample_projects import make_feeder, make_project  # noqa: E402

from app.core import workflow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    a.setLayoutDirection(Qt.RightToLeft)
    return a


@pytest.fixture()
def win(app, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTFORGE_HOME", str(tmp_path / "home"))
    from app.ui.main_window import MainWindow
    w = MainWindow()
    p = make_project()
    p.feeders = [make_feeder(years=[1401, 1402, 1403, 1404, 1405], values=[4.0, 4.3, 4.5, 4.9, 5.1])]
    w.manager.new_project(tmp_path / "proj", p)
    w._after_project_loaded()
    w.settings.output_dir = str(tmp_path)
    yield w
    w.manager.dirty = False
    w.close()


def test_all_pages_open_without_error_in_both_themes(win, app):
    for theme in ("light", "dark"):
        win.apply_theme(theme)
        for key in win.pages:
            win.navigate(key)
            app.processEvents()
            assert win.current_key == key


def test_nav_blocked_without_project(app, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTFORGE_HOME", str(tmp_path))
    from app.ui.main_window import MainWindow
    w = MainWindow()
    w.navigate("generate")
    assert w.current_key == "home"
    assert not w.nav_buttons["generate"].isEnabled() and w.nav_buttons["settings"].isEnabled()
    w.close()


def test_theme_toggle_persists_in_settings(win):
    start = win.settings.theme
    win.toggle_theme()
    assert win.settings.theme != start
    from app.core.settings import AppSettings
    assert AppSettings.load().theme == win.settings.theme


def test_workflow_states_with_errors_and_with_ready(win):
    from app.core.validation import validate_project
    items = validate_project(win.manager.project, win.settings)
    steps = workflow.compute_steps(win.manager.project, items, win.analysis.findings())
    assert steps["validation"].state in ("done", "warning")
    win.manager.project.feeders[0].after.loss_kw = None
    items = validate_project(win.manager.project, win.settings)
    steps = workflow.compute_steps(win.manager.project, items, [])
    assert steps["validation"].state == "error" and steps["generate"].state == "todo"
    st, _txt = workflow.overall_status(win.manager.project, items, [], False)
    assert st == "error"


def test_review_page_accept_and_comment_flow(win, app):
    win.navigate("review")
    rp = win.review_page
    assert rp.list.count() >= 5
    rp.list.setCurrentRow(0)
    rp.txt_comment.setPlainText("بررسی شد")
    rp._decide("accepted")
    key = rp._current.key
    assert win.manager.project.reviews[key].status == "accepted"
    assert win.manager.project.reviews[key].comment == "بررسی شد"


def test_review_reject_requires_comment(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[1]))
    win.navigate("review")
    rp = win.review_page
    rp.list.setCurrentRow(0)
    rp.txt_comment.setPlainText("")
    rp._decide("rejected")
    assert shown and not win.manager.project.reviews


def test_generate_in_background_creates_docx(win, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    win.settings.open_folder_after = False
    win.navigate("generate")
    gp = win.generate_page
    done = []
    gp.generated.connect(done.append)
    gp.generate()
    t0 = time.time()
    while not done and time.time() - t0 < 60:
        app.processEvents()
        time.sleep(0.05)
    assert done, "تولید گزارش تمام نشد"
    from pathlib import Path
    assert Path(done[0]).exists() and Path(done[0]).suffix == ".docx"
    assert win.manager.project.last_report_path == done[0]
    assert gp._thread is None            # Thread تمیز بسته شده


def test_generate_blocked_on_validation_error(win, app):
    win.manager.project.feeders = []
    win.navigate("generate")
    assert not win.generate_page.btn_generate.isEnabled()


def test_preview_manual_edit_survives_regeneration(win, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    win.navigate("preview")
    pv = win.preview_page
    pv.section_list.setCurrentRow(5)         # جمع‌بندی
    pv.editor.setPlainText("جمع‌بندی دستی مهندس.")
    pv.save_manual_text()
    rep = win.analysis.get(force=True)
    txt = "\n".join(p.text for s in rep.sections if s.key == "conclusion" for p in s.paragraphs())
    assert txt == "جمع‌بندی دستی مهندس."


def test_dashboard_shows_current_project(win):
    win._refresh_status()
    assert "افزایش قدرت" in win.home_page.lbl_name.text()
    assert win.home_page.btn_continue.isVisible() or win.home_page.btn_continue.text()


def test_feeder_manual_edit_marks_source_manual(win):
    win.navigate("input")
    fp = win.feeder_page
    fp.sp_peak.setValue(5.4)
    f = win.manager.project.feeders[0]
    assert f.data_sources.get("peak_load_mw") == "MANUAL"


def _import_order(path):
    import ast
    order, full_names = [], []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
            full_names += names
            order += [n.split(".")[0] for n in names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            order.append(node.module.split(".")[0])
            imported = [a.name for a in node.names]
            full_names.append(node.module)
            if node.module == "six.moves":
                assert "_thread" in imported or "range" in imported
    return order, full_names


def test_import_order_before_pyside():
    """رگرسیون کرش «_SixMetaPathImporter»: pandas/six باید قبل از PySide6 import شوند."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main_order, _ = _import_order(root / "app" / "main.py")
    first_qt = main_order.index("PySide6")
    assert "app" in main_order and main_order.index("app") < first_qt
    order, full_names = _import_order(root / "app" / "pyside_compat.py")
    assert "PySide6" not in order
    for lib in ("six", "dateutil", "numpy", "pandas", "matplotlib", "openpyxl", "docx"):
        assert lib in order, lib
    assert "dateutil.rrule" in full_names
    assert "matplotlib.pyplot" in full_names
