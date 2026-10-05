# -*- coding: utf-8 -*-
"""محافظهای ورود ماژول (Import-Guard) — رفع کرش برنامه در حالت Frozen (exe).

پیشینهٔ خطا (ReportForge v1.1.2)
--------------------------------
در نسخه‌های **Python 3.12.0 تا 3.12.3**، تابع `_module_repr_from_spec` در
`importlib._bootstrap` برای هر ماژولی که `__spec__.origin is None` باشد مستقیماً
`spec.loader._path` را می‌خواند:

    return f'<module {name!r} (namespace) from {list(spec.loader._path)}>'

ماژول‌های «مجازی» بستهٔ ``six`` (مانند ``six.moves`` و ``six.moves._thread``) با
`spec_from_loader` ساخته می‌شوند و origin ندارند؛ بارگذار آن‌ها
`_SixMetaPathImporter` است که `_path` ندارد. نتیجه: هر `repr()` روی این ماژول‌ها
با خطای زیر می‌شکند:

    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'

در exe ساخته‌شده با PyInstaller، hook آمادهٔ `pyi_rth_inspect` تابع
`inspect.getsourcefile` را طوری عوض می‌کند که برای ماژول بدون `__file__`
به `inspect.getfile` می‌رود؛ آن هم برای ساختن پیام خطا ماژول را repr می‌کند و
باگ بالا فعال می‌شود. Import-Hook خود Shiboken (PySide6) از همین مسیر
`inspect.getsource` را روی ماژول‌های six صدا می‌زند و کل برنامه در شروع کرش می‌کند.

راهکار (سه لایه، بی‌نیاز از ارتقای Python)
-----------------------------------------
1. ``patch_inspect()`` — `getfile`/`getsource`/`getsourcefile` برای ماژول‌های
   بی‌فایل (virtual) رفتار تمیز دارند و هیچ‌وقت repr نمی‌سازند.
2. ``protect_six_virtual_modules()`` — به ماژول‌های مجازی six یک `__file__` واقعی
   نسبت داده می‌شود (و روی Python 3.12.0–3.12.3 مقدار `__spec__` پاک می‌شود) تا
   از پایه هیچ مسیر کرشی باقی نماند.
3. ``patch_shiboken_feature_hook()`` — هوک Shiboken برای ماژول‌های six و ماژول‌های
   بی‌فایل بی‌اثر می‌شود (سازگار با همهٔ نسخه‌های PySide6).

این ماژول فقط به کتابخانهٔ استاندارد وابسته است تا هم در اجرای عادی و هم در
*Runtime Hook* فایل اجرایی (``pyi_rth_reportforge.py``) بی‌خطر قابل استفاده باشد.
"""
from __future__ import annotations

import sys
import types
from typing import Any

# ---------------------------------------------------------------------------
# Python 3.12.0–3.12.3 درگیر باگ repr ماژول‌های virtual است
# ---------------------------------------------------------------------------
_AFFECTED_PY312 = ((3, 12, 0), (3, 12, 4))


def _repr_bug_active() -> bool:
    """آیا `_module_repr_from_spec` جاری، ماژول بدون `_path` را می‌شکند؟

    به‌جای حدس از شمارهٔ نسخه، رفتار واقعی تابع تست می‌شود (هم باگ CPython
    3.12.0–3.12.3 را می‌گیرد، هم هر پیاده‌سازی وصله‌شده/شبیه‌سازی‌شدهٔ دیگری را).
    """
    try:
        import importlib._bootstrap as _bootstrap
        repr_from_spec = getattr(_bootstrap, "_module_repr_from_spec", None)
        if repr_from_spec is None:
            return False

        class _Loader:            # بارگذار بدون _path (مثل _SixMetaPathImporter)
            pass

        class _Spec:
            name = "reportforge._probe"
            origin = None
            loader = None
            has_location = False

        spec = _Spec()
        spec.loader = _Loader()
        repr_from_spec(spec)      # نسخهٔ آسیب‌پذیر: AttributeError
        return False
    except AttributeError:
        return True
    except Exception:  # noqa: BLE001
        return False


def _version_sniff_bug() -> bool:
    """تشخیص با شمارهٔ نسخه (۳.۱۲.۰ تا ۳.۱۲.۳) — مکمل تست رفتاری."""
    version = sys.version_info[:3]
    if sys.version_info[:2] != (3, 12):
        return False
    return _AFFECTED_PY312[0] <= version < _AFFECTED_PY312[1]


