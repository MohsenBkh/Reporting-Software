# -*- coding: utf-8 -*-
"""Workspace پروژه: انتخاب مطالعات + داده مشترک شبکه (Common Network) + ترجیحات گزارش.

ذخیره در ``workspace.json`` کنار ``project.json`` انجام می‌شود تا
* ``project.json`` و ساختار قدیمی (``report_type`` / ``recloser`` / ``sectionalizer``) دست‌نخورده بماند،
* پروژه‌های قدیمی بدون فایل Workspace با مهاجرت خودکار باز شوند،
* ``Project`` به God Class تبدیل نشود.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.protection_models import ProtectionSettings
from app.core.studies import StudyKind, StudySelection, selection_from_legacy

WORKSPACE_FILE = "workspace.json"
SCHEMA_VERSION = 1

OUTPUT_COMBINED = "combined"
OUTPUT_SEPARATE = "separate"

DEVICE_FEEDER_RELAY = "feeder_relay"
DEVICE_RECLOSER = "recloser"
DEVICE_SECTIONALIZER = "sectionalizer"
DEVICE_FUSE = "fuse"


def _norm(name: str) -> str:
    return " ".join((name or "").replace("‌", " ").split()).casefold()


@dataclass
class ExistingProtectionDevice:
    """تجهیز حفاظتی موجود روی فیدر (مثلاً رله سر فیدر)."""

    name: str = ""
    device_type: str = DEVICE_FEEDER_RELAY
    location: str = ""
    settings: ProtectionSettings = field(default_factory=ProtectionSettings)
    source: str = ""        # مثلاً «برق منطقه‌ای» / فایل DIgSILENT


@dataclass
class FeederNetworkData:
    """داده مشترک یک فیدر — یک‌بار ثبت و برای همه مطالعات استفاده می‌شود."""

    name: str = ""
    substation: str = ""
    voltage_kv: Optional[float] = None
    load_current_a: Optional[float] = None
    max_fault_current_ka: Optional[float] = None   # سطح اتصال کوتاه سه‌فاز پست (kA)
    min_fault_current_ka: Optional[float] = None
    sc_1ph_ka: Optional[float] = None              # سطح اتصال کوتاه تکفاز پست (kA)
    has_dg: Optional[bool] = None                  # منابع تولید پراکنده: None = نامشخص
    dg_note: str = ""
    normal_scenario: str = ""                      # سناریوی بهره‌برداری عادی
    emergency_scenario: str = ""                   # سناریوی بهره‌برداری اضطراری
    topology_note: str = ""
    powerflow_note: str = ""
    source: str = ""        # MANUAL | DIGSILENT:<file> | ...
    existing_protection: list[ExistingProtectionDevice] = field(default_factory=list)

    def device(self, device_type: str) -> Optional[ExistingProtectionDevice]:
        for d in self.existing_protection:
            if d.device_type == device_type:
                return d
        return None


@dataclass
class CommonNetwork:
    feeders: list[FeederNetworkData] = field(default_factory=list)

    def feeder(self, name: str) -> Optional[FeederNetworkData]:
        key = _norm(name)
        if not key:
            return None
        for f in self.feeders:
            if _norm(f.name) == key:
                return f
        return None

    def upsert(self, data: FeederNetworkData) -> FeederNetworkData:
        existing = self.feeder(data.name)
        if existing is None:
            self.feeders.append(data)
            return data
        self.feeders[self.feeders.index(existing)] = data
        return data


@dataclass
class ReportPreferences:
    output_mode: str = OUTPUT_COMBINED          # برای مطالعات حفاظتی
    section_order: list[str] = field(default_factory=list)   # خالی = ترتیب پیش‌فرض Composer
    # پیوست ردیابی به‌صورت پیش‌فرض خاموش است (در Report Center روشن می‌شود)
    disabled_sections: list[str] = field(default_factory=lambda: ["prot_trace"])


@dataclass
class Workspace:
    schema_version: int = SCHEMA_VERSION
    selection: StudySelection = field(default_factory=StudySelection)
    common_network: CommonNetwork = field(default_factory=CommonNetwork)
    report_prefs: ReportPreferences = field(default_factory=ReportPreferences)
    # محدودهٔ فیدرهای هر مطالعه: {"recloser": ["F4", ...], "sectionalizer": [...]}
    study_scopes: dict[str, list[str]] = field(default_factory=dict)
    # Guided Flow (v2.0.0): مراحل تأییدشده/ردشده توسط کاربر و آخرین تصویر فرایند
    flow_done: list[str] = field(default_factory=list)        # مثلاً "analysis", "review", "preview"
    flow_overrides: list[str] = field(default_factory=list)   # مراحلی که کاربر با نقص رد کرده است

    def mark_done(self, step: str) -> None:
        if step not in self.flow_done:
            self.flow_done.append(step)

    def clear_done(self, *steps: str) -> None:
        self.flow_done = [s for s in self.flow_done if s not in steps]

    def override(self, step: str, on: bool = True) -> None:
        self.flow_overrides = [s for s in self.flow_overrides if s != step]
        if on:
            self.flow_overrides.append(step)

    def scope(self, kind: str) -> list[str]:
        """نام فیدرهای محدودهٔ مطالعه (kind = recloser | sectionalizer)."""
        return self.study_scopes.setdefault(str(getattr(kind, "value", kind)), [])

    def add_to_scope(self, kind: str, feeder_name: str) -> None:
        names = self.scope(kind)
        if feeder_name and all(_norm(n) != _norm(feeder_name) for n in names):
            names.append(feeder_name)
            if self.common_network.feeder(feeder_name) is None:
                self.common_network.upsert(FeederNetworkData(name=feeder_name, source="MANUAL"))

    def remove_from_scope(self, kind: str, feeder_name: str) -> None:
        names = self.scope(kind)
        names[:] = [n for n in names if _norm(n) != _norm(feeder_name)]

    # --- سریال‌سازی ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Workspace":
        data = data or {}
        ws = cls(schema_version=int(data.get("schema_version", SCHEMA_VERSION)))
        ws.selection = StudySelection.from_dict(data.get("selection"))
        prefs = data.get("report_prefs") or {}
        ws.report_prefs = ReportPreferences(
            output_mode=prefs.get("output_mode", OUTPUT_COMBINED),
            section_order=list(prefs.get("section_order", [])),
            disabled_sections=list(prefs.get("disabled_sections", ["prot_trace"])))
        for fd in (data.get("common_network") or {}).get("feeders", []):
            ws.common_network.feeders.append(_feeder_from_dict(fd))
        ws.flow_done = [str(x) for x in (data.get("flow_done") or [])]
        ws.flow_overrides = [str(x) for x in (data.get("flow_overrides") or [])]
        raw_scopes = data.get("study_scopes") or {}
        ws.study_scopes = {str(k): [str(n) for n in v] for k, v in raw_scopes.items()
                           if isinstance(v, list)}
        return ws

    def save(self, project_dir: Path | str) -> Path:
        path = Path(project_dir) / WORKSPACE_FILE
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path


def _feeder_from_dict(fd: dict) -> FeederNetworkData:
    known = {f.name for f in dataclasses.fields(FeederNetworkData)} - {"existing_protection"}
    obj = FeederNetworkData(**{k: v for k, v in fd.items() if k in known})
    for dv in fd.get("existing_protection", []) or []:
        obj.existing_protection.append(ExistingProtectionDevice(
            name=dv.get("name", ""), device_type=dv.get("device_type", DEVICE_FEEDER_RELAY),
            location=dv.get("location", ""), source=dv.get("source", ""),
            settings=ProtectionSettings.from_dict(dv.get("settings"))))
    return obj


# ---------------------------------------------------------------------------
# مهاجرت و بارگذاری
# ---------------------------------------------------------------------------
def workspace_from_project(project: Any) -> Workspace:
    """ساخت Workspace برای پروژهٔ قدیمی (بدون workspace.json).

    * انتخاب مطالعات از ``report_type`` مشتق می‌شود.
    * Common Network از فیدرهای موجود پروژه ساخته می‌شود؛ فقط داده‌ای که واقعاً
      در پروژه هست منتقل می‌شود (جریان پیک فیدر = جریان بار).
    """
    ws = Workspace(selection=selection_from_legacy(getattr(project, "report_type", None)))
    voltage = getattr(project, "network_voltage_kv", None)
    for f in getattr(project, "feeders", []) or []:
        if not getattr(f, "name", ""):
            continue
        ws.common_network.upsert(FeederNetworkData(
            name=f.name, substation=getattr(f, "substation", "") or "",
            voltage_kv=voltage, load_current_a=getattr(f, "peak_current_a", None),
            source="MIGRATED:project.feeders"))
    for kind in ("recloser", "sectionalizer"):
        info = getattr(project, kind, None)
        name = getattr(info, "feeder_name", "") if info is not None else ""
        if name:
            ws.add_to_scope(kind, name)
    return ws


def load_workspace(project_dir: Path | str, project: Any) -> Workspace:
    """بارگذاری ``workspace.json``؛ در نبود یا خرابی فایل، مهاجرت از پروژه."""
    path = Path(project_dir) / WORKSPACE_FILE
    if path.exists():
        try:
            return Workspace.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return workspace_from_project(project)


# ---------------------------------------------------------------------------
# تجمیع ورودی‌های مطالعه از «مطالعه + شبکه مشترک»
# ---------------------------------------------------------------------------
@dataclass
class Resolved:
    value: Any = None
    source: str = "missing"      # study | common | missing

    @property
    def present(self) -> bool:
        return self.value is not None


def _pick(study_value: Any, common_value: Any) -> Resolved:
    if study_value not in (None, ""):
        return Resolved(study_value, "study")
    if common_value not in (None, ""):
        return Resolved(common_value, "common")
    return Resolved(None, "missing")


def resolve_study_inputs(project: Any, workspace: Workspace, kind: StudyKind) -> dict[str, Any]:
    """ورودی‌های مطالعه؛ مقدار ثبت‌شدهٔ خود مطالعه بر شبکهٔ مشترک اولویت دارد.

    خروجی شامل ``Resolved`` برای هر ورودی و ``upstream_settings`` (ProtectionSettings
    یا None) به‌همراه نام مرجع آن است. هیچ مقداری ساخته یا حدس زده نمی‌شود.
    """
    kind = StudyKind(kind)
    info = getattr(project, kind.value)
    feeder_name = getattr(info, "feeder_name", "") or ""
    common = workspace.common_network.feeder(feeder_name)

    out: dict[str, Any] = {
        "feeder_name": Resolved(feeder_name or None, "study" if feeder_name else "missing"),
        "common_feeder": common,
        "fault_current_ka": _pick(getattr(info, "fault_current_ka", None),
                                  common.max_fault_current_ka if common else None),
        "min_fault_current_ka": _pick(getattr(info, "min_fault_current_ka", None),
                                      common.min_fault_current_ka if common else None),
        "load_current_a": _pick(getattr(info, "load_current_a", None),
                                common.load_current_a if common else None),
        "voltage_kv": _pick(getattr(info, "nominal_voltage_kv", None),
                            common.voltage_kv if common else None),
    }
    settings, ref_name = _upstream(project, kind, info, common)
    out["upstream_settings"] = settings
    out["upstream_ref"] = ref_name
    return out


def _upstream(project: Any, kind: StudyKind, info: Any,
              common: Optional[FeederNetworkData]) -> tuple[Optional[ProtectionSettings], Optional[str]]:
    """مرجع بالادست: ریکلوزر ← رله سر فیدر؛ سکشنالایزر ← ریکلوزر."""
    if kind is StudyKind.RECLOSER:
        own = getattr(info, "upstream_settings", None)
        if own is not None and own.any_function_set():
            return own, getattr(info, "upstream_device", "") or "تجهیز بالادست (ورودی مطالعه)"
        dev = common.device(DEVICE_FEEDER_RELAY) if common else None
        if dev is not None and dev.settings.any_function_set():
            return dev.settings, dev.name or "رله سر فیدر (شبکه مشترک)"
        return None, None
    own = getattr(info, "reference_recloser_settings", None)
    if own is not None and own.any_function_set():
        return own, "ریکلوزر مرجع (ورودی مطالعه)"
    if getattr(info, "link_to_project_recloser", True):
        rec = getattr(project, "recloser", None)
        rec_settings = getattr(rec, "settings", None)
        if rec_settings is not None and rec_settings.any_function_set():
            return rec_settings, getattr(rec, "name", "") or "ریکلوزر پروژه"
    dev = common.device(DEVICE_RECLOSER) if common else None
    if dev is not None and dev.settings.any_function_set():
        return dev.settings, dev.name or "ریکلوزر موجود (شبکه مشترک)"
    return None, None


def load_workspace_for(project: Any) -> Workspace:
    """Workspace بدون مسیر پروژه (مثلاً در تست/Preview): مهاجرت مستقیم از پروژه.

    اگر پروژه ``report_type`` ریکلوزر/سکشنالایزر دارد همان مطالعه انتخاب می‌شود؛ برای
    ساخت گزارش ترکیبی ابتدا ``workspace.selection`` را صریحاً تنظیم کنید.
    """
    return workspace_from_project(project)
