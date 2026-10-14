# -*- coding: utf-8 -*-
"""Design System مرکزی Shell مهندسی (Design Tokens) — بدون وابستگی به Qt.

* رنگ‌ها فقط از ``app.ui.theme.tokens`` (Light/Dark) خوانده می‌شوند؛ اینجا رنگ
  Hard-code نمی‌شود.
* Spacing / Radius / Typography و Glyph وضعیت‌ها مقادیر ثابت و مرکزی‌اند.
* ``shell_qss`` فقط قواعد اختصاصی Shell را می‌سازد و به QSS پایه (theme.build_qss) افزوده می‌شود.
"""
from __future__ import annotations

from typing import Optional

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}
RADIUS = {"sm": 4, "md": 6, "lg": 8}
FONT_PT = {"caption": 8.5, "body": 10.5, "title": 11.5, "page": 15}
ICON_PX = {"toolbar": 20, "tree": 16, "badge": 14}

# وضعیت منطقی مطالعه ← حالت بصری Badge در theme.py
STUDY_STATE_TO_BADGE = {
    "complete": "completed", "review_required": "review", "incomplete": "warning",
    "empty": "pending", "not_selected": "pending", "not_evaluated": "info",
}
# وضعیت نتیجهٔ Rule ← حالت بصری
RESULT_STATE_TO_BADGE = {
    "PASS": "completed", "WARNING": "warning", "FAIL": "error", "INFO": "info",
    "MISSING_DATA": "warning", "MISSING_RULE": "review", "DATA_ERROR": "error",
    "REQUIRES_ENGINEER_REVIEW": "review",
}
GLYPH = {"completed": "✓", "warning": "⚠", "error": "✕", "review": "◆",
         "info": "ℹ", "pending": "○", "normal": "✓"}

MISSING_TEXT = "—"


def format_quantity(value: Optional[float], unit: str = "", decimals: int = 2) -> str:
    """نمایش استاندارد عدد مهندسی با واحد؛ نبود داده = «—» (نه صفر).

    صفرهای انتهایی حذف می‌شود (۶۳۰ A، ۰٫۱۸) و بین عدد و واحد یک فاصلهٔ ناشکن
    می‌آید تا واحد در RTL از عدد جدا نشود.
    """
    if value is None:
        return MISSING_TEXT
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".") if decimals else f"{value:.0f}"
    return f"{text}\u00a0{unit}" if unit else text


def shell_qss(theme: str, tokens: dict) -> str:
    """QSS افزودهٔ Shell (Explorer، Inspector، Dock، ToolBar، MenuBar)."""
    t, r, s = tokens, RADIUS, SPACING
    return f"""
QMenuBar {{ background: {t['surface']}; color: {t['text']}; border-bottom: 1px solid {t['border']}; }}
QMenuBar::item {{ padding: {s['xs']}px {s['md']}px; background: transparent; }}
QMenuBar::item:selected {{ background: {t['selection']}; border-radius: {r['sm']}px; }}
QToolBar {{ background: {t['surface_alt']}; border: none; border-bottom: 1px solid {t['border']};
    spacing: {s['xs']}px; padding: {s['xs']}px {s['sm']}px; }}
QToolButton {{ background: transparent; color: {t['text']}; border: 1px solid transparent;
    border-radius: {r['md']}px; padding: {s['xs']}px {s['sm']}px; }}
QToolButton:hover {{ background: {t['selection']}; border-color: {t['border']}; }}
QToolButton:checked {{ background: {t['info_bg']}; border-color: {t['info']}; }}
QToolButton:disabled {{ color: {t['disabled']}; }}
QFrame#GuideBar {{ background: {t['info_bg']}; border-bottom: 1px solid {t['border']}; }}
QLabel#GuideTitle {{ color: {t['primary']}; font-weight: 700; }}
QLabel#PanelTitle {{ background: {t['table_head']}; color: {t['text']}; font-weight: 600;
    padding: {s['sm']}px {s['md']}px; border-bottom: 1px solid {t['border']}; }}
QSplitter::handle {{ background: {t['border']}; }}
QSplitter::handle:hover {{ background: {t['primary']}; }}
QDockWidget {{ color: {t['text']}; }}
QDockWidget::title {{ background: {t['table_head']}; padding: {s['sm']}px {s['md']}px;
    border-bottom: 1px solid {t['border']}; font-weight: 600; }}
QTreeWidget#ProjectExplorer {{ background: {t['surface']}; border: none; outline: 0; }}
QTreeWidget#ProjectExplorer::item {{ padding: {s['xs']}px {s['xs']}px; }}
QTreeWidget#ProjectExplorer::item:selected {{ background: {t['selection']}; color: {t['text']}; }}
QTabWidget#WorkspaceTabs::pane {{ border: none; border-top: 1px solid {t['border']}; background: {t['bg']}; }}
QTabWidget#WorkspaceTabs QTabBar::tab {{ background: {t['surface_alt']}; color: {t['muted']};
    border: 1px solid {t['border']}; border-bottom: none;
    border-top-left-radius: {r['md']}px; border-top-right-radius: {r['md']}px;
    padding: {s['sm']}px {s['lg']}px; margin-left: 2px; }}
QTabWidget#WorkspaceTabs QTabBar::tab:selected {{ background: {t['surface']}; color: {t['text']};
    border-top: 2px solid {t['primary']}; font-weight: 600; }}
QFrame#InspectorCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {r['lg']}px; }}
QLabel#InspectorTitle {{ font-size: {FONT_PT['title']}pt; font-weight: 700; }}
QLabel#InspectorKey {{ color: {t['muted']}; }}
QLabel#InspectorValue {{ font-weight: 600; }}
QFrame#DashCard {{ background: {t['surface']}; border: 1px solid {t['border']};
    border-radius: {r['lg']}px; }}
QLabel#DashValue {{ font-size: {FONT_PT['page']}pt; font-weight: 700; }}
QLineEdit[invalid="true"] {{ border: 1px solid {t['danger']}; background: {t['danger_bg']}; }}
QLabel#FieldError {{ color: {t['danger']}; font-size: {FONT_PT['caption']}pt; }}
QListWidget#ValidationList::item {{ padding: {s['xs']}px {s['sm']}px; border-bottom: 1px solid {t['border']}; }}
"""