def requires_python_upgrade() -> bool:
    """نسخه‌های ۳.۱۲.۰–۳.۱۲.۳ باگ شناخته‌شدهٔ CPython دارند (gh-113526-area).

    کد این ماژول کرش را در ReportForge رفع می‌کند، اما توصیه می‌شود برای ساخت
    exe از Python 3.12.4+ یا 3.13 استفاده شود.
    """
    return _repr_bug_active() or _version_sniff_bug()


def shiboken_hook_is_patched() -> bool:
    """آیا هوک shiboken در همین لحظه بی‌اثر است؟"""
    for mod_name in ("shibokensupport.feature", "shibokensupport.signature.loader"):
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        current = getattr(mod, "feature_imported", None)
        if current is not None and getattr(current, "_reportforge_patched", False):
            return True
    return bool(getattr(sys, "_reportforge_shiboken_patched", False))


def frozen_guard_report() -> dict:
    """گزارش وضعیت محافظ‌ها (برای ``ReportForge.exe --smoke-test``)."""
    try:
        from app import __name__ as _  # noqa: F401
        app_version = getattr(__import__("app"), "APP_VERSION", "-")
    except Exception:  # noqa: BLE001
        app_version = "-"
    return {
        "python_312_bug": _version_sniff_bug(),
        "repr_vulnerable": _repr_bug_active(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "six_stubbed": getattr(sys, "_reportforge_six_stubbed", False),
        "inspect_guarded": bool(getattr(__import__("inspect"), "_reportforge_guarded", False)),
        "shiboken_loaded": any(n.startswith("shibokensupport") or n.startswith("shiboken6")
                               for n in sys.modules),
        "shiboken_patched": shiboken_hook_is_patched(),
    }


# ---------------------------------------------------------------------------
# ۱) محافظ inspect
# ---------------------------------------------------------------------------
def patch_inspect() -> None:
    """`inspect` را برای ماژول‌های بدون فایل امن می‌کند (فقط ماژول‌ها، بدون دست‌کاری بقیه)."""
    import inspect

    if getattr(inspect, "_reportforge_guarded", False):
        return

    orig_getfile = inspect.getfile

    def safe_getfile(obj: Any) -> str:
        if isinstance(obj, types.ModuleType) and not getattr(obj, "__file__", None):
            # پیام خطا بدون repr ماژول ساخته می‌شود (مسیر باگ Python 3.12.0)
            raise TypeError(
                f"module {getattr(obj, '__name__', '?')!s} has no source file (virtual module)")
        return orig_getfile(obj)

    orig_getsource = inspect.getsource

    def safe_getsource(obj: Any) -> str:
        if isinstance(obj, types.ModuleType):
            name = getattr(obj, "__name__", "") or ""
            if name == "six" or name.startswith("six."):
                return ""        # shiboken هنگام import شش، منبع آن را می‌پرسد
            if not getattr(obj, "__file__", None):
                return ""
        try:
            return orig_getsource(obj)
        except (OSError, TypeError, AttributeError):
            return ""            # ماژول فریز/بسته‌بندی‌شده منبع خواندنی روی دیسک ندارد

    orig_getsourcefile = inspect.getsourcefile

    def safe_getsourcefile(obj: Any) -> Any:
        try:
            return orig_getsourcefile(obj)
        except TypeError:
            return None
        except AttributeError:
            # مسیر دقیق باگ Python 3.12.0 روی ماژول‌های six
            return None
        except Exception:  # noqa: BLE001 — inspect نباید برنامه را بشکند
            return None

    inspect.getfile = safe_getfile
    inspect.getsource = safe_getsource
    inspect.getsourcefile = safe_getsourcefile
    inspect._reportforge_guarded = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ۲) ماژول‌های مجازی six
# ---------------------------------------------------------------------------
def _stub_module(mod: Any, six_file: str) -> None:
    """ماژول مجازی six را بی‌خطر می‌کند.

    ۱) اگر ``__file__`` ندارد، مسیر فایل خود six داده می‌شود تا
       ``inspect.getfile`` به TypeError («built-in module») نخورد.
    ۲) اگر spec آن ``origin is None`` دارد (همان شعبهٔ خطرناک
       ``_module_repr_from_spec``)، ``__spec__`` پاک می‌شود تا هیچ repr‌ای
       به ``loader._path`` نرسد — روی هر نسخه‌ای از Python.
    """
    if not isinstance(mod, types.ModuleType):
        return
    mod_name = getattr(mod, "__name__", "") or ""
    if not (mod_name == "six" or mod_name.startswith("six.")):
        return  # فقط ماژول‌های خودِ six؛ ماژول‌های واقعی (alias) دست‌کاری نمی‌شوند
    if not getattr(mod, "__file__", None):
        try:
            mod.__file__ = six_file
        except Exception:  # noqa: BLE001
            pass
    spec = getattr(mod, "__spec__", None)
    if spec is not None and getattr(spec, "origin", None) is None:
        try:
            mod.__spec__ = None
        except Exception:  # noqa: BLE001
            pass


