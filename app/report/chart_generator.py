# -*- coding: utf-8 -*-
"""مولد نمودار — پروفیل بار، پیش‌بینی و منحنی جریان–زمان (TCC) با متن فارسی (matplotlib)."""
from __future__ import annotations

from pathlib import Path

from app.core.tcc import RelayCurve

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

try:
    import arabic_reshaper
    from bidi.get_display import get_display

    def rtl(text: str) -> str:
        return get_display(arabic_reshaper.reshape(str(text)))
except Exception:  # pragma: no cover — اگر کتابخانه‌ها نبودند
    def rtl(text: str) -> str:
        return str(text)

_FONT_READY = False


def _setup_font() -> None:
    """فونت فارسی موجود در ویندوز را به matplotlib معرفی می‌کند."""
    global _FONT_READY
    if _FONT_READY:
        return
    candidates = [
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/TAHOMA.TTF"),
        Path("C:/Windows/Fonts/Segoe UI.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for p in candidates:
        if p.exists():
            try:
                font_manager.fontManager.addfont(str(p))
                name = font_manager.FontProperties(fname=str(p)).get_name()
                matplotlib.rcParams["font.family"] = name
                break
            except Exception:  # noqa: BLE001
                continue
    matplotlib.rcParams["axes.unicode_minus"] = False
    _FONT_READY = True


PALETTE = {"P": "#1F4E79", "Q": "#C00000", "hist": "#1F4E79",
           "fit": "#C00000", "fc": "#E36C0A"}


def profile_chart(df, feeder_name: str, out_path: str | Path) -> Path | None:
    """نمودار تغییرات پیک توان اکتیو و راکتیو فیدر در طول یک سال (شکل ۲/۳ نمونه‌ها)."""
    if df is None or df.empty or "p_mw" not in df.columns:
        return None
    _setup_font()
    d = df.reset_index(drop=True)
    x = range(len(d))
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=150)

    ax.plot(x, d["p_mw"], color=PALETTE["P"], linewidth=1.6,
            label=rtl("توان اکتیو (P)"))
    if "q_mvar" in d.columns and d["q_mvar"].notna().any():
        ax.plot(x, d["q_mvar"], color=PALETTE["Q"], linewidth=1.2, linestyle="--",
                label=rtl("توان راکتیو (Q)"))

    dates = d["date"].astype(str).tolist()
    n = len(dates)
    step = max(1, n // 8)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([dates[i] for i in ticks], rotation=30, fontsize=7)
    ax.set_ylabel(rtl("مگاوات (MW)"), fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    out_path = Path(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def forecast_chart(history_years: list[int], history_values: list[float],
                   points, out_path: str | Path) -> Path | None:
    """منحنی پیش‌بینی پیک بار در افق ۵ ساله (شکل ۳/۴/۵ نمونه‌ها)."""
    _setup_font()
    if not history_years and not points:
        return None
    fig, ax = plt.subplots(figsize=(8.2, 3.8), dpi=150)

    if history_years:
        ax.plot(history_years, history_values, "o", color=PALETTE["hist"],
                markersize=5, label=rtl("پیک تاریخی"))
        if len(history_years) >= 2:
            ax.plot(history_years, history_values, "-", color=PALETTE["hist"],
                    linewidth=1.0, alpha=0.6)

    if points:
        xs = [p.year for p in points]
        ys = [p.value_mw for p in points]
        all_x = history_years[-1:] + xs if history_years else xs
        all_y = history_values[-1:] + ys if history_values else ys
        ax.plot(all_x, all_y, "--s", color=PALETTE["fc"], markersize=5,
                linewidth=1.4, label=rtl("پیش‌بینی"))
        for xx, yy in zip(xs, ys):
            ax.annotate(f"{yy:g}", (xx, yy), textcoords="offset points",
                        xytext=(0, 6), fontsize=7, ha="center")

    ax.set_xlabel(rtl("سال"), fontsize=9)
    ax.set_ylabel(rtl("مگاوات (MW)"), fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path = Path(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# منحنی جریان–زمان (TCC) رله‌های جریانی — شکل‌های ۳ و ۴ دفترچه نمونه فیدر ۴ خلخال
# ---------------------------------------------------------------------------
TCC_COLORS = ["#1F4E79", "#C00000", "#2E7D32", "#E36C0A", "#6A1B9A", "#00838F"]


def tcc_chart(curves: list[RelayCurve], out_path: str | Path, title: str = "",
              i_min_a: float | None = None, i_max_a: float | None = None,
              fault_markers: dict[str, float] | None = None) -> Path | None:
    """نمودار جریان–زمان (log–log) توابع جریانی تجهیزات (رله سر خط، ریکلوزر، سکشنالایزر).

    * توابع تأخیری (۵۱/۵۱N) با منحنی معکوس IEC (NI/VI/EI) و TMS درصد رسم می‌شوند.
    * توابع آنی (۵۰/۵۰N) به‌صورت پله (خط افقی از Pickup به بعد) رسم می‌شوند.
    * ``fault_markers``: خطوط عمودی مرجع (مثلاً حداقل/حداکثر جریان اتصال کوتاه).
    """
    curves = [c for c in (curves or []) if c is not None and c.pickup_a > 0]
    if not curves:
        return None
    _setup_font()

    pickups = [c.pickup_a for c in curves]
    lo = min(pickups) * 1.05
    hi = max([p * 10 for p in pickups]
             + [v * 2.0 for v in (fault_markers or {}).values()]
             + ([i_max_a * 1.5] if i_max_a else []))
    hi = max(hi, lo * 20)
    if i_min_a:
        lo = min(lo, i_min_a * 0.8)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=150)
    n_pts = 400
    import numpy as np
    xs = np.logspace(np.log10(lo), np.log10(hi), n_pts)
    for idx, c in enumerate(curves):
        color = TCC_COLORS[idx % len(TCC_COLORS)]
        label = rtl(f"{c.device} — {c.function}")
        if c.is_inverse:
            ys = [c.time_at(float(x)) for x in xs]
            pts = [(x, y) for x, y in zip(xs, ys) if y is not None and y <= 1000]
            if not pts:
                continue
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                    linewidth=1.7, label=label + rtl(f" ({c.curve})"))
        else:
            t = max(c.fixed_time_s or 0.0, 0.01)       # صفر در محور لگاریتمی رسم نمی‌شود
            ax.plot([c.pickup_a, hi], [t, t], color=color, linewidth=1.5,
                    linestyle="--", label=label)
            ax.plot([c.pickup_a, c.pickup_a], [t, 1000], color=color,
                    linewidth=1.2, linestyle=":", alpha=0.8)

    for name, val in (fault_markers or {}).items():
        if val and val > 0:
            ax.axvline(val, color="#555555", linewidth=1.0, linestyle="-.", alpha=0.7)
            ax.annotate(rtl(name), (val, ax.get_ylim()[0]), rotation=90, fontsize=7,
                        xytext=(3, 12), textcoords="offset points", color="#444444")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(rtl("جریان (آمپر)"), fontsize=9)
    ax.set_ylabel(rtl("زمان عملکرد (ثانیه)"), fontsize=9)
    if title:
        ax.set_title(rtl(title), fontsize=10)
    ax.grid(True, which="both", linestyle=":", alpha=0.45)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path
