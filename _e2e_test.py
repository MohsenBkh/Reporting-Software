# -*- coding: utf-8 -*-
"""تست کامل End-to-End با پروفیل بار، نمودار و پیش‌بینی + بررسی ساختار DOCX."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from app.core import loading_profile as lp
from app.core import forecast as fc_mod
from app.core.models import (Feeder, ForecastPoint, PowerFlowResult, Project,
                             REQUEST_NEW)
from app.core.settings import AppSettings
from app.report import pipeline
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine

out = Path(__file__).resolve().parent / "_demo_out"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir()

settings = AppSettings()
project = Project(
    name="نیرورسانی ایستگاه پمپاژ آب شهرک شهید سلیمانی",
    report_number="DM-18-003", date_jalali="1405/06/21",
    applicant_name="ایستگاه پمپاژ آب شهرک شهید سلیمانی",
    request_type=REQUEST_NEW, requested_power_kw=1500,
    substation="اردبیل غربی", office="اردبیل", expert_name="مهندس بخشایی",
    location_note="موقعیت زمین پست در اراضی شامل‌آسبی به مختصات X=259094 و Y=4230283 ثبت گردیده است.",
    location_distance_m=50, cable_suggestion="آلومینیومی سایز 70",
)

# --- پروفیل بار چهارساله (ماهانه) ---
rows = []
import math
for y in (1402, 1403, 1404, 1405):
    for m in range(1, 13):
        base = 2.1 + 0.15 * (y - 1402) + 0.02 * m
        summer = 0.5 if m in (5, 6, 7) else 0.0
        p = round(min(base + summer, 2.75), 2)
        q = round(p * 0.4, 2)
        rows.append({"date": f"{y:04d}/{m:02d}/15", "feeder": "فیدر 2 اردبیل غربی",
                     "p_mw": p, "q_mvar": q})
df, errs = lp.parse_profile(pd.DataFrame(rows))
assert not errs, errs

f1 = Feeder(name="فیدر 2 اردبیل غربی", substation="اردبیل غربی",
            peak_year=1405, power_factor=0.93, peak_current_a=85,
            max_current_a=490, capacity_mw=7,
            before=PowerFlowResult(79, 64, 0.972, 0.992),
            after=PowerFlowResult(122, 93, 0.967, 0.986))
f1._profile_df = df
f1.profile_stats = lp.compute_stats(df)
years, values = lp.annual_peaks(df)
f1.peak_load_mw = f1.profile_stats.peak_p_mw
f1.forecast = fc_mod.linear_forecast(years, values, 5, 3)
project.feeders = [f1]

report, docx, items = pipeline.generate_report_full(
    project, settings, out / "charts", out, TemplateManager(), RuleEngine())
print("DOCX:", docx, "exists:", docx.exists())
print("Validation:", [(i.status, i.message[:40]) for i in items])

text = "\n".join(p.text for s in report.sections for p in s.paragraphs())
assert "{" not in text and "}" not in text
assert "TAV111-10/00" in text
assert "موقعیت" in text and "50" in text
assert "در محدوده مجاز" in text
assert "رگرسیون" in text

# --- بررسی ساختار DOCX ---
with zipfile.ZipFile(docx) as z:
    names = z.namelist()
    xml = z.read("word/document.xml").decode("utf-8")
    n_media = sum(1 for n in names if n.startswith("word/media/"))

print("bidi paragraphs:", xml.count("<w:bidi/>"))
print("rtl runs:", xml.count("<w:rtl/>"))
print("bidiVisual tables:", xml.count("bidiVisual"))
print("TOC field:", "TOC" in xml)
print("PAGE field:", " PAGE " in xml)
print("images in docx:", n_media)
print("cs font refs:", xml.count('w:cs="B Nazanin"') + xml.count('w:cs="B Titr"'))
assert n_media >= 2, "نمودارها داخل docx نیستند"
assert xml.count("<w:bidi/>") > 20
assert xml.count("bidiVisual") >= 1
print("charts on disk:", list((out / "charts").glob("*.png")))
print("E2E OK ✔")
