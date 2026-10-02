# -*- coding: utf-8 -*-
"""بررسی دسترسی به سند مرجع PDF."""
import importlib
import sys
from pathlib import Path

pdf = Path(r"D:\My apps\Report Generator\chatbox_fixed_v1_0_3-1\نمونه مطالعه متقاضی سنگین.pdf")
print("exists:", pdf.exists(), "| size:", pdf.stat().st_size if pdf.exists() else 0)

for m in ("pypdf", "PyPDF2", "pdfminer", "fitz", "pdfplumber"):
    try:
        importlib.import_module(m)
        print(m, "OK")
    except ImportError:
        print(m, "--")
