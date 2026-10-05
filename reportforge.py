# -*- coding: utf-8 -*-
"""نقطه ورود ساخت فایل اجرایی (PyInstaller) — همان مسیر اجرای python -m app.main."""
from __future__ import annotations

import sys

from app.main import main


def _cli() -> int:
    """اجرای برنامه؛ با پرچم ``--smoke-test`` فقط سلامتی بالا آمدن بررسی می‌شود.

        ReportForge.exe --smoke-test
    """
    if "--smoke-test" in sys.argv[1:] or "--self-check" in sys.argv[1:]:
        from app.utils.selfcheck import run_smoke_test
        return run_smoke_test()
    return main()


if __name__ == "__main__":
    sys.exit(_cli())
