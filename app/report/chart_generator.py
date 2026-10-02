# -*- coding: utf-8 -*-
"""مولد نمودار — پروفیل بار و پیش‌بینی با متن فارسی (matplotlib)."""
from __future__ import annotations

from pathlib import Path

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
