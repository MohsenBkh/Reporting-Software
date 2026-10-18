# -*- coding: utf-8 -*-
"""صفحه «مطالعه مصارف سنگین» — ورود داده‌های دفترچه مطالعات (TAV111-10/00).

شش تب مطابق ساختار دفترچه:

1. **اطلاعات تقاضا** — تقاضا با/بدون ضریب همزمانی و دیماند موجود (+ محاسبه‌های خودکار).
2. **ایستگاه‌های نزدیک به محل تقاضا** — فاصله، ظرفیت، بارگیری T1/T2، پیک T1/T2، تعداد فیدر.
3. **خطوط نزدیک به محل تقاضا** — فاصله، پیک MVA/MW/A، افت ولتاژ قبل/بعد، اتصال کوتاه، ظرفیت هدایتی.
4. **متقاضیان همزمان و کنترل داده** — فهرست متقاضیان، کل بار گزارش‌شده، تقاضای مبنای تحلیل،
   سطح ولتاژ شبکه و بررسی توپولوژیکی تأمین مشترک.
5. **مسیر و هزینه سناریوها** — سناریوهای تولیدشده توسط Rule Engine، طول/درصد مسیر،
   هزینه ثبت‌شده و برآورد پارامتریک.
6. **فیدرهای همجوار (بازآرایی)** — کاندیدهای انتقال بار؛ مبنای Ruleهای LD-REARRANGE و
   سناریوی «بازآرایی فیدر».

هر ردیف جدول‌ها یک کلید On/Off («در گزارش») دارد: ردیف خاموش، از تحلیل و گزارش حذف
می‌شود ولی داده‌اش پاک نمی‌شود. ویرایش جدول‌ها مانند Excel است (Delete، Enter، کپی/چسباندن).

هیچ آستانه یا مقدار فنی‌ای در این صفحه ساخته نمی‌شود؛ داده‌ها فقط ثبت/ویرایش و در پروژه
ذخیره می‌شوند تا Rule Engine بر پایه آن‌ها تحلیل کند.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox,
                               QHeaderView, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.models import (CoincidentDemand, LineCandidate, NeighborFeeder,
                             SubstationCandidate, SupplyScenario,
                             SCENARIO_KIND_LABELS)
from app.core.settings import AppSettings
from app.core.study import cost_estimate
from app.ui.excel_table import enable_excel_table
from app.ui.widgets import (OptionalSpin, configure_data_table, fit_columns,
                            make_spin, page_header, scrollable)
from app.utils.formatting import fmt

# ---------------------------------------------------------------------------
# ستون‌های جدول‌ها
# ---------------------------------------------------------------------------
ONOFF_COL = "در گزارش (On/Off)"
SUBSTATION_COLS = [ONOFF_COL, "نام ایستگاه", "امور/دفتر", "فاصله km", "ظرفیت MVA",
                   "بارگیری T1 ٪", "بارگیری T2 ٪", "پیک T1 MVA", "پیک T2 MVA",
                   "تعداد فیدر", "سال پیک"]
LINE_COLS = [ONOFF_COL, "نام خط", "امور/دفتر", "فاصله m", "پیک MVA", "پیک MW", "پیک A",
             "افت ولتاژ قبل ٪", "افت ولتاژ بعد ٪", "SC حداکثر kA", "SC حداقل kA",
             "ظرفیت هدایتی A", "سال پیک"]
COINCIDENT_COLS = [ONOFF_COL, "نام متقاضی", "توان موجود/درخواستی kW", "توان جدید kW",
                   "افزایش بار kW", "محل", "امکان تأمین"]
SCENARIO_COLS = [ONOFF_COL, "نوع", "عنوان سناریو", "فیدر نامزد", "طول شبکه km", "٪ هوایی",
                 "٪ زمینی", "هزینه (م.ت)", "تجهیزات",
                 "برآورد (م.ت)"]
NEIGHBOR_COLS = [ONOFF_COL, "نام فیدر همجوار", "امور/دفتر", "پست", "پیک بار MW",
                 "معیار بارگذاری MW", "پیک جریان A", "حداکثر جریان مجاز A",
                 "فاصله km", "بار قابل انتقال MW", "ملاحظات"]
READ_ONLY_COLS = {"برآورد (م.ت)"}

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _num(text: str) -> Optional[float]:
    """تبدیل متن خانه جدول به عدد؛ خالی = None (هیچ مقدار جایگزینی ساخته نمی‌شود)."""
    raw = (text or "").translate(_FA_DIGITS).replace("٬", "").replace(",", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _text(value) -> str:
    return "" if value is None else fmt(value, 3) if isinstance(value, float) else str(value)



_configure_table = configure_data_table
_fit_columns = fit_columns


class StudyPage(QWidget):
    """ورود داده‌های مطالعه مصارف سنگین (۵ جدول)."""

    changed = Signal()
    request_generate_scenarios = Signal()
    request_cost_estimate = Signal()

    def __init__(self, manager, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.settings = settings
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "مطالعه مصارف سنگین",
            "داده‌های دفترچه مطالعات فنی اتصال مصارف سنگین (TAV111-10/00): اطلاعات تقاضا، "
            "ایستگاه‌های نزدیک، خطوط نزدیک، متقاضیان همزمان و مسیر/هزینه سناریوها. "
            "این داده‌ها مستقیماً در Rule Engine و بخش‌های گزارش استفاده می‌شوند."))

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._wrap(self._build_demand_tab()), "۱) اطلاعات تقاضا")
        self.tabs.addTab(self._wrap(self._build_table_tab(
            SUBSTATION_COLS, "substations",
            "ایستگاه‌های نزدیک به محل تقاضا (ردیف = ایستگاه)")), "۲) ایستگاه‌های نزدیک")
        self.tabs.addTab(self._wrap(self._build_table_tab(
            LINE_COLS, "lines",
            "خطوط نزدیک به محل تقاضا (ردیف = خط)")), "۳) خطوط نزدیک")
        self.tabs.addTab(self._wrap(self._build_coincident_tab()), "۴) متقاضیان و کنترل داده")
        self.tabs.addTab(self._wrap(self._build_scenario_tab()), "۵) مسیر و هزینه سناریوها")
        self.tabs.addTab(self._wrap(self._build_neighbor_tab()),
                         "۶) فیدرهای همجوار (بازآرایی)")

    # ------------------------------------------------------------------
    def _wrap(self, inner: QWidget) -> QWidget:
        """قرار دادن محتوای تب در ناحیهٔ اسکرول‌دار تا در پنجره‌های کوچک فشرده نشود."""
        return scrollable(inner)

    # ------------------------------------------------------------------
    # ساخت تب‌ها
    # ------------------------------------------------------------------
    def _build_demand_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        grp = QGroupBox("اطلاعات تقاضا (جدول «اطلاعات تقاضا» دفترچه)")
        f = QFormLayout(grp)
        self.sp_without = make_spin(0, 1e7, 0, 0.0)
        self.sp_without.setSuffix(" kW")
        self.sp_with = make_spin(0, 1e7, 0, 0.0)
        self.sp_with.setSuffix(" kW")
        self.sp_existing = OptionalSpin(None, 0, 1e7, 0, " kW", "دارد")
        self.chk_demand = QCheckBox("این اطلاعات در تحلیل و گزارش لحاظ شود (On/Off)")
        self.chk_demand.setChecked(True)
        self.chk_demand.toggled.connect(self._on_item_changed)
        for w in (self.sp_without, self.sp_with, self.sp_existing.spinbox()):
            w.valueChanged.connect(self._recalc_demand)
        self.sp_existing.chk.toggled.connect(self._recalc_demand)
        f.addRow("میزان تقاضا بدون ضریب همزمانی:", self.sp_without)
        f.addRow("میزان تقاضا با ضریب همزمانی:", self.sp_with)
        f.addRow("میزان دیماند موجود:", self.sp_existing)
        f.addRow("", self.chk_demand)
        v.addWidget(grp)

        info = QGroupBox("مقادیر محاسبه‌شده (فقط نمایش — مبنای Rule Engine)")
        fi = QFormLayout(info)
        self.lbl_factor = QLabel("—")
        self.lbl_analysis = QLabel("—")
        self.lbl_note = QLabel("")
        self.lbl_note.setObjectName("Muted")
        self.lbl_note.setWordWrap(True)
        fi.addRow("ضریب همزمانی (با ÷ بدون):", self.lbl_factor)
        fi.addRow("تقاضای مبنای تحلیل:", self.lbl_analysis)
        v.addWidget(info)
        v.addWidget(self.lbl_note)
        v.addStretch(1)
        return page

    def _build_table_tab(self, cols: list[str], key: str, title: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel(title))
        table = self._make_table(cols, min_width=92)
        table.setMinimumHeight(220)
        v.addWidget(table, 1)
        v.addLayout(self._row_col_bar(table, cols, key))
        setattr(self, f"tbl_{key}", table)
        return page

    # ------------------------------------------------------------------
    # ساخت جدول با رفتار اکسل (v1.2.0)
    # ------------------------------------------------------------------
    def _make_table(self, cols: list[str], min_width: int = 92) -> QTableWidget:
        table = QTableWidget(0, len(cols))
        _configure_table(table, cols, min_width=min_width)
        table.readonly_columns = set(READ_ONLY_COLS)      # type: ignore[attr-defined]
        table.itemChanged.connect(self._on_item_changed)
        behavior = enable_excel_table(table, editable=True, auto_add_row=True)
        behavior.note.connect(self._note)
        behavior.changed.connect(self._on_item_changed)
        return table

    def _note(self, text: str) -> None:
        if text:
            self.lbl_hint.setText(text)

    # ------------------------------------------------------------------
    # کلید On/Off هر ردیف
    # ------------------------------------------------------------------
    @staticmethod
    def _onoff_item(enabled: bool = True) -> QTableWidgetItem:
        item = QTableWidgetItem("")
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        item.setToolTip("روشن = این ردیف در تحلیل و گزارش لحاظ می‌شود؛ "
                        "خاموش = ردیف نادیده گرفته می‌شود (داده پاک نمی‌شود).")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _enabled(self, table: QTableWidget, r: int) -> bool:
        c = self._col(table, ONOFF_COL)
        if c < 0:
            return True
        item = table.item(r, c)
        if item is None:
            return True
        state = item.data(Qt.CheckStateRole)
        if state is None:
            return True                     # کلید هرگز تنظیم نشده (یا متن بازنویسی شده) → روشن
        return Qt.CheckState(state) == Qt.Checked

    def _set_all_enabled(self, table: QTableWidget, state: bool) -> None:
        c = self._col(table, ONOFF_COL)
        if c < 0:
            return
        for r in range(table.rowCount()):
            item = table.item(r, c)
            if item is not None:
                item.setCheckState(Qt.Checked if state else Qt.Unchecked)
        self._on_item_changed()

    def _row_col_bar(self, table: QTableWidget, cols: list[str], name: str) -> QHBoxLayout:
        """نوار عملیات مشترک: افزودن/حذف ردیف و حذف/بازگرداندن ستون."""
        bar = QHBoxLayout()
        btn_add = QPushButton("+ ردیف")
        btn_del = QPushButton("حذف ردیف انتخاب‌شده")
        btn_del.setObjectName("danger")
        btn_delc = QPushButton("حذف ستون انتخاب‌شده")
        btn_delc.setObjectName("danger")
        btn_rest = QPushButton("بازگرداندن ستون‌ها")
        btn_on = QPushButton("فعال‌کردن همه (On)")
        btn_off = QPushButton("غیرفعال‌کردن همه (Off)")
        btn_add.clicked.connect(lambda: self._add_row(table))
        btn_del.clicked.connect(lambda: self._del_row(table))
        btn_delc.clicked.connect(lambda: self._del_column(table, name))
        btn_rest.clicked.connect(lambda: self._restore_columns(table, cols))
        btn_on.clicked.connect(lambda: self._set_all_enabled(table, True))
        btn_off.clicked.connect(lambda: self._set_all_enabled(table, False))
        for b in (btn_add, btn_del, btn_delc, btn_rest, btn_on, btn_off):
            bar.addWidget(b)
        bar.addStretch(1)
        hint = QLabel("ویرایش مثل Excel: Delete پاک‌کردن خانه، Enter ردیف بعد، "
                      "Ctrl+C / Ctrl+V (چسباندن از Excel) · ستون «در گزارش» = On/Off ردیف")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        bar.addWidget(hint)
        # منوی راست‌کلیک روی سرستون
        header = table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(
            lambda pos, t=table, c=cols, n=name: self._header_menu(t, c, n, pos))
        return bar

    def _header_menu(self, table: QTableWidget, cols: list[str], name: str, pos) -> None:
        from PySide6.QtWidgets import QMenu
        col = table.horizontalHeader().logicalIndexAt(pos)
        menu = QMenu(table)
        if col >= 0:
            label = table.horizontalHeaderItem(col).text()
            act = menu.addAction(f"حذف ستون «{label}»")
            act.triggered.connect(lambda: self._del_column(table, name, col))
        menu.addAction("بازگرداندن ستون‌های پیش‌فرض").triggered.connect(
            lambda: self._restore_columns(table, cols))
        menu.exec(table.horizontalHeader().viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # عملیات ستون‌ها
    # ------------------------------------------------------------------
    def _del_column(self, table: QTableWidget, name: str, col: int | None = None) -> None:
        c = table.currentColumn() if col is None else col
        if c < 0 or c >= table.columnCount():
            QMessageBox.information(self, "حذف ستون", "ابتدا یک ستون را انتخاب کنید.")
            return
        label = table.horizontalHeaderItem(c).text()
        if QMessageBox.question(
                self, "حذف ستون",
                f"ستون «{label}» از جدول حذف شود؟\n"
                "دادهٔ این ستون از همهٔ ردیف‌ها پاک می‌شود (با «بازگرداندن ستون‌ها» می‌توانید ستون "
                "را برگردانید، اما مقادیر آن بازنمی‌گردد).") != QMessageBox.Yes:
            return
        table.removeColumn(c)
        self._on_item_changed()          # ذخیره در مدل: مقدار این فیلد پاک می‌شود

    def _restore_columns(self, table: QTableWidget, cols: list[str]) -> None:
        """بازسازی ستون‌ها با حفظ داده‌های فعلی (بر مبنای عنوان ستون)."""
        keep: list[dict[str, str]] = []
        for r in range(table.rowCount()):
            row = {}
            for c in range(table.columnCount()):
                item = table.horizontalHeaderItem(c)
                if item is not None and table.item(r, c) is not None:
                    row[item.text()] = table.item(r, c).text()
            keep.append(row)
        self._loading = True
        try:
            table.clear()                     # حذف کامل آیتم‌ها/سرستون‌ها (بدون بازاستفاده از آیتم‌ها)
            table.setColumnCount(len(cols))
            table.setRowCount(len(keep))
            _configure_table(table, cols)
            for r, row in enumerate(keep):
                for c, label in enumerate(cols):
                    item = QTableWidgetItem(row.get(label, ""))
                    item.setTextAlignment(Qt.AlignCenter)
                    if label in READ_ONLY_COLS:
                        item.setFlags(Qt.ItemIsEnabled)
                    table.setItem(r, c, item)
            fit_columns(table)
        finally:
            self._loading = False
        self._on_item_changed()

    def _build_coincident_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel("متقاضیان/تقاضاهای همزمان محدوده (ردیف = متقاضی)"))
        self.tbl_coincident = self._make_table(COINCIDENT_COLS, min_width=110)
        self.tbl_coincident.setMinimumHeight(240)
        v.addWidget(self.tbl_coincident, 3)
        v.addLayout(self._row_col_bar(self.tbl_coincident, COINCIDENT_COLS, "coincident"))

        grp = QGroupBox("کنترل ناسازگاری داده‌ها (Cross Validation) و توپولوژی تأمین مشترک")
        f = QFormLayout(grp)
        self.sp_reported_total = OptionalSpin(None, 0, 1e7, 0, " kW", "ثبت‌شده")
        self.sp_analysis_demand = OptionalSpin(None, 0, 1e7, 0, " kW", "ثبت‌شده")
        self.sp_voltage = OptionalSpin(None, 0, 400, 2, " kV", "ثبت‌شده")
        f.addRow("کل بار اضافه‌شده گزارش‌شده (Reported_Total):", self.sp_reported_total)
        f.addRow("تقاضای به‌کاررفته در تحلیل (Demand used in analysis):", self.sp_analysis_demand)
        f.addRow("سطح ولتاژ شبکه (برای کنترل سازگاری جریان):", self.sp_voltage)
        self.cb_joint = QComboBox()
        self.cb_joint.addItems(["ثبت‌نشده", "امکان‌پذیر", "امکان‌پذیر نیست"])
        self.ed_joint_note = QLineEdit()
        self.ed_joint_evidence = QLineEdit()
        self.ed_joint_evidence.setPlaceholderText(
            "شاهد توپولوژیکی (مسیر فیدر/آرایش شبکه) — بدون آن، نتیجه «امکان‌پذیر» ثبت نمی‌شود")
        self.ed_selection = QLineEdit()
        self.ed_selection.setPlaceholderText(
            "در صورت خالی بودن، Rule Engine هیچ سناریویی را توصیه نمی‌کند")
        f.addRow("تأمین مشترک چند نقطه از یک مسیر/فیدر:", self.cb_joint)
        f.addRow("توضیح بررسی:", self.ed_joint_note)
        f.addRow("شاهد توپولوژیکی:", self.ed_joint_evidence)
        f.addRow("معیار صریح انتخاب سناریو:", self.ed_selection)
        v.addWidget(grp, 2)
        return page

    def _build_scenario_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel(
            "سناریوهای تأمین: Rule Engine سناریوها را تولید می‌کند و انتخاب با مهندس است؛ "
            "مسیر و هزینه هر سناریو را در همین جدول ثبت کنید."))
        self.tbl_scenarios = self._make_table(SCENARIO_COLS, min_width=100)
        self.tbl_scenarios.setMinimumHeight(200)
        v.addWidget(self.tbl_scenarios, 1)
        v.addLayout(self._row_col_bar(self.tbl_scenarios, SCENARIO_COLS, "scenarios"))
        bar = QHBoxLayout()
        b_gen = QPushButton("تولید/بازتولید سناریوها از Rule Engine")
        b_gen.setObjectName("primary")
        b_gen.clicked.connect(self.request_generate_scenarios.emit)
        b_calc = QPushButton("محاسبه برآورد پارامتریک هزینه")
        b_calc.clicked.connect(self.request_cost_estimate.emit)
        b_del = QPushButton("حذف سناریوی انتخاب‌شده")
        b_del.setObjectName("danger")
        b_del.clicked.connect(lambda: self._del_row(self.tbl_scenarios))
        bar.addWidget(b_gen)
        bar.addWidget(b_calc)
        bar.addWidget(b_del)
        bar.addStretch(1)
        v.addLayout(bar)
        self.lbl_cost_hint = QLabel(
            "برآورد پارامتریک فقط وقتی محاسبه می‌شود که پارامترهای هزینه در "
            "«تنظیمات → مطالعه و هزینه» تعریف شده باشند.")
        self.lbl_cost_hint.setObjectName("Muted")
        self.lbl_cost_hint.setWordWrap(True)
        v.addWidget(self.lbl_cost_hint)
        return page

    def _build_neighbor_tab(self) -> QWidget:
        """تب ۶ — فیدرهای همجوار (کاندید بازآرایی/انتقال بار)."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel(
            "فیدرهای همجوار برای «بازآرایی و تعدیل بار» (ردیف = فیدر). "
            "کاندید بازآرایی، فیدر همجواری است که کمترین «فاصله» ثبت‌شده را داشته باشد "
            "(در نبود فاصله، ترتیب ردیف‌ها ملاک است)."))
        self.tbl_neighbors = self._make_table(NEIGHBOR_COLS, min_width=100)
        self.tbl_neighbors.setMinimumHeight(220)
        v.addWidget(self.tbl_neighbors, 1)
        v.addLayout(self._row_col_bar(self.tbl_neighbors, NEIGHBOR_COLS, "neighbors"))

        info = QGroupBox("آستانه‌های بارگذاری فیدر (از تنظیمات — مبنای Ruleهای LD-*)")
        fi = QFormLayout(info)
        st = self.settings.study
        self.lbl_ld_crit = QLabel("—")
        self.lbl_ld_sev = QLabel("—")
        fi.addRow("بارگذاری بحرانی (پیک فیدر + بار جدید):", self.lbl_ld_crit)
        fi.addRow("بارگذاری شدیداً بحرانی:", self.lbl_ld_sev)
        note = QLabel("این دو آستانه در «تنظیمات → مطالعه و هزینه» قابل تغییرند؛ "
                      "در صورت خالی بودن، Ruleهای بارگذاری MISSING_RULE می‌شوند.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        fi.addRow("", note)
        v.addWidget(info)
        self._refresh_loading_thresholds()
        return page

    def _refresh_loading_thresholds(self) -> None:
        st = self.settings.study
        crit = fmt(st.feeder_loading_critical_mw, 2) if st.feeder_loading_critical_mw is not None else "تعریف‌نشده"
        sev = fmt(st.feeder_loading_severe_mw, 2) if st.feeder_loading_severe_mw is not None else "تعریف‌نشده"
        text = f"{crit} مگاوات و بالاتر (بحرانی)"
        text2 = f"{sev} مگاوات و بالاتر (شدیداً بحرانی)"
        for lbl, value in ((getattr(self, "lbl_ld_crit", None), text),
                           (getattr(self, "lbl_ld_sev", None), text2)):
            if lbl is not None:
                lbl.setText(value)

    # ------------------------------------------------------------------
    # جدول‌ها
    # ------------------------------------------------------------------
    def _add_row(self, table: QTableWidget) -> None:
        r = table.rowCount()
        table.insertRow(r)
        for c in range(table.columnCount()):
            header = table.horizontalHeaderItem(c)
            label = header.text() if header is not None else ""
            if label == ONOFF_COL:
                table.setItem(r, c, self._onoff_item(True))
                continue
            item = QTableWidgetItem("")
            if label in READ_ONLY_COLS:
                item.setFlags(Qt.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, c, item)
        fit_columns(table)
        self._on_item_changed()

    def _del_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "حذف ردیف", "ابتدا یک ردیف را انتخاب کنید.")
            return
        table.removeRow(row)
        fit_columns(table)
        self._on_item_changed()

    def _on_item_changed(self, *_args) -> None:
        if self._loading:
            return
        self._recalc_demand()
        self.save_to_project()
        self.changed.emit()

    # ------------------------------------------------------------------
    # بارگذاری و ذخیره
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        project = self.manager.project
        self._loading = True
        try:
            if project is None:
                return
            d = project.demand
            self.sp_without.setValue(d.without_coincidence_kw or 0.0)
            self.sp_with.setValue(d.with_coincidence_kw or 0.0)
            self.sp_existing.setValue(d.existing_demand_kw)

            self.chk_demand.setChecked(getattr(d, "enabled", True))
            self._fill_table(self.tbl_substations, [
                [s.display_name if s.name else "", s.office, s.distance_km,
                 s.transformer_capacity_mva, s.t1_loading_percent, s.t2_loading_percent,
                 s.t1_peak_mva, s.t2_peak_mva, s.feeder_count, s.peak_year]
                for s in project.nearby_substations],
                [getattr(s, "enabled", True) for s in project.nearby_substations])
            self._fill_table(self.tbl_lines, [
                [ln.display_name if ln.name else "", ln.office, ln.distance_m, ln.peak_mva,
                 ln.peak_mw, ln.peak_current_a, ln.vdrop_before_percent,
                 ln.vdrop_after_percent, ln.sc_max_ka, ln.sc_min_ka, ln.max_current_a,
                 ln.peak_year]
                for ln in project.nearby_lines],
                [getattr(ln, "enabled", True) for ln in project.nearby_lines])
            self._fill_table(self.tbl_coincident, [
                [c.name, c.existing_or_requested_power_kw, c.new_requested_power_kw,
                 c.computed_delta_kw(), c.location, c.supply_feasibility]
                for c in project.coincident_demands],
                [getattr(c, "enabled", True) for c in project.coincident_demands])
            self._fill_table(self.tbl_neighbors, [
                [n.display_name if n.name else "", n.office, n.substation, n.peak_load_mw,
                 n.capacity_mw, n.peak_current_a, n.max_current_a, n.distance_km,
                 n.transferable_mw, n.note]
                for n in getattr(project, "neighbor_feeders", [])],
                [getattr(n, "enabled", True) for n in getattr(project, "neighbor_feeders", [])])

            self.sp_reported_total.setValue(project.reported_total_additional_load_kw)
            self.sp_analysis_demand.setValue(project.demand_used_in_analysis_kw)
            self.sp_voltage.setValue(project.network_voltage_kv)
            self.cb_joint.setCurrentIndex(0 if project.joint_supply_feasible is None
                                          else (1 if project.joint_supply_feasible else 2))
            self.ed_joint_note.setText(project.joint_supply_note)
            self.ed_joint_evidence.setText(project.joint_supply_evidence)
            self.ed_selection.setText(project.scenario_selection_criterion)
            self._fill_scenarios(project)
            for table in (self.tbl_substations, self.tbl_lines,
                          self.tbl_coincident, self.tbl_scenarios,
                          self.tbl_neighbors):
                _fit_columns(table)
            self._refresh_loading_thresholds()
        finally:
            self._loading = False
        self._recalc_demand()

    def _fill_table(self, table: QTableWidget, rows: list[list],
                    enabled: list[bool] | None = None) -> None:
        """پرکردن جدول؛ ستون «در گزارش» از پرچم enabled هر ردیف ساخته می‌شود.

        ``rows`` فقط مقادیر دادهٔ مدل را دارد (بدون ستون کلید)؛ بنابراین در جدول‌های
        دارای ستون «در گزارش»، نوشتن از ستون ۱ شروع می‌شود.
        """
        table.setRowCount(0)
        start = 1 if (table.columnCount() and table.horizontalHeaderItem(0) is not None
                      and table.horizontalHeaderItem(0).text() == ONOFF_COL) else 0
        for i, row in enumerate(rows):
            r = table.rowCount()
            table.insertRow(r)
            if start == 1:
                flag = True if enabled is None else (i < len(enabled) and enabled[i])
                table.setItem(r, 0, self._onoff_item(flag))
            for c, value in enumerate(row, start=start):
                if c >= table.columnCount():
                    break
                item = QTableWidgetItem(_text(value))
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, item)

    def _fill_scenarios(self, project) -> None:
        table = self.tbl_scenarios
        table.setRowCount(0)
        for s in project.scenarios:
            est = cost_estimate(s, project, self.settings)
            row = [SCENARIO_KIND_LABELS.get(s.kind, s.kind), s.title, s.candidate_feeder,
                   s.required_line_length_km, s.overhead_percent, s.underground_percent,
                   s.estimated_cost_million, "، ".join(s.required_equipment),
                   est["estimated_total"] if est["estimated_total"] is not None else "MISSING_DATA"]
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, self._onoff_item(getattr(s, "enabled", True)))
            for c, value in enumerate(row, start=1):
                item = QTableWidgetItem(_text(value))
                item.setTextAlignment(Qt.AlignCenter)
                header = table.horizontalHeaderItem(c)
                if (header is not None and header.text() in READ_ONLY_COLS) or c == 1:
                    item.setFlags(Qt.ItemIsEnabled)
                table.setItem(r, c, item)

    # ------------------------------------------------------------------
    def save_to_project(self) -> None:
        """نوشتن مقادیر صفحه در مدل پروژه (بدون ساخت هیچ مقدار حدسی)."""
        project = self.manager.project
        if project is None or self._loading:
            return
        d = project.demand
        without = self.sp_without.value() or None
        with_ = self.sp_with.value() or None
        d.without_coincidence_kw = without
        d.with_coincidence_kw = with_
        d.existing_demand_kw = self.sp_existing.value()
        d.enabled = self.chk_demand.isChecked()      # کلید On/Off اطلاعات تقاضا

        project.nearby_substations = [self._row_to_substation(r)
                                      for r in range(self.tbl_substations.rowCount())]
        project.nearby_lines = [self._row_to_line(r)
                                for r in range(self.tbl_lines.rowCount())]
        project.coincident_demands = [self._row_to_coincident(r)
                                      for r in range(self.tbl_coincident.rowCount())]
        project.neighbor_feeders = [self._row_to_neighbor(r)
                                    for r in range(self.tbl_neighbors.rowCount())]

        project.reported_total_additional_load_kw = self.sp_reported_total.value()
        project.demand_used_in_analysis_kw = self.sp_analysis_demand.value()
        project.network_voltage_kv = self.sp_voltage.value()
        idx = self.cb_joint.currentIndex()
        project.joint_supply_feasible = None if idx == 0 else (idx == 1)
        project.joint_supply_note = self.ed_joint_note.text().strip()
        project.joint_supply_evidence = self.ed_joint_evidence.text().strip()
        project.scenario_selection_criterion = self.ed_selection.text().strip()
        self._rows_to_scenarios(project)

    # ---- ردیف → مدل (نگاشت بر مبنای عنوان ستون؛ مستقل از شمارهٔ ستون) ----
    @staticmethod
    def _cell(table: QTableWidget, r: int, c: int) -> str:
        item = table.item(r, c)
        return item.text() if item else ""

    @staticmethod
    def _col(table: QTableWidget, key: str) -> int:
        for c in range(table.columnCount()):
            head = table.horizontalHeaderItem(c)
            if head is not None and head.text() == key:
                return c
        return -1

    def _val(self, table: QTableWidget, r: int, key: str):
        """مقدار عددی خانه با عنوان ستون مشخص؛ ستون حذف‌شده ⇒ None."""
        c = self._col(table, key)
        return _num(self._cell(table, r, c)) if c >= 0 else None

    def _txt(self, table: QTableWidget, r: int, key: str) -> str:
        c = self._col(table, key)
        return self._cell(table, r, c).strip() if c >= 0 else ""

    def _row_to_substation(self, r: int) -> SubstationCandidate:
        t = self.tbl_substations
        existing = self.manager.project.nearby_substations
        uid = existing[r].uid if r < len(existing) else None
        fc, py = self._val(t, r, "تعداد فیدر"), self._val(t, r, "سال پیک")
        st = SubstationCandidate(
            name=self._txt(t, r, "نام ایستگاه"), office=self._txt(t, r, "امور/دفتر"),
            distance_km=self._val(t, r, "فاصله km"),
            transformer_capacity_mva=self._val(t, r, "ظرفیت MVA"),
            t1_loading_percent=self._val(t, r, "بارگیری T1 ٪"),
            t2_loading_percent=self._val(t, r, "بارگیری T2 ٪"),
            t1_peak_mva=self._val(t, r, "پیک T1 MVA"),
            t2_peak_mva=self._val(t, r, "پیک T2 MVA"),
            feeder_count=int(fc) if fc is not None else None,
            peak_year=int(py) if py is not None else None,
            enabled=self._enabled(t, r))
        if uid:
            st.uid = uid
        return st

    def _row_to_line(self, r: int) -> LineCandidate:
        t = self.tbl_lines
        existing = self.manager.project.nearby_lines
        uid = existing[r].uid if r < len(existing) else None
        py = self._val(t, r, "سال پیک")
        ln = LineCandidate(
            name=self._txt(t, r, "نام خط"), office=self._txt(t, r, "امور/دفتر"),
            distance_m=self._val(t, r, "فاصله m"), peak_mva=self._val(t, r, "پیک MVA"),
            peak_mw=self._val(t, r, "پیک MW"), peak_current_a=self._val(t, r, "پیک A"),
            vdrop_before_percent=self._val(t, r, "افت ولتاژ قبل ٪"),
            vdrop_after_percent=self._val(t, r, "افت ولتاژ بعد ٪"),
            sc_max_ka=self._val(t, r, "SC حداکثر kA"),
            sc_min_ka=self._val(t, r, "SC حداقل kA"),
            max_current_a=self._val(t, r, "ظرفیت هدایتی A"),
            peak_year=int(py) if py is not None else None,
            enabled=self._enabled(t, r))
        if uid:
            ln.uid = uid
        return ln

    def _row_to_coincident(self, r: int) -> CoincidentDemand:
        t = self.tbl_coincident
        existing = self.manager.project.coincident_demands
        uid = existing[r].uid if r < len(existing) else None
        cd = CoincidentDemand(
            name=self._txt(t, r, "نام متقاضی"),
            existing_or_requested_power_kw=self._val(t, r, "توان موجود/درخواستی kW"),
            new_requested_power_kw=self._val(t, r, "توان جدید kW"),
            delta_power_kw=self._val(t, r, "افزایش بار kW"),
            location=self._txt(t, r, "محل"),
            supply_feasibility=self._txt(t, r, "امکان تأمین"),
            enabled=self._enabled(t, r))
        if uid:
            cd.uid = uid
        return cd

    def _row_to_neighbor(self, r: int) -> NeighborFeeder:
        """تب ۶ — فیدر همجوار (کاندید بازآرایی)."""
        t = self.tbl_neighbors
        existing = getattr(self.manager.project, "neighbor_feeders", [])
        uid = existing[r].uid if r < len(existing) else None
        nf = NeighborFeeder(
            name=self._txt(t, r, "نام فیدر همجوار"),
            office=self._txt(t, r, "امور/دفتر"),
            substation=self._txt(t, r, "پست"),
            peak_load_mw=self._val(t, r, "پیک بار MW"),
            capacity_mw=self._val(t, r, "معیار بارگذاری MW"),
            peak_current_a=self._val(t, r, "پیک جریان A"),
            max_current_a=self._val(t, r, "حداکثر جریان مجاز A"),
            distance_km=self._val(t, r, "فاصله km"),
            transferable_mw=self._val(t, r, "بار قابل انتقال MW"),
            note=self._txt(t, r, "ملاحظات"),
            enabled=self._enabled(t, r))
        if uid:
            nf.uid = uid
        return nf

    def _rows_to_scenarios(self, project) -> None:
        t = self.tbl_scenarios
        out: list[SupplyScenario] = []
        for r in range(t.rowCount()):
            kind = next((k for k, label in SCENARIO_KIND_LABELS.items()
                         if label == self._txt(t, r, "نوع")), "new_feeder")
            scenario = next((s for s in project.scenarios if s.kind == kind), None)
            if scenario is None:
                scenario = SupplyScenario(kind=kind)
            scenario.title = self._txt(t, r, "عنوان سناریو") or scenario.title
            scenario.candidate_feeder = self._txt(t, r, "فیدر نامزد")
            scenario.required_line_length_km = self._val(t, r, "طول شبکه km")
            scenario.overhead_percent = self._val(t, r, "٪ هوایی")
            scenario.underground_percent = self._val(t, r, "٪ زمینی")
            scenario.estimated_cost_million = self._val(t, r, "هزینه (م.ت)")
            scenario.enabled = self._enabled(t, r)
            equipment = self._txt(t, r, "تجهیزات")
            scenario.required_equipment = ([x.strip() for x in equipment.split("،") if x.strip()]
                                           if equipment else scenario.required_equipment)
            out.append(scenario)
        project.scenarios = out

    # ------------------------------------------------------------------
    def _recalc_demand(self, *_args) -> None:
        """نمایش مقادیر محاسبه‌شده تقاضا (بدون ذخیره‌سازی و بدون حدس)."""
        without = self.sp_without.value() or None
        with_ = self.sp_with.value() or None
        factor = (with_ / without) if (without and with_ is not None) else None
        self.lbl_factor.setText(fmt(factor, 4) if factor is not None else "—")
        self.lbl_analysis.setText(f"{fmt(with_ or without, 0)} kW"
                                  if (with_ is not None or without is not None) else "—")
        if factor is not None and abs(factor - 1.0) < 1e-9:
            self.lbl_note.setText(
                "توجه: تقاضا با و بدون ضریب همزمانی برابر است؛ اعمال‌نشدن ضریب همزمانی "
                "با Rule «D-COINCIDENCE-NOT-APPLIED» ثبت و نیازمند تأیید مهندس است.")
        else:
            self.lbl_note.setText("")
