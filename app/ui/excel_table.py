# -*- coding: utf-8 -*-
"""رفتار «جدول شبیه اکسل» برای همهٔ جدول‌های داده‌ای برنامه — نسخه ۱.۲.۰.

قابلیت‌ها (روی هر ``QTableWidget``):

* **Delete/Backspace**: پاک‌کردن محتوای خانه‌های انتخاب‌شده (چند خانه با هم).
* **Enter / Shift+Enter**: رفتن به ردیف پایین/بالا (همان ستون)؛ در آخرین ردیف،
  یک ردیف خالی تازه افزوده می‌شود (اگر ``auto_add_row=True`` باشد).
* **Tab / Shift+Tab**: رفتن به ستون بعد/قبل و در انتهای ردیف، ابتدای ردیف بعد.
* **Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+A**: کپی، برش، چسباندن و انتخاب همه.
  محتوا با قالب TSV در ``text/plain`` کپی می‌شود (مستقیماً در Excel می‌چسبد) و
  چسباندن از Excel هم پشتیبانی می‌شود: بلوک چندخانه‌ای، رشد خودکار ردیف‌ها و
  پرکردن همهٔ خانه‌های انتخاب‌شده با یک مقدار.
* **منوی راست‌کلیک**: کپی، چسباندن، پاک‌کردن محتوا، درج ردیف، حذف ردیف، انتخاب همه.
* **کلید تایپ**: شروع ویرایش همان خانه (رفتار اکسل).

رفتار محافظه‌کارانه (مطابق قواعد پروژه):

* هیچ داده‌ای ساخته نمی‌شود؛ فقط نوشتن/پاک‌کردن ورودی کاربر انجام می‌گیرد.
* خانه‌هایی که ویرایش‌ناپذیرند (پرچم ``ItemIsEditable`` ندارند یا در فهرست
  ``table.readonly_columns`` هستند) هرگز تغییر نمی‌کنند.
* پاک‌کردن، مقدار خالی می‌گذارد (نه صفر و نه صفر جایگزین)، پس در مدل هم خانهٔ
  خالی به ``None`` نگاشت می‌شود.
"""
from __future__ import annotations

import html as html_mod
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QMenu,
                               QTableWidget, QTableWidgetItem)

#: ستون‌هایی که هرگز نباید ویرایش شوند (نام ستون‌ها) — از سمت صفحه‌ها پر می‌شود.
_DEFAULT_READONLY: set[str] = set()


