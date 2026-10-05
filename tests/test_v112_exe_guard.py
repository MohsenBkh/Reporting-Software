# -*- coding: utf-8 -*-
"""تست‌های اصلاح v1.1.2 — رفع کرش فایل اجرایی (exe) در شروع برنامه.

خطای اصلی که این تست‌ها قفل می‌کنند:

    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'

مسیر: shibokensupport.feature_imported → inspect.getsource → pyi_rth_inspect
(inspect.getfile) → importlib._bootstrap._module_repr_from_spec → list(loader._path)
(باگ CPython 3.12.0–3.12.3 روی ماژول‌های مجازی six.moves).
"""
from __future__ import annotations

import ast
import importlib
import importlib._bootstrap as _bootstrap
import importlib.util
import inspect
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RTHOOK = REPO / "app" / "pyi_rth_reportforge.py"
SPEC = REPO / "ReportForge.spec"


@pytest.fixture(scope="module")
def qapp():
    """نمونهٔ QApplication برای آزمون خودکار شروع برنامه."""
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


def _buggy_repr_from_spec(spec):  # noqa: ANN001 — عیناً کد CPython 3.12.0
    name = "?" if spec.name is None else spec.name
    if spec.origin is None:
        if spec.loader is None:
            return f"<module {name!r}>"
        return f"<module {name!r} (namespace) from {list(spec.loader._path)}>"
    if spec.has_location:
        return f"<module {name!r} from {spec.origin!r}>"
    return f"<module {spec.name!r} ({spec.origin})>"


def _make_virtual_module(name: str) -> types.ModuleType:
    """ماژول مجازی بدون __file__، مثل six.moves (بارگذار بدون _path)."""
    class _Loader:  # noqa: D401 — بارگذار ساختگی
        pass

    mod = types.ModuleType(name)
    mod.__spec__ = importlib.util.spec_from_loader(name, _Loader())
    return mod


# ---------------------------------------------------------------------------
# ۱) بازتولید ریشه‌ای باگ (کنترل) + اثبات رفع آن
# ---------------------------------------------------------------------------
def test_buggy_cpython_repr_reproduces_the_crash():
    """با repr نسخهٔ ۳.۱۲.۰، ماژول مجازی شبیه six.moves می‌شکند (کنترل)."""
    mod = _make_virtual_module("reportforge_probe_virtual")
    original = _bootstrap._module_repr_from_spec
    _bootstrap._module_repr_from_spec = _buggy_repr_from_spec
    try:
        with pytest.raises(AttributeError):
            repr(mod)
    finally:
        _bootstrap._module_repr_from_spec = original


def test_guard_makes_virtual_modules_repr_safe_under_buggy_cpython():
    """پس از محافظ، همان ماژول روی همان repr آسیب‌پذیر دیگر نمی‌شکند."""
    from app.utils.import_guard import _stub_module

    mod = _make_virtual_module("six._reportforge_probe_virtual")
    _stub_module(mod, "six.py")
    assert mod.__file__ == "six.py"
    assert mod.__spec__ is None

    original = _bootstrap._module_repr_from_spec
    _bootstrap._module_repr_from_spec = _buggy_repr_from_spec
    try:
        text = repr(mod)          # نباید AttributeError بدهد
    finally:
        _bootstrap._module_repr_from_spec = original
    assert "six._reportforge_probe_virtual" in text


def test_guard_detects_vulnerable_repr_by_behaviour():
    from app.utils import import_guard

    original = _bootstrap._module_repr_from_spec
    try:
        assert import_guard._repr_bug_active() is False
        _bootstrap._module_repr_from_spec = _buggy_repr_from_spec
        assert import_guard._repr_bug_active() is True
    finally:
        _bootstrap._module_repr_from_spec = original


# ---------------------------------------------------------------------------
# ۲) six.moves در محیط واقعی
# ---------------------------------------------------------------------------
def test_six_moves_is_stubbed_and_inspect_is_safe():
    import six
    import six.moves  # noqa: F401
    from app.utils.import_guard import protect_six_virtual_modules

    assert protect_six_virtual_modules() is True

    assert getattr(six.moves, "__file__", None)          # مسیر واقعی six.py
    assert six.moves.__spec__ is None                     # مسیر کرش بسته شده
    assert inspect.getfile(six.moves)                     # بدون TypeError
    assert inspect.getsource(six.moves) == ""             # بدون استثنا


def test_repr_six_moves_is_safe_even_with_buggy_cpython():
    import six.moves
    from app.utils.import_guard import protect_six_virtual_modules

    protect_six_virtual_modules()
    original = _bootstrap._module_repr_from_spec
    _bootstrap._module_repr_from_spec = _buggy_repr_from_spec
    try:
        assert "six.moves" in repr(six.moves)
    finally:
        _bootstrap._module_repr_from_spec = original


