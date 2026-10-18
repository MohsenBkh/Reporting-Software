# رفع کرش فایل اجرایی ReportForge (نسخه ۱.۱.۲)

## ۱) نشانهٔ ایراد

پس از اجرای `build_exe.bat` و تولید `dist\ReportForge.exe`، برنامه در ویندوز بلافاصله بسته می‌شد:

```
AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
```

## ۲) زنجیرهٔ کامل خطا (تصویر واقعی از exe)

```
reportforge.py:7                        from app.main import main
app\main.py:13                          from app import pyside_compat
app\pyside_compat.py:19                 from six.moves import _thread, range
shibokensupport\signature\loader.py:72  feature_imported
shibokensupport\feature.py:148          feature_imported
shibokensupport\feature.py:159          _mod_uses_pyside
inspect.py:1267 getsource → 1064 findsource
pyi_rth_inspect.py:64                   _pyi_getsourcefile
inspect.py:928 getfile
<frozen importlib._bootstrap>:545       _module_repr  ⇒  _module_repr_from_spec
    return f'<module {name!r} (namespace) from {list(spec.loader._path)}>'
AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
```

## ۳) علت ریشه‌ای

1. ماژول‌های مجازی `six` (`six.moves`, `six.moves._thread`, `six.moves.range`, …) با
   `spec_from_loader` ساخته می‌شوند: `spec.origin is None` و بارگذار آن‌ها
   `_SixMetaPathImporter` است که هیچ `_path` ندارد.
2. در **CPython 3.12.0–3.12.3** تابع `_module_repr_from_spec` در شعبهٔ `origin is None`
   بدون بررسی نوع بارگذار، `list(spec.loader._path)` را می‌سازد ⇒ `AttributeError`.
   این باگ در 3.12.4 و 3.13 رفع شده است (شعبهٔ جدید `isinstance(loader, NamespaceLoader)`).
3. در exe، هوک `pyi_rth_inspect` (PyInstaller) `inspect.getsourcefile` را طوری جایگزین
   می‌کند که برای ماژول بدون `__file__` به `inspect.getfile` می‌رسد؛ آن هم برای ساختن
   **پیام خطا** ماژول را repr می‌کند ⇒ باگ بند ۲ فعال می‌شود.
4. هوک Shiboken (PySide6) با اولین import پس از خود، برای هر ماژول تازه
   `feature_imported` → `_mod_uses_pyside` → `inspect.getsource` را صدا می‌زند.
   ترکیب این سه، exe را در اولین `from six.moves import …` می‌شکند
   (اجرای سورسی کرش نمی‌کند چون هوک‌های PyInstaller وجود ندارند).

## ۴) اصلاح پیاده‌شده (بدون نیاز به ارتقای Python)

| فایل | نقش |
|---|---|
| `app/pyi_rth_reportforge.py` | **Runtime Hook** — پیش از هر کد برنامه اجرا می‌شود |
| `app/utils/import_guard.py` | همان محافظ‌ها برای اجرای سورسی و idempotent |
| `app/__init__.py` | اجرای محافظ در اولین خط برنامه |
| `app/pyside_compat.py` | اجرای محافظ پیش از `from six.moves import …` |
| `app/main.py` | اجرای صریح محافظ پیش از PySide6 |
| `ReportForge.spec` | `runtime_hooks` + `hiddenimports` (six.moves*) + `excludes` |
| `app/utils/selfcheck.py` | `--smoke-test` برای تأیید سلامت شروع |
| `build_exe.bat` | اجرای خودکار خودآزمون پس از ساخت |

سه ضمانت:

1. **inspect امن**: `getfile/getsource/getsourcefile` برای ماژول‌های مجازی هیچ‌گاه
   استثنا یا `repr` خطرناک نمی‌سازند (`getsource` مقدار خالی می‌دهد).
2. **six بی‌خطر**: هر ماژول `six.*` که `__file__` ندارد مسیر واقعی `six.py` را می‌گیرد و
   اگر `spec.origin` تهی باشد، `__spec__` حذف می‌شود؛ پس `repr` هرگز به `loader._path`
   نمی‌رسد — روی **همهٔ** نسخه‌های Python، نه فقط 3.12.0–3.12.3.
3. **هوک Shiboken بی‌اثر**: `feature_imported` برای `six*` و ماژول‌های بی‌فایل
   `None` برمی‌گرداند و فایندرهای شبیه‌ساز از `sys.meta_path` برداشته می‌شوند.

## ۵) شواهد تأیید (در همین مخزن قابل تکرار)

* `tests/test_v112_exe_guard.py` — ۱۴ تست، از جمله:
  * نصب عین کد `_module_repr_from_spec` نسخهٔ 3.12.0 ⇒ بازتولید خطا، و پس از محافظ ⇒ سالم.
  * امن بودن `repr(six.moves)` و `inspect.getsource/getfile` روی همان repr آسیب‌پذیر.
  * ثبت Runtime Hook در spec، ASCII/سبک بودن فایل rthook، بی‌اثر شدن هوک Shiboken،
    ترتیب import محافظ‌ها و اجرای `--smoke-test`.
* `python -m app.main --smoke-test` ⇒ `RESULT: OK`.
* exe ساخته‌شده در محیط frozen با `--smoke-test` ⇒ `RESULT: OK`
  (همهٔ `guard.*` فعال، ساخت پنجرهٔ اصلی و اجرای حلقهٔ رویداد).
* کنترل: exe آزمایشی که فقط باگ CPython 3.12.0 را شبیه‌سازی می‌کند، **بدون** Runtime Hook
  عیناً همان traceback را می‌دهد و **با** Runtime Hook سالم است.
* کل مجموعه تست: **۱۵۲ تست موفق** + `tools/ui_check_study.py` بدون خطا.

## ۶) بازسازی و بررسی (کاربر، ویندوز)

```bat
rem ۱) ساخت exe
build_exe.bat

rem ۲) در پایان، خودآزمون خودکار اجرا می‌شود؛ برای بررسی دستی:
dist\ReportForge.exe --smoke-test
type dist\ReportForge-smoke.txt
```

در فایل گزارش باید خط `RESULT       : OK` دیده شود. اگر خطا داشت، همان فایل را ارسال کنید.

## ۷) اگر باز هم مشکلی بود

* Python را به 3.12.4+ یا 3.13 ارتقا دهید (باگ CPython در این نسخه‌ها رفع شده است).
* نسخهٔ اشکال‌زدایی با کنسول بسازید تا متن خطا دیده شود:
  `set REPORTFORGE_SPEC_CONSOLE=1 && build_exe.bat`
* مطمئن شوید ساخت با `python -m PyInstaller --clean --noconfirm ReportForge.spec` انجام شده
  است (پوشه‌های `build\` و `dist\` قبلی پاک می‌شوند).
