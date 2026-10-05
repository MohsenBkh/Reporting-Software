# -*- coding: utf-8 -*-
"""ساخت نمونهٔ کامل نسخه ۱.۲.۰ — «پروژهٔ نمونه» + «گزارش نمونهٔ Word».

اجرا از ریشهٔ مخزن:

    python tools/build_demo.py                 # خروجی در ../demo و ../demo-project
    python tools/build_demo.py --out D:/demo   # مسیر دلخواه

خروجی‌ها:

* ``demo-project/پروژه_نمونه_مطالعه/``  — پروژهٔ واقعی (project.json + پوشه‌های projects/images/output)
* ``demo/مطالعه تأمین برق متقاضی نمونه.docx`` — گزارش Word تولیدشده از همین پروژه

نمونه شامل دو فیدر است تا **هر دو باند** اصلاح v1.2.0 در گزارش دیده شود:

* فیدر ۴۱۵ فاز ۵ — پیک ۶٫۵ MW + بار جدید ۱٫۲ MW = ۷٫۷ MW ⇒ «بارگذاری بحرانی» (≥ ۷)
* فیدر ۴۲۰ فاز ۳ — پیک ۷٫۲ MW + بار جدید ۱٫۲ MW = ۸٫۴ MW ⇒ «شدیداً بحرانی» (≥ ۸)

فیدرهای همجوار (کاندید بازآرایی) برای هر دو فیدر ثبت می‌شوند تا Rule
``LD-REARRANGE-PROPOSAL`` و سناریوی «بازآرایی فیدر» هم در گزارش بیایند.
یک ردیف ایستگاه نیز عمداً **خاموش (On/Off)** است تا رفتار حذف ورودی ناخواسته
از گزارش در پروژهٔ نمونه قابل مشاهده باشد.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.core import scenarios as scenario_mod                        # noqa: E402
from app.core.models import ForecastPoint, NeighborFeeder, ProjectImage  # noqa: E402
from app.core.project_manager import ProjectManager                   # noqa: E402
from app.core.settings import AppSettings, CostSettings               # noqa: E402
from app.report.pipeline import generate_report_full                  # noqa: E402
from app.rules.rule_engine import RuleEngine                          # noqa: E402
from sample_projects import make_feeder, make_study_project           # noqa: E402

PROJECT_DIR_NAME = "پروژه_نمونه_مطالعه"


def build_settings() -> AppSettings:
    """تنظیمات نمونه — پارامترهای هزینهٔ نمونه (کاربر مقادیر خودش را وارد می‌کند)."""
    return AppSettings(
        include_appendices=True,
        costs=CostSettings(overhead_per_km_million=2000.0,
                           underground_per_km_million=4000.0,
                           ground_substation_million=600.0,
                           switchgear_million=150.0,
                           protection_million=90.0))


def build_project(settings: AppSettings):
    """پروژهٔ نمونه با داده‌های مطالعه، دو فیدر و فیدرهای همجوار."""
    from app.core import forecast as fc_mod

    project = make_study_project()
    project.existing_power_kw = 1000.0
    project.demand.existing_demand_kw = 1000.0

    # --- فیدر ۱: باند «بحرانی» (۷٫۷ MW)
    f1 = make_feeder(name="فیدر ۴۱۵ فاز ۵")
    f1.peak_load_mw = 6.5
    f1.capacity_mw = 10.0
    f1.annual_peaks = [ForecastPoint(year=y, value_mw=v, source="MANUAL")
                       for y, v in ((1399, 2.1), (1400, 2.25), (1401, 2.4),
                                    (1402, 2.52), (1403, 2.75))]
    f1.forecast = fc_mod.linear_forecast([p.year for p in f1.annual_peaks],
                                         [p.value_mw for p in f1.annual_peaks], 5, 3,
                                         th=settings.thresholds)

    # --- فیدر ۲: باند «شدیداً بحرانی» (۸٫۴ MW)
    f2 = make_feeder(name="فیدر ۴۲۰ فاز ۳")
    f2.peak_load_mw = 7.2
    f2.capacity_mw = 10.0
    f2.annual_peaks = [ForecastPoint(year=y, value_mw=v, source="MANUAL")
                       for y, v in ((1399, 4.1), (1400, 4.35), (1401, 4.6),
                                    (1402, 4.92), (1403, 5.2))]
    f2.forecast = fc_mod.linear_forecast([p.year for p in f2.annual_peaks],
                                         [p.value_mw for p in f2.annual_peaks], 5, 3,
                                         th=settings.thresholds)
    project.feeders = [f1, f2]

    # --- فیدرهای همجوار (کاندید بازآرایی) با فاصلهٔ ثبت‌شده
    project.neighbor_feeders = [
        NeighborFeeder(name="فیدر ۴۱۶ فاز ۲", office="امور برق مرکزی", substation="پست ۲",
                       peak_load_mw=3.2, capacity_mw=8.0, peak_current_a=95,
                       max_current_a=400, distance_km=1.4, transferable_mw=1.5,
                       note="کاندید بازآرایی بر اساس کمترین فاصلهٔ ثبت‌شده"),
        NeighborFeeder(name="فیدر ۴۱۸ فاز ۱", office="امور برق مرکزی", substation="پست ۳",
                       peak_load_mw=5.4, capacity_mw=8.0, peak_current_a=150,
                       max_current_a=400, distance_km=3.1, transferable_mw=1.0,
                       note="گزینهٔ دوم (فاصلهٔ بیشتر)"),
    ]

    # --- نمونهٔ ورودی خاموش: ردیف ناخواسته که در گزارش نمی‌آید (ولی داده‌اش می‌ماند)
    from app.core.models import SubstationCandidate
    project.nearby_substations.append(
        SubstationCandidate(name="ایستگاه پیشنهادی (خارج از محدودهٔ مطالعه)",
                            distance_km=12.0, transformer_capacity_mva=25.0,
                            enabled=False))

    # --- سناریوها
    scenario_mod.ensure_scenarios(project, settings, RuleEngine(), regenerate=True)
    for sc in project.scenarios:
        if sc.kind == "new_feeder":
            sc.required_line_length_km = 2.0
            sc.overhead_percent = 90.0
            sc.underground_percent = 10.0
            sc.estimated_cost_million = 5130.0
            sc.cost_excluded_items = ["هزینه کلید ایستگاه", "احداث پست زمینی"]
        else:
            sc.estimated_cost_million = 0.0        # مطابق نمونهٔ مرجع: هزینهٔ صفر بدون مبنا
    return project


def _diagram_png(path: Path, title: str, feeder_label: str, load_mw: float) -> None:
    """شکل سادهٔ تک‌خطی فیدر (نمونه) برای بخش تصاویر — بدون وابستگی به فونت خاص."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=110)
    ax.plot([0.05, 0.35], [0.5, 0.5], lw=2.4, color="#1f3b73")
    ax.plot([0.5, 0.95], [0.5, 0.5], lw=2.4, color="#1f3b73")
    for cx in (0.42, 0.5, 0.58):
        ax.plot([cx, cx], [0.46, 0.54], lw=2.0, color="#1f3b73")
    ax.add_patch(plt.Rectangle((0.05, 0.38), 0.16, 0.24, fill=False, lw=1.6))
    ax.text(0.13, 0.50, feeder_label, ha="center", va="center", fontsize=9)
    ax.text(0.50, 0.62, f"P = {load_mw:g} MW", ha="center", va="bottom", fontsize=9)
    ax.text(0.5, 0.16, title, ha="center", va="center", fontsize=10)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_images(project_root: Path, project) -> None:
    """دو شکل نمونه با محل درج/اولویت/کپشن مستقل (ویژگی جدید بخش تصاویر)."""
    images_dir = project_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    made = [
        ("demo-before.png", "قبل از اتصال بار جدید", "فیدر ۴۱۵", 6.5, "before", 10,
         "شکل — وضعیت فیدر ۴۱۵ پیش از اتصال بار جدید متقاضی (پیک ۶٫۵ مگاوات)."),
        ("demo-loading.png", "پس از اتصال بار جدید", "فیدر ۴۱۵", 7.7, "study_loading", 20,
         "شکل — بارگذاری کل فیدر ۴۱۵ پس از افزودن بار جدید (۷٫۷ مگاوات: بارگذاری بحرانی)."),
    ]
    for name, title, label, load, section, order, caption in made:
        _diagram_png(images_dir / name, title, label, load)
        project.images.append(ProjectImage(file_name=name, title=title,
                                           kind="network" if section == "study_loading" else "before",
                                           section_key=section, order=order, caption=caption))
    # شکل خاموش: نمونهٔ حذف یک شکل از گزارش بدون پاک‌کردن داده
    project.images.append(ProjectImage(file_name="demo-before.png",
                                       title="شکل نمونهٔ غیرفعال (On/Off)",
                                       kind="other", section_key="before", order=99,
                                       caption="این شکل به‌صورت نمونه غیرفعال شده است.",
                                       enabled=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ساخت نمونهٔ نسخه ۱.۲.۰")
    ap.add_argument("--out", default=str(ROOT.parent), help="پوشهٔ والد خروجی")
    args = ap.parse_args(argv)
    out_root = Path(args.out)
    demo_dir = out_root / "demo"
    project_root = out_root / "demo-project"

    settings = build_settings()
    project = build_project(settings)

    # ۱) ذخیرهٔ پروژهٔ واقعی (تا کاربر بتواند آن را در برنامه باز کند)
    manager = ProjectManager(settings)
    manager.new_project(project_root / PROJECT_DIR_NAME, project)
    manager.save()

    # ۱-ب) شکل‌های نمونه با «بخش گزارش / اولویت / کپشن مستقل» + یک شکل غیرفعال (On/Off)
    build_images(manager.project_dir, project)
    manager.save()

    # ۲) تولید گزارش Word از همان پروژه
    (demo_dir / "charts").mkdir(parents=True, exist_ok=True)
    report, docx, items = generate_report_full(
        project, settings, demo_dir / "charts", demo_dir,
        engine=RuleEngine(), image_resolver=manager.image_path)

    print(f"پروژه : {manager.project_dir}")
    print(f"گزارش : {docx}  ({docx.stat().st_size / 1024:.0f} کیلوبایت)")
    print("بخش‌ها:", " | ".join(s.key for s in report.sections))
    print(f"جدول‌ها: {sum(1 for s in report.sections for b in s.blocks if type(b).__name__ == 'TableSpec')}"
          f" | شکل‌ها: {sum(1 for s in report.sections for b in s.blocks if type(b).__name__ == 'FigureBlock')}"
          f" | Findings: {len(report.findings)}")
    warnings = [i for i in items if i.status == "error"]
    print(f"خطاهای اعتبارسنجی: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
