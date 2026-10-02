# -*- coding: utf-8 -*-
"""سیستم Theme (Light / Dark) — رنگ‌بندی محدود و مناسب نرم‌افزار مهندسی (v1.0.3).

همه رنگ‌ها از Token ها می‌آیند؛ QSS در زمان اجرا ساخته می‌شود تا تعویض Theme
بدون راه‌اندازی مجدد ممکن باشد. کنتراست متن/جداول در هر دو Theme رعایت شده است.
"""
from __future__ import annotations

FONT_STACK = '"Vazirmatn", "Segoe UI", "Tahoma", "DejaVu Sans", sans-serif'

LIGHT = {
    "bg": "#F3F5F8", "surface": "#FFFFFF", "surface_alt": "#F7F9FC",
    "border": "#D5DBE3", "text": "#1B2430", "muted": "#5F6B7A",
    "primary": "#1F5FA8", "primary_hover": "#184E8C", "on_primary": "#FFFFFF",
    "sidebar": "#18283B", "sidebar_text": "#C9D3E0", "sidebar_active": "#27466B",
    "sidebar_hover": "#203650", "sidebar_head": "#FFFFFF",
    "success": "#2E7D32", "success_bg": "#E4F3E5",
    "warning": "#A15C00", "warning_bg": "#FFF1D6",
    "danger": "#B3261E", "danger_bg": "#FBE4E2",
    "review": "#6A3FB5", "review_bg": "#EEE6FA",
    "info": "#1F5FA8", "info_bg": "#E1ECF9",
    "done": "#00796B", "done_bg": "#DDF1EE",
    "table_head": "#E8EDF4", "table_alt": "#F7F9FC", "selection": "#D6E6FA",
    "input_bg": "#FFFFFF", "disabled": "#9AA5B3",
}
DARK = {
    "bg": "#12171E", "surface": "#1B222C", "surface_alt": "#212A36",
    "border": "#323D4B", "text": "#E6EBF2", "muted": "#9AA7B8",
    "primary": "#4C97E6", "primary_hover": "#6AABF0", "on_primary": "#0B1622",
    "sidebar": "#0D1218", "sidebar_text": "#A9B6C7", "sidebar_active": "#1F3A5C",
    "sidebar_hover": "#17222F", "sidebar_head": "#FFFFFF",
    "success": "#6FCF76", "success_bg": "#1B3A20",
    "warning": "#F0B14A", "warning_bg": "#3D2E10",
    "danger": "#F2837C", "danger_bg": "#4A1F1C",
    "review": "#B99BEF", "review_bg": "#2E2347",
    "info": "#7DB6F2", "info_bg": "#1B2F47",
    "done": "#52C2B2", "done_bg": "#12332F",
    "table_head": "#27313F", "table_alt": "#202936", "selection": "#27466B",
    "input_bg": "#161C25", "disabled": "#5E6A7A",
}
THEMES = {"light": LIGHT, "dark": DARK}
THEME_LABELS = {"light": "روشن (Light)", "dark": "تاریک (Dark)"}

# وضعیت‌ها (Normal / Warning / Error / Requires Review / Completed)
STATES = ("normal", "warning", "error", "review", "completed", "info", "pending")
STATE_LABELS_FA = {"normal": "Normal", "warning": "Warning", "error": "Error",
                   "review": "Requires Review", "completed": "Completed",
                   "info": "Info", "pending": "Pending"}


def tokens(name: str) -> dict:
    return THEMES.get(name, LIGHT)


def state_colors(name: str, state: str) -> tuple[str, str]:
    t = tokens(name)
    key = {"normal": "success", "completed": "done", "error": "danger",
           "warning": "warning", "review": "review", "info": "info",
           "pending": "muted"}.get(state, "info")
    bg = t.get(f"{key}_bg", t["surface_alt"])
    return t[key], bg