def test_late_six_submodules_are_stubbed_too():
    """زیرماژول‌هایی که بعداً import می‌شوند هم باید stub شوند."""
    import six.moves  # noqa: F401
    from app.utils.import_guard import protect_six_virtual_modules

    protect_six_virtual_modules()
    mod = sys.modules.get("six.moves.urllib") or importlib.import_module("six.moves.urllib")
    assert getattr(mod, "__file__", None)
    assert mod.__spec__ is None


# ---------------------------------------------------------------------------
# ۳) هوک Shiboken
# ---------------------------------------------------------------------------
def test_shiboken_feature_hook_is_neutralized(monkeypatch):
    from app.utils import import_guard

    calls: list[str] = []

    def _exploding_feature_imported(module, *args, **kwargs):
        calls.append(getattr(module, "__name__", "?"))
        raise AttributeError("'_SixMetaPathImporter' object has no attribute '_path'")

    fake_feature = types.ModuleType("shibokensupport.feature")
    fake_feature.feature_imported = _exploding_feature_imported
    fake_loader = types.ModuleType("shibokensupport.signature.loader")
    fake_loader.feature_imported = _exploding_feature_imported
    monkeypatch.setitem(sys.modules, "shibokensupport.feature", fake_feature)
    monkeypatch.setitem(sys.modules, "shibokensupport.signature.loader", fake_loader)

    assert import_guard.patch_shiboken_feature_hook() is True

    import six.moves  # noqa: F401

    # ماژول six: بی‌اثر (هیچ استثنایی)
    assert fake_feature.feature_imported(six.moves) is None
    # ماژول بدون فایل: بی‌اثر
    assert fake_feature.feature_imported(_make_virtual_module("reportforge_probe_virtual2")) is None
    # ماژول عادی: باید به تابع اصلی برسد
    with pytest.raises(AttributeError):
        fake_feature.feature_imported(importlib)


# ---------------------------------------------------------------------------
# ۴) فایل‌های بسته‌بندی (spec / rthook / build bat)
# ---------------------------------------------------------------------------
def test_spec_registers_the_runtime_hook():
    text = SPEC.read_text(encoding="utf-8")
    assert "runtime_hooks=['app/pyi_rth_reportforge.py']" in text
    assert RTHOOK.exists()


def test_spec_hides_six_virtual_modules_and_guard():
    text = SPEC.read_text(encoding="utf-8")
    for name in ("'six'", "'six.moves'", "'six.moves._thread'", "'app.utils.import_guard'"):
        assert name in text, name


def test_runtime_hook_is_ascii_and_stdlib_only():
    """rthook قبل از هر چیز اجرا می‌شود؛ باید ASCII و سبک باشد."""
    raw = RTHOOK.read_bytes()
    raw.decode("ascii")                       # اگر نبود: UnicodeDecodeError

    tree = ast.parse(raw.decode("ascii"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"sys", "types", "inspect", "importlib", "six"}
    assert imported <= allowed, imported - allowed


def test_build_bat_runs_the_self_check():
    text = (REPO / "build_exe.bat").read_text(encoding="utf-8")
    text.encode("ascii")                      # bat باید ASCII بماند
    assert "--smoke-test" in text
    assert "start /wait" in text


def test_guards_run_before_pyside_in_main():
    """ترتیب import قفل است: محافظ‌ها قبل از PySide6 و قبل از six.moves."""
    text = (REPO / "app" / "main.py").read_text(encoding="utf-8")
    pos_guard = text.index("apply_frozen_guards")
    pos_pyside = text.index("from PySide6.QtCore")
    pos_compat = text.index("from app import pyside_compat")
    assert pos_compat < pos_guard < pos_pyside

    compat = (REPO / "app" / "pyside_compat.py").read_text(encoding="utf-8")
    assert compat.index("apply_frozen_guards()") < compat.index("from six.moves import")


def test_package_init_applies_guards():
    from app import APP_VERSION

    text = (REPO / "app" / "__init__.py").read_text(encoding="utf-8")
    assert "apply_frozen_guards" in text
    assert f'APP_VERSION = "{APP_VERSION}"' in text      # نسخه یک‌جا از پکیج خوانده می‌شود


# ---------------------------------------------------------------------------
# ۵) آزمون خودکار شروع برنامه (--smoke-test)
# ---------------------------------------------------------------------------
def test_smoke_test_reports_ok(tmp_path, monkeypatch, qapp):
    from app.utils.selfcheck import run_smoke_test

    monkeypatch.chdir(tmp_path)               # گزارش در tmp نوشته شود، نه در مخزن
    code = run_smoke_test(["python", "--smoke-test"])
    assert code == 0

    report = (tmp_path / "ReportForge-smoke.txt").read_text(encoding="utf-8")
    assert "RESULT       : OK" in report
    assert "main window  : OK" in report
    assert "guard.post.inspect_guarded: True" in report
