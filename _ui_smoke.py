# -*- coding: utf-8 -*-
"""تست راه‌اندازی UI بدون نمایش پنجره."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setLayoutDirection(Qt.RightToLeft)
win = MainWindow()
qss = Path(__file__).resolve().parent / "app" / "ui" / "theme.qss"
win.setStyleSheet(qss.read_text(encoding="utf-8"))
win.show()

# ناوبری بین همه صفحات
for key in list(win.nav_buttons.keys()):
    win.navigate(key)

# ساخت پروژه جدید در پوشه موقت و پر کردن فرم پروژه
import tempfile
tmp = Path(tempfile.mkdtemp()) / "پروژه_تست"
win.new_project_silent(tmp) if hasattr(win, "new_project_silent") else None

# تست با متد داخلی
win.manager.new_project(tmp)
win._update_project_dependent_pages()
for key in list(win.nav_buttons.keys()):
    win.navigate(key)

win.project_page.save_to(win.manager.project)
win.manager.save()
print("UI smoke test OK — pages:", len(win.nav_buttons), "project:", win.manager.project_dir.name)