class ExcelTableBehavior(QObject):
    """نصب رفتار اکسل روی یک جدول موجود (بدون تغییر کلاس جدول)."""

    #: پس از هر تغییر محتوا (پاک‌کردن/چسباندن) منتشر می‌شود.
    changed = Signal()
    #: پیام‌های راهنما (مثلاً افزوده‌شدن ردیف یا ستون‌های نادیده‌گرفته‌شده).
    note = Signal(str)

    def __init__(self, table: QTableWidget, *, editable: bool = True,
                 auto_add_row: bool = True,
                 note_cb: Optional[Callable[[str], None]] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent or table)
        self.table = table
        self.editable = bool(editable)
        self.auto_add_row = bool(auto_add_row)
        self._note_cb = note_cb
        self._installed = True

        table.installEventFilter(self)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if self.editable:
            triggers = table.editTriggers()
            table.setEditTriggers(triggers | QAbstractItemView.DoubleClicked
                                  | QAbstractItemView.EditKeyPressed
                                  | QAbstractItemView.AnyKeyPressed)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._context_menu)
        # با lambda وصل می‌شود تا هنگام حذف جدول، خطای «Slot not found» رخ ندهد
        table.destroyed.connect(lambda *_a, _self=self: _self._detach())

    # ------------------------------------------------------------------
    # پیام راهنما
    # ------------------------------------------------------------------
    def _note(self, text: str) -> None:
        self.note.emit(text)
        if self._note_cb is not None:
            try:
                self._note_cb(text)
            except Exception:                       # noqa: BLE001 (پیام راهنما نباید بشکند)
                pass

    # ------------------------------------------------------------------
    # چرخهٔ عمر
    # ------------------------------------------------------------------
    def _detach(self, *_a) -> None:
        self._installed = False
        try:
            self.table = None                   # type: ignore[assignment]
        except Exception:                       # noqa: BLE001 (هنگام تخریب شیء)
            pass

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    def _cell_editable(self, row: int, col: int) -> bool:
        if not self.editable or self.table is None:
            return False
        item = self.table.item(row, col)
        if item is None:
            return True                          # خانهٔ خالی ساخته می‌شود
        if not (item.flags() & Qt.ItemIsEditable):
            return False
        header = self.table.horizontalHeaderItem(col)
        name = header.text() if header is not None else ""
        return name not in getattr(self.table, "readonly_columns", _DEFAULT_READONLY)

    def _ensure_item(self, row: int, col: int) -> QTableWidgetItem:
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)
        return item

    def _selection_rect(self) -> tuple[int, int, int, int]:
        """(سطر بالا، ستون چپ، سطر پایین، ستون راست) از انتخاب فعلی."""
        ranges = self.table.selectedRanges()
        if not ranges:
            row, col = self.table.currentRow(), self.table.currentColumn()
            return (max(row, 0), max(col, 0), max(row, 0), max(col, 0))
        top = min(r.topRow() for r in ranges)
        left = min(r.leftColumn() for r in ranges)
        bottom = max(r.bottomRow() for r in ranges)
        right = max(r.rightColumn() for r in ranges)
        return top, left, bottom, right

    def _clip_text(self, matrix: list[list[str]]) -> str:
        return "\r\n".join("\t".join(cell.replace("\r", " ").replace("\n", " ")
                                    for cell in row) for row in matrix)

    # ------------------------------------------------------------------
    # عملیات عمومی (قابل صدا زدن از دکمه‌های صفحه)
    # ------------------------------------------------------------------
    def clear_selected(self) -> None:
        """پاک‌کردن محتوای خانه‌های انتخاب‌شده (خانه‌های فقط‌خواندنی دست‌نخورده)."""
        top, left, bottom, right = self._selection_rect()
        changed = False
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if not self._cell_editable(row, col):
                    continue
                item = self.table.item(row, col)
                if item is not None and item.text():
                    item.setText("")
                    changed = True
        if changed:
            self.changed.emit()

    def copy(self, cut: bool = False) -> bool:
        top, left, bottom, right = self._selection_rect()
        matrix = [[self.table.item(r, c).text() if self.table.item(r, c) else ""
                   for c in range(left, right + 1)]
                  for r in range(top, bottom + 1)]
        text = self._clip_text(matrix)
        html = ("<table>" + "".join(
            "<tr>" + "".join(f"<td>{html_mod.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in matrix) + "</table>")
        mime = _make_mime(text, html)
        QApplication.clipboard().setMimeData(mime)
        if cut:
            self.clear_selected()
        return True

    def paste(self) -> bool:
        """چسباندن از کلیپ‌بورد (پشتیبانی از بلوک کپی‌شده از Excel)."""
        if not self.editable:
            return False
        text = _clipboard_text()
        if text is None:
            self._note("کلیپ‌بورد خالی است.")
            return False
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        rows = text.split("\n")
        if rows and rows[-1] == "":
            rows.pop()
        matrix = [row.split("\t") for row in rows]
        if not matrix:
            return False

        top, left, bottom, right = self._selection_rect()
        selected_multi = (bottom > top or right > left)

        # یک مقدار و انتخاب چندخانه‌ای → همهٔ خانه‌های انتخاب‌شده پر می‌شوند (اکسل)
        if selected_multi and len(matrix) == 1 and len(matrix[0]) == 1:
            value = matrix[0][0]
            for row in range(top, bottom + 1):
                for col in range(left, right + 1):
                    if self._cell_editable(row, col):
                        self._ensure_item(row, col).setText(value)
            self.changed.emit()
            return True

        need_rows = top + len(matrix) - self.table.rowCount()
        added = 0
        if need_rows > 0 and self.auto_add_row:
            for _ in range(need_rows):
                self._insert_row(self.table.rowCount())
                added += 1
        skipped_cells = 0
        for r_off, row_values in enumerate(matrix):
            row = top + r_off
            if row >= self.table.rowCount():
                skipped_cells += len(row_values)
                continue
            for c_off, value in enumerate(row_values):
                col = left + c_off
                if col >= self.table.columnCount():
                    skipped_cells += 1
                    continue
                if not self._cell_editable(row, col):
                    continue
                self._ensure_item(row, col).setText(value)
        if added:
            self._note(f"{added} ردیف تازه برای جا شدن دادهٔ چسبانده‌شده افزوده شد.")
        if skipped_cells:
            self._note(f"{skipped_cells} خانه خارج از محدودهٔ جدول بود و نادیده گرفته شد.")
        self.changed.emit()
        return True

    def insert_row_below(self) -> None:
        row = max(self.table.currentRow(), 0)
        self._insert_row(row + 1)
        self.changed.emit()

    def delete_current_row(self) -> None:
        row = self.table.currentRow()
        if row < 0 or self.table.rowCount() <= 0:
            return
        self.table.removeRow(row)
        self.changed.emit()

    def select_all(self) -> None:
        self.table.selectAll()

    # ------------------------------------------------------------------
    # رویدادها
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (نام Qt)
        # هنگام بسته‌شدن پروژه/پنجره ممکن است ویژگی‌های پایتونی پاک شده باشند؛
        # بنابراین همهٔ دسترسی‌ها با getattr و try انجام می‌شود.
        try:
            table = getattr(self, "table", None)
            if table is None or not getattr(self, "_installed", False) or obj is not table:
                return False
            if event.type() == QEvent.KeyPress:
                return self._on_key(event)
        except RuntimeError:
            return False
        return False

    def _on_key(self, event) -> bool:
        table, key = self.table, event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        shift = bool(mods & Qt.ShiftModifier)
        editing = table.state() == QAbstractItemView.EditingState

        if key == Qt.Key_Escape:
            if not editing:
                table.clearSelection()
                return True
            return False

        if editing:
            # هنگام ویرایش خانه، کلیدها در اختیار ویرایشگر هستند (رفتار اکسل)
            return False

        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.clear_selected()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._move_row(-1 if shift else +1)
            return True
        if key == Qt.Key_Tab:
            self._move_col(-1 if shift else +1)
            return True
        if ctrl and key == Qt.Key_C:
            self.copy(); return True
        if ctrl and key == Qt.Key_X:
            self.copy(cut=True); return True
        if ctrl and key == Qt.Key_V:
            self.paste(); return True
        if ctrl and key == Qt.Key_A:
            table.selectAll(); return True
        if ctrl and key == Qt.Key_D:
            self.clear_selected(); return True
        return False

    # ------------------------------------------------------------------
    # جابه‌جایی
    # ------------------------------------------------------------------
    def _move_row(self, step: int) -> None:
        table = self.table
        if table.rowCount() == 0:
            return
        row = table.currentRow()
        col = max(table.currentColumn(), 0)
        if row < 0:                      # هنوز خانه‌ای انتخاب نشده → اولین خانه
            table.setCurrentCell(0, col)
            return
        target = row + step
        if target < 0:
            target = 0
        if target >= table.rowCount() and step > 0 and self.auto_add_row:
            self._insert_row(table.rowCount())
        if table.rowCount() == 0:
            return
        target = min(max(target, 0), table.rowCount() - 1)
        table.setCurrentCell(target, col)
        table.scrollToItem(table.item(target, col))

    def _move_col(self, step: int) -> None:
        table = self.table
        if table.rowCount() == 0:
            return
        row = table.currentRow()
        col = table.currentColumn() + step
        if col >= table.columnCount():
            col = 0
            row += 1
            if row >= table.rowCount() and self.auto_add_row:
                self._insert_row(table.rowCount())
        if col < 0:
            col = max(table.columnCount() - 1, 0)
            row -= 1
        row = min(max(row, 0), max(table.rowCount() - 1, 0))
        if table.rowCount() == 0:
            return
        col = min(max(col, 0), table.columnCount() - 1)
        table.setCurrentCell(row, col)
        table.scrollToItem(table.item(row, col))

    def _insert_row(self, row: int) -> None:
        """افزودن ردیف خالی و هم‌شکل با سایر ردیف‌ها (ستون‌های فقط‌خواندنی خالی، غیرقابل ویرایش)."""
        table = self.table
        table.insertRow(row)
        readonly_names = set(getattr(table, "readonly_columns", _DEFAULT_READONLY))
        for col in range(table.columnCount()):
            header = table.horizontalHeaderItem(col)
            name = header.text() if header is not None else ""
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            if name in readonly_names:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # منوی راست‌کلیک
    # ------------------------------------------------------------------
    def _context_menu(self, pos) -> None:
        if self.table is None:
            return
        menu = QMenu(self.table)
        act_copy = menu.addAction("کپی\tCtrl+C")
        if self.editable:
            act_paste = menu.addAction("چسباندن\tCtrl+V")
            act_clear = menu.addAction("پاک‌کردن محتوای خانه‌های انتخاب‌شده\tDelete")
            menu.addSeparator()
            act_row = menu.addAction("درج ردیف زیر ردیف جاری")
            act_del = menu.addAction("حذف ردیف جاری")
        else:
            act_paste = act_clear = act_row = act_del = None
        menu.addSeparator()
        act_all = menu.addAction("انتخاب همه\tCtrl+A")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_copy:
            self.copy()
        elif act_paste is not None and chosen is act_paste:
            self.paste()
        elif act_clear is not None and chosen is act_clear:
            self.clear_selected()
        elif act_row is not None and chosen is act_row:
            self.insert_row_below()
        elif act_del is not None and chosen is act_del:
            self.delete_current_row()
        elif chosen is act_all:
            self.select_all()


# ---------------------------------------------------------------------------
# کمکی‌های ماژول
# ---------------------------------------------------------------------------
#: نگه‌داشتن آخرین دادهٔ کلیپ‌بورد تا در جمع‌آوری زبالهٔ پایتون آزاد نشود
#: (کلیپ‌بورد Qt مالکیت را می‌گیرد؛ نگه‌داشتن مرجع، کرش هنگام خروج را حذف می‌کند).
_LAST_MIME = None


def _make_mime(text: str, html: str = ""):
    global _LAST_MIME
    from PySide6.QtCore import QMimeData
    mime = QMimeData()
    mime.setText(text)
    if html:
        mime.setHtml(html)
    _LAST_MIME = mime
    return mime


def _clipboard_text() -> Optional[str]:
    mime = QApplication.clipboard().mimeData()
    if mime is None:
        return None
    if mime.hasText():
        return mime.text()
    if mime.hasHtml():
        return None                     # HTML بدون متن ساده: چیزی برای چسباندن نیست
    return None


def enable_excel_table(table: QTableWidget, *, editable: bool = True,
                       auto_add_row: bool = True,
                       note: Optional[Callable[[str], None]] = None) -> ExcelTableBehavior:
    """نصب رفتار اکسل روی جدول و نگه‌داشتن مرجع آن روی خود جدول (جلوگیری از GC)."""
    existing = getattr(table, "excel", None)
    if isinstance(existing, ExcelTableBehavior):
        return existing
    behavior = ExcelTableBehavior(table, editable=editable, auto_add_row=auto_add_row,
                                  note_cb=note)
    table.excel = behavior                # type: ignore[attr-defined]
    return behavior


def clipboard_matrix() -> Optional[list[list[str]]]:
    """ماتریس دادهٔ کلیپ‌بورد (برای تست/ابزارها)."""
    text = _clipboard_text()
    if text is None:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    rows = text.split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    return [row.split("\t") for row in rows]
