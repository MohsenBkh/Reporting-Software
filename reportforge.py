# -*- coding: utf-8 -*-
"""نقطه ورود ساخت فایل اجرایی (PyInstaller) — همان مسیر اجرای python -m app.main."""
from __future__ import annotations

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
