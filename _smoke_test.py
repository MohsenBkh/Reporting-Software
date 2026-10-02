# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.models import Project, Feeder, PowerFlowResult, REQUEST_INCREASE
from app.core.settings import AppSettings
from app.rules.rule_engine import RuleEngine, safe_eval_bool
from app.report.template_manager import TemplateManager
from app.report import pipeline

print('imports OK')
e = RuleEngine()
print('rules:', len(e.rules))
t = TemplateManager()
print('texts:', len(t.entries))
s = AppSettings()
print('settings:', s.company_name[:25], s.thresholds.voltage_min_pu)
print('eval true:', safe_eval_bool('a > 1 and b == 2', {'a': 3, 'b': 2}))
print('eval unsafe:', safe_eval_bool('__import__("os")', {}))

# --- ساخت پروژه تست (سناریوی ناب پروتئین) ---
p = Project(
    name="افزایش قدرت ناب پروتئین مهر",
    report_number="DM-18-001", date_jalali="1405/06/15",
    applicant_name="شرکت تأمین تولید و توزیع ناب پروتئین مهر",
    request_type=REQUEST_INCREASE,
    existing_power_kw=1000, requested_power_kw=1100,
    substation="کمی‌آباد", office="اردبیل", expert_name="کارشناس تست",
)
f1 = Feeder(name="فیدر 1 اردبیل", peak_load_mw=6.3, peak_year=1404, power_factor=0.89,
            peak_current_a=204, max_current_a=630, capacity_mw=7,
            before=PowerFlowResult(201, 452, 0.835, 0.956),
            after=PowerFlowResult(204, 459, 0.835, 0.954))
f2 = Feeder(name="فیدر 2 اردبیل", peak_load_mw=6.1, peak_year=1404, power_factor=0.89,
            peak_current_a=200, max_current_a=630, capacity_mw=7,
            before=PowerFlowResult(205, 687, 0.847),
            after=PowerFlowResult(205, 687, 0.847))
p.feeders = [f1, f2]

out = Path(r"D:\My apps\Report Generator\new\_smoke_out")
report, docx, items = pipeline.generate_report_full(
    p, s, out / "charts", out, t, e)
print('docx:', docx, docx.exists())
for it in items:
    print(' V', it.status, it.message[:60])
# بررسی متن‌های کلیدی
all_text = "\n".join(par.text for sec in report.sections for par in sec.paragraphs())
print('has intro:', 'TAV111-10/00' in all_text)
print('has preexisting (فیدر1):', 'خارج از محدوده مجاز' in all_text)
print('no leftover braces:', '{' not in all_text and '}' not in all_text)
print('sections:', [sec.title[:30] for sec in report.sections])
