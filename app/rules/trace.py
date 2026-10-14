# -*- coding: utf-8 -*-
"""ردیابی دقیق یافته‌ها: هر نتیجهٔ Rule به «محل ورود داده» و «سند منبع» ارجاع دارد (v2.0.0).

``TraceLink`` شامل:
  * ``route`` + ``field``  — صفحهٔ ورود داده و فیلد دقیق که باید اصلاح شود (قابل کلیک در UI)
  * ``rule_id`` + ``source`` + ``source_page`` — Rule و سند/صفحه‌ای که قاعده از آن آمده
  * ``values`` — مقادیر ورودی که Rule با آن‌ها ارزیابی شده (برای ردیابی محاسبه)
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Optional

from app.core.studies import StudyKind

# نام داده‌ی ناموجود در Rule ← (صفحهٔ ورود داده، فیلد)  — «{k}» = نوع مطالعه
FIELD_TARGETS: dict[str, tuple[str, str]] = {
    "feeder_name": ("{k}.network", "feeders"),
    "fault_current_ka": ("{k}.network", "sc3"),
    "min_fault_current_ka": ("{k}.device", "min_fault_current_ka"),
    "load_current_a": ("{k}.network", "load"),
    "installation_location": ("{k}.device", "installation_location"),
    "placement_basis": ("{k}.device", "objective"),
    "protection_functions": ("{k}.settings", "f51.pickup_a"),
    "upstream_settings_ref": ("{k}.network", "relay"),
    "reference_ref": ("{k}.settings", "reference"),
    "dg_status": ("{k}.network", "dg"),
    "operating_scenarios": ("{k}.network", "scenarios"),
}
# پیشوند شناسهٔ Rule ← (صفحه، فیلد) برای یافته‌های محاسباتی
RULE_TARGETS: list[tuple[str, tuple[str, str]]] = [
    ("REC-COORD-51N", ("{k}.settings", "f51n.pickup_a")), ("REC-COORD-50N", ("{k}.settings", "f50n.pickup_a")),
    ("REC-COORD-51", ("{k}.settings", "f51.pickup_a")), ("REC-COORD-50", ("{k}.settings", "f50.pickup_a")),
    ("REC-RECLAIM", ("{k}.settings", "reclaim")), ("REC-SHOTS", ("{k}.settings", "shots")),
    ("REC-SENS", ("{k}.settings", "f51.pickup_a")), ("REC-LOADMARGIN", ("{k}.settings", "f51.pickup_a")),
    ("REC-PICKUP", ("{k}.settings", "f51.pickup_a")), ("REC-INST", ("{k}.settings", "f50.pickup_a")),
    ("SECZ-PK-51N", ("{k}.settings", "f51n.pickup_a")), ("SECZ-PK-50N", ("{k}.settings", "f50n.pickup_a")),
    ("SECZ-PK-51", ("{k}.settings", "f51.pickup_a")), ("SECZ-PK-50", ("{k}.settings", "f50.pickup_a")),
    ("SECZ-TMS-51N", ("{k}.settings", "f51n.time_value")), ("SECZ-TMS-51", ("{k}.settings", "f51.time_value")),
    ("SECZ-COUNTER", ("{k}.settings", "counter")), ("SECZ-DEADLINE", ("{k}.settings", "dead_line")),
    ("PCM-NO-COMMON", ("{k}.network", "feeders")), ("PCM-DG", ("{k}.network", "dg")),
    ("PCM-SCENARIO", ("{k}.network", "scenarios")),
    ("REC-PLACEMENT", ("{k}.device", "objective")),
]


@dataclass
class TraceLink:
    route: str = ""
    field: str = ""
    rule_id: str = ""
    label: str = ""
    source: str = ""
    source_page: str = ""
    values: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def has_target(self) -> bool:
        return bool(self.route)

    def to_text(self) -> str:
        parts = [f"قاعده {self.rule_id}"]
        if self.route:
            parts.append(f"محل اصلاح: {self.route} ← {self.field or '—'}")
        if self.source:
            parts.append(f"منبع: {self.source}" + (f" — {self.source_page}" if self.source_page else ""))
        return " | ".join(parts)


def _fill(pair: tuple[str, str], kind: StudyKind) -> tuple[str, str]:
    return pair[0].format(k=StudyKind(kind).value), pair[1]


def trace_link(result: Any, kind: StudyKind) -> TraceLink:
    """لینک دقیق برای یک ``RuleResult``؛ ابتدا داده‌ی ناموجود، سپس شناسهٔ Rule."""
    route = fld = ""
    for key in (getattr(result, "missing", None) or []):
        if key in FIELD_TARGETS:
            route, fld = _fill(FIELD_TARGETS[key], kind)
            break
    if not route:
        rid = getattr(result, "rule_key", "") or getattr(result, "rule_id", "")
        for prefix, pair in RULE_TARGETS:
            if rid.startswith(prefix):
                route, fld = _fill(pair, kind)
                break
    values = {}
    for src in (getattr(result, "input_values", None), getattr(result, "calculated_values", None)):
        for k, v in (src or {}).items():
            values[k] = v
    return TraceLink(route=route, field=fld,
                     rule_id=getattr(result, "rule_key", "") or getattr(result, "rule_id", ""),
                     label=getattr(result, "rule_name", ""), source=getattr(result, "source", ""),
                     source_page=getattr(result, "source_page", ""), values=values)