def _patch_six_importer(six_module: Any) -> None:
    """ماژول‌های six که بعداً import شوند هم `__file__` بگیرند."""
    cls = getattr(six_module, "_SixMetaPathImporter", None)
    if cls is None or getattr(cls, "_reportforge_patched", False):
        return
    six_file = getattr(six_module, "__file__", "") or ""

    # create_module/load_module «قبل» از _init_module_attrs اجرا می‌شوند و
    # exec_module «بعد» از آن؛ پس هر سه را می‌گیریم تا spec تازه دوباره نچسبد.
    for method_name in ("create_module", "load_module", "exec_module"):
        orig = getattr(cls, method_name, None)
        if orig is None or not callable(orig):
            continue

        def wrapper(self, *args, __orig=orig, **kwargs):  # noqa: ANN001
            result = __orig(self, *args, **kwargs)
            # exec_module(module) ماژول را در آرگومان می‌دهد؛ create/load آن را
            # برمی‌گردانند — هر دو حالت پوشش داده می‌شود
            for candidate in (result,) + tuple(args):
                _stub_module(candidate, six_file)
            return result

        wrapper._reportforge_patched = True  # type: ignore[attr-defined]
        setattr(cls, method_name, wrapper)
    cls._reportforge_patched = True  # type: ignore[attr-defined]


def protect_six_virtual_modules() -> bool:
    """six و زیرماژول‌های مجازی‌اش را import و بی‌خطر می‌کند. خروجی: موفقیت."""
    try:
        import six  # noqa: F401
        import six.moves  # noqa: F401
        from six.moves import _thread, range  # noqa: F401
        if sys.platform == "win32":
            from six.moves import winreg  # noqa: F401
    except Exception:  # noqa: BLE001 — نبود six نباید برنامه را متوقف کند
        return False

    six_file = getattr(six, "__file__", "") or ""
    for name, mod in list(sys.modules.items()):
        if name == "six" or name.startswith("six."):
            _stub_module(mod, six_file)
    _patch_six_importer(six)
    sys._reportforge_six_stubbed = True  # type: ignore[attr-defined]
    return True


# ---------------------------------------------------------------------------
# ۳) هوک Shiboken (PySide6)
# ---------------------------------------------------------------------------
def _skip_module(module: Any) -> bool:
    name = getattr(module, "__name__", "") or ""
    if name == "six" or name.startswith("six."):
        return True
    # هر ماژول بدون فایل: بررسی منبع روی آن معنا ندارد و در ۳.۱۲.۰–۳.۱۲.۳ کرش می‌کند
    return not getattr(module, "__file__", None)


def patch_shiboken_feature_hook() -> bool:
    """`feature_imported` شبیه‌کنندهٔ Shiboken را برای ماژول‌های six/بی‌فایل بی‌اثر می‌کند."""
    patched = False
    for mod_name in ("shibokensupport.feature", "shibokensupport.signature.loader"):
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        orig = getattr(mod, "feature_imported", None)
        if orig is None or getattr(orig, "_reportforge_patched", False):
            continue

        def safe_feature_imported(module, *args, __orig=orig, **kwargs):  # noqa: ANN001
            if _skip_module(module):
                return None
            return __orig(module, *args, **kwargs)

        safe_feature_imported._reportforge_patched = True  # type: ignore[attr-defined]
        mod.feature_imported = safe_feature_imported
        patched = True

    # در صورت نیاز، فایندرهای Shiboken از sys.meta_path برداشته می‌شوند
    for finder in list(sys.meta_path):
        cls = type(finder)
        module_name = getattr(cls, "__module__", "") or ""
        if module_name.startswith("shibokensupport") or module_name == "shiboken6.feature":
            try:
                sys.meta_path.remove(finder)
            except ValueError:
                pass
            patched = True
    return patched


# ---------------------------------------------------------------------------
def apply_frozen_guards() -> dict:
    """اجرای هر سه لایه محافظ (idempotent و بی‌خطر برای فراخوانی از Runtime Hook)."""
    result = {"inspect": False, "six": False, "shiboken": False,
              "python_312_bug": _repr_bug_active()}
    try:
        patch_inspect()
        result["inspect"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        result["six"] = protect_six_virtual_modules()
    except Exception:  # noqa: BLE001
        pass
    try:
        result["shiboken"] = patch_shiboken_feature_hook()
        if result["shiboken"]:
            sys._reportforge_shiboken_patched = True  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return result