def build_qss(name: str = "light") -> str:
    t = tokens(name)
    badge_rules = []
    for st in STATES:
        fg, bg = state_colors(name, st)
        badge_rules.append(
            f'QLabel[badge="true"][state="{st}"] {{ color: {fg}; background: {bg}; '
            f'border: 1px solid {fg}; }}')
    return f"""
* {{ font-family: {FONT_STACK}; font-size: 10.5pt; }}
QMainWindow, QDialog, QMessageBox {{ background: {t['bg']}; color: {t['text']}; }}
QWidget#Page, QStackedWidget {{ background: {t['bg']}; }}
QWidget {{ color: {t['text']}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px; }}

/* ---- Sidebar ---- */
QWidget#Sidebar {{ background: {t['sidebar']}; }}
QLabel#SidebarTitle {{ color: {t['sidebar_head']}; font-size: 13pt; font-weight: 700; padding: 4px 6px 2px 6px; }}
QLabel#SidebarSub {{ color: {t['sidebar_text']}; font-size: 8.5pt; padding: 0 6px 10px 6px; }}
QLabel#SidebarGroup {{ color: {t['sidebar_text']}; font-size: 8.5pt; padding: 12px 8px 2px 8px; }}
QPushButton#NavButton {{ background: transparent; color: {t['sidebar_text']}; border: none; border-radius: 6px;
    text-align: right; padding: 9px 12px; }}
QPushButton#NavButton:hover {{ background: {t['sidebar_hover']}; }}
QPushButton#NavButton:checked {{ background: {t['sidebar_active']}; color: #FFFFFF; font-weight: 600; }}
QPushButton#NavButton:disabled {{ color: {t['disabled']}; }}
QLabel#SidebarFooter {{ color: {t['sidebar_text']}; font-size: 8.5pt; padding: 6px; }}

/* ---- Header / Stepper ---- */
QFrame#HeaderBar {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
QLabel#ProjectName {{ font-size: 13pt; font-weight: 700; }}
QLabel#ProjectMeta {{ color: {t['muted']}; font-size: 9pt; }}
QFrame#StepBar {{ background: {t['surface_alt']}; border-bottom: 1px solid {t['border']}; }}
QPushButton#StepChip {{ background: transparent; border: 1px solid transparent; border-radius: 12px;
    padding: 4px 12px; color: {t['muted']}; }}
QPushButton#StepChip:hover {{ border-color: {t['border']}; }}
QPushButton#StepChip[step="current"] {{ background: {t['info_bg']}; color: {t['info']}; border-color: {t['info']}; font-weight: 600; }}
QPushButton#StepChip[step="done"] {{ color: {t['done']}; }}
QPushButton#StepChip[step="error"] {{ color: {t['danger']}; font-weight: 600; }}
QPushButton#StepChip[step="warning"] {{ color: {t['warning']}; }}
QPushButton#StepChip:disabled {{ color: {t['disabled']}; }}

/* ---- Typography ---- */
QLabel#PageTitle {{ font-size: 15pt; font-weight: 700; }}
QLabel#PageSubtitle, QLabel#Muted {{ color: {t['muted']}; }}
QLabel#SectionTitle {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#CardValue {{ font-size: 17pt; font-weight: 700; }}
QLabel#CardCaption {{ color: {t['muted']}; font-size: 9pt; }}
QLabel#AppTitle {{ font-size: 20pt; font-weight: 700; }}

/* ---- Cards ---- */
QFrame#Card, QGroupBox {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px; }}
QGroupBox {{ margin-top: 14px; padding: 12px 10px 8px 10px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top right; padding: 0 8px; color: {t['text']}; }}
QFrame#CardAccent {{ background: {t['surface']}; border: 1px solid {t['border']}; border-right: 4px solid {t['primary']}; border-radius: 8px; }}

/* ---- Badges ---- */
QLabel[badge="true"] {{ border-radius: 9px; padding: 1px 9px; font-size: 8.5pt; font-weight: 600; }}
{chr(10).join(badge_rules)}

/* ---- Buttons ---- */
QPushButton {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ background: {t['surface_alt']}; border-color: {t['primary']}; }}
QPushButton:pressed {{ background: {t['selection']}; }}
QPushButton:disabled {{ color: {t['disabled']}; background: {t['surface_alt']}; border-color: {t['border']}; }}
QPushButton:focus {{ border: 1px solid {t['primary']}; }}
QPushButton#primary {{ background: {t['primary']}; color: {t['on_primary']}; border: 1px solid {t['primary']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {t['primary_hover']}; }}
QPushButton#primary:disabled {{ background: {t['border']}; color: {t['disabled']}; border-color: {t['border']}; }}
QPushButton#success {{ background: {t['success']}; color: {t['on_primary']}; border-color: {t['success']}; font-weight: 600; }}
QPushButton#danger {{ color: {t['danger']}; border-color: {t['danger']}; }}
QPushButton#danger:hover {{ background: {t['danger_bg']}; }}
QPushButton#ghost {{ border: none; background: transparent; color: {t['primary']}; }}
QPushButton#QuickAction {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 8px;
    padding: 14px; text-align: right; }}
QPushButton#QuickAction:hover {{ border-color: {t['primary']}; background: {t['info_bg']}; }}

/* ---- Inputs ---- (ارتفاع استاندارد فیلدها؛ min-height از فشرده‌شدن توسط Layout جلوگیری می‌کند) */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox, QTextBrowser {{
    background: {t['input_bg']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px;
    padding: 5px 10px; min-height: 26px;
    selection-background-color: {t['selection']}; selection-color: {t['text']}; }}
QTextEdit, QPlainTextEdit, QTextBrowser {{ min-height: 64px; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {t['primary']}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {t['disabled']}; background: {t['surface_alt']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; color: {t['text']}; selection-background-color: {t['selection']}; selection-color: {t['text']}; border: 1px solid {t['border']}; }}
QCheckBox, QRadioButton {{ spacing: 6px; }}

/* ---- Tables / Lists ---- */
QTableWidget, QTableView, QListWidget, QTreeWidget {{ background: {t['surface']}; alternate-background-color: {t['table_alt']};
    color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px; gridline-color: {t['border']};
    selection-background-color: {t['selection']}; selection-color: {t['text']}; }}
QHeaderView::section {{ background: {t['table_head']}; color: {t['text']}; border: none; border-bottom: 1px solid {t['border']};
    border-left: 1px solid {t['border']}; padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {t['table_head']}; border: none; }}
QListWidget::item {{ padding: 6px 8px; }}
QListWidget::item:selected {{ background: {t['selection']}; color: {t['text']}; }}

/* ---- Tabs ---- */
QTabWidget::pane {{ border: 1px solid {t['border']}; border-radius: 6px; background: {t['surface']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {t['primary']}; border-bottom: 2px solid {t['primary']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {t['text']}; }}

/* ---- Progress / Status / Scroll ---- */
QProgressBar {{ background: {t['surface_alt']}; border: 1px solid {t['border']}; border-radius: 6px; text-align: center; height: 16px; color: {t['text']}; }}
QProgressBar::chunk {{ background: {t['primary']}; border-radius: 5px; }}
QStatusBar {{ background: {t['surface']}; color: {t['muted']}; border-top: 1px solid {t['border']}; }}
QStatusBar QLabel {{ color: {t['muted']}; padding: 0 8px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle {{ background: {t['border']}; }}
QMenu {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['selection']}; }}
"""


def apply_theme(app_or_widget, name: str) -> None:
    app_or_widget.setStyleSheet(build_qss(name))
