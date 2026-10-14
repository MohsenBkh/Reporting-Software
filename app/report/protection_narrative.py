# -*- coding: utf-8 -*-
"""موتور تولید متن گزارش‌های ریکلوزر/سکشنالایزر (Narrative Engine).

    داده‌های ورودی + نتایج Rule Engine ──► متغیرهای متن (build_vars)
                 ──► قالب‌های شرطی (protection_templates.json) ──► پاراگراف‌های دارای ارجاع

* هیچ مقدار مهندسی ساخته نمی‌شود: متغیرِ ناموجود «ناموجود» نمایش داده می‌شود و شرط قالب‌ها
  (``when``) بین جمله‌های «دارای داده» و «ناموجود» تفکیک می‌کند.
* هر پاراگراف شناسهٔ قالب و شناسهٔ Ruleهای مرتبط (``refs``) را نگه می‌دارد تا هر جمله تا
  منبع آن (Rule، سند مرجع، ورودی کاربر) ردیابی‌پذیر باشد.
* قالب‌ها در ``app/report/data/protection_templates.json`` قابل ویرایش‌اند (بدون تغییر کد).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.studies import STUDY_LABELS_FA, StudyKind
from app.core.workspace import DEVICE_FEEDER_RELAY, Workspace, resolve_study_inputs
from app.report.sections import Paragraph
from app.rules.rule_engine import safe_eval_bool

MISSING = "ناموجود"
TEMPLATES_FILE = Path(__file__).resolve().parent / "data" / "protection_templates.json"
_VAR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

# قالب ← پیشوند Ruleهای مرتبط (برای ارجاع)
REF_PREFIXES = {
    "network.": ("PCM-",), "existing.": ("REC-UP", "PCM-"), "recloser.": ("REC-SHOTS", "REC-RECLAIM", "REC-LOC", "REC-SET"),
    "sectionalizer.": ("SECZ-REF", "SECZ-COUNTER", "SECZ-SET"), "coordination.": ("REC-COORD", "REC-CURVE", "SECZ-PK", "SECZ-TMS",
                                                                                   "SECZ-COUNTER", "SECZ-DEADLINE"),
    "placement.": ("REC-PLACEMENT",), "scenario.": ("PCM-SCENARIO",), "conclusion.": ("",), "intro.": (), "recommendation.": (),
}


@dataclass
class RefParagraph(Paragraph):
    """پاراگراف دارای ارجاع به قالب و Ruleهای سازندهٔ آن (برای ردیابی)."""
    refs: list[str] = field(default_factory=list)
    template_id: str = ""


def _n(v: Optional[float], unit: str = "", fmt: str = "g") -> str:
    return MISSING if v is None else f"{format(v, fmt)}{(' ' + unit) if unit else ''}"


def _s(v: Any) -> str:
    return (str(v).strip() if v not in (None, "") else "") or MISSING


class NarrativeEngine:
    def __init__(self, templates_path: Optional[Path] = None) -> None:
        self.path = Path(templates_path) if templates_path else TEMPLATES_FILE
        self.templates: dict[str, list[dict]] = self._load()

    def _load(self) -> dict[str, list[dict]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}

    # ------------------------------------------------------------------
    def build_vars(self, project: Any, workspace: Workspace, kinds: list[StudyKind],
                   results: dict) -> dict[str, Any]:
        v: dict[str, Any] = {"true": True}
        rec_sel, secz_sel = StudyKind.RECLOSER in kinds, StudyKind.SECTIONALIZER in kinds
        v.update(rec_selected=rec_sel, secz_selected=secz_sel)
        v["studies_text"] = " و ".join(
            ("مطالعه " + STUDY_LABELS_FA[k]) for k in kinds) or MISSING
        names: list[str] = []
        for k in kinds:
            for n in workspace.scope(k):
                if n not in names:
                    names.append(n)
            fn = getattr(getattr(project, k.value), "feeder_name", "")
            if fn and fn not in names:
                names.append(fn)
        v["feeders_text"] = "، ".join(names) or MISSING
        # شبکهٔ مشترک (اولین فیدر)
        common = next((workspace.common_network.feeder(n) for n in names
                       if workspace.common_network.feeder(n) is not None), None)
        sub = (common.substation if common else "") or getattr(project, "substation", "")
        v["substation"] = _s(sub)
        v["substation_clause"] = f" (پست {sub})" if sub else ""
        v["substation_from"] = f" از پست {sub}" if sub else ""
        volt = common.voltage_kv if common else getattr(project, "network_voltage_kv", None)
        v["voltage_clause"] = f" با سطح ولتاژ {_n(volt, 'کیلوولت')}" if volt is not None else ""
        sc3 = common.max_fault_current_ka if common else None
        sc1 = common.sc_1ph_ka if common else None
        first_kind = kinds[0] if kinds else StudyKind.RECLOSER
        inp = resolve_study_inputs(project, workspace, first_kind)
        sc3 = sc3 if sc3 is not None else inp["fault_current_ka"].value
        load = inp["load_current_a"].value
        v.update(has_sc3=sc3 is not None, sc3=_n(sc3), has_load=load is not None, load=_n(load))
        v["sc1_clause"] = f" و تکفاز {_n(sc1)} کیلوآمپر" if sc1 is not None else ""
        v["has_report_number"] = bool(getattr(project, "report_number", ""))
        v["report_number"] = _s(getattr(project, "report_number", ""))
        date = getattr(project, "date_jalali", "")
        v["date_clause"] = f" به تاریخ {date}" if date else ""
        # منابع تولید پراکنده
        dg = common.has_dg if common else None
        v["dg_known"] = dg is not None
        v["dg_text"] = ("روی فیدر منبع تولید پراکنده وجود ندارد." if dg is False else
                        f"روی فیدر منبع تولید پراکنده وجود دارد ({_s(common.dg_note)}); اثر آن بر جریان خطا "
                        "و هماهنگی حفاظتی باید بررسی شود." if dg else "")
        # حفاظت موجود
        relay = common.device(DEVICE_FEEDER_RELAY) if common else None
        v["has_relay"] = bool(relay and relay.settings.any_function_set())
        others = [d for d in (common.existing_protection if common else [])
                  if d.device_type != DEVICE_FEEDER_RELAY]
        v["has_other_devices"] = bool(others)
        v["others_text"] = "، ".join(f"{d.name or d.device_type}" + (f" ({d.location})" if d.location else "")
                                    for d in others)
        # ریکلوزر / سکشنالایزر
        rec, secz = getattr(project, "recloser", None), getattr(project, "sectionalizer", None)
        rs = getattr(rec, "settings", None)
        ss = getattr(secz, "settings", None)
        v.update(rec_name=_s(getattr(rec, "name", "")), rec_location=_s(getattr(rec, "installation_location", "")),
                 rec_feeder=_s(getattr(rec, "feeder_name", "")), rec_objective=_s(getattr(rec, "objective", "")),
                 has_rec_shots=bool(rs and rs.shots is not None),
                 rec_shots=_n(getattr(rs, "shots", None)),
                 rec_dead_times=("، ".join(f"{t:g} ثانیه" for t in rs.dead_times_s) if rs and rs.dead_times_s else MISSING),
                 rec_reclaim=_n(getattr(rs, "reclaim_time_s", None), "ثانیه"))
        v.update(secz_name=_s(getattr(secz, "name", "")), secz_location=_s(getattr(secz, "installation_location", "")),
                 secz_feeder=_s(getattr(secz, "feeder_name", "")), secz_objective=_s(getattr(secz, "objective", "")),
                 has_secz_counter=bool(ss and ss.counter is not None), secz_counter=_n(getattr(ss, "counter", None)))
        ref_name = ""
        if secz_sel:
            sin = resolve_study_inputs(project, workspace, StudyKind.SECTIONALIZER)
            ref_name = sin["upstream_ref"] or ""
        v.update(has_secz_ref=bool(ref_name), secz_ref=_s(ref_name))
        shots_ref = rs.shots if rs else None
        cvs = ""
        if ss and ss.counter is not None and shots_ref is not None:
            cvs = (f" و با تعداد شات ریکلوزر ({shots_ref}) برابر است" if ss.counter == shots_ref
                   else f" و با تعداد شات ریکلوزر ({shots_ref}) برابر نیست")
        v["counter_vs_shots"] = cvs
        up_ref = resolve_study_inputs(project, workspace, StudyKind.RECLOSER)["upstream_ref"] if rec_sel else None
        v["up_ref"] = _s(up_ref)
        placement = getattr(rec, "placement_basis", "") if rec is not None else ""
        v.update(has_placement=bool(placement), placement_text=_s(placement))
        normal = "؛ ".join(dict.fromkeys(n.normal_scenario.strip() for n in
                                          (workspace.common_network.feeder(x) for x in names) if n and n.normal_scenario.strip()))
        emerg = "؛ ".join(dict.fromkeys(n.emergency_scenario.strip() for n in
                                         (workspace.common_network.feeder(x) for x in names) if n and n.emergency_scenario.strip()))
        v.update(has_normal=bool(normal), normal_scenario=normal, has_emergency=bool(emerg), emergency_scenario=emerg)
        parts = []
        if v["has_rec_shots"]:
            parts.append(f"ریکلوزر در برابر خطای پایدار حداکثر {v['rec_shots']} بار وصل مجدد انجام می‌دهد")
        if v["has_secz_counter"]:
            parts.append(f"سکشنالایزر با شمارندهٔ {v['secz_counter']} پس از شمارش قطع‌های ریکلوزر در حالت "
                         "بی‌برقی خط (Dead line) فرمان باز شدن می‌دهد")
        v["derived_scenario"] = ("؛ ".join(parts) + ".") if parts else ""
        v.update(self._result_vars(results))
        return v

    @staticmethod
    def _result_vars(results: dict) -> dict[str, Any]:
        allr = [r for rows in results.values() for r in rows]
        by = lambda st: [r for r in allr if r.status == st]          # noqa: E731
        key = lambda r: getattr(r, "rule_key", "")                   # noqa: E731
        rc = [r for r in allr if key(r).startswith("REC-COORD")]
        sz = [r for r in allr if key(r).startswith(("SECZ-PK", "SECZ-TMS", "SECZ-COUNTER", "SECZ-DEADLINE"))]
        miss_rule = []
        for r in by("MISSING_RULE"):
            for t in (getattr(r, "thresholds", None) or {}).values():
                if t.get("value") is None and t.get("label") and t["label"] not in miss_rule:
                    miss_rule.append(t["label"])
        uniq = lambda xs: list(dict.fromkeys(xs))                    # noqa: E731
        return {
            "n_total": len(allr), "n_pass": len(by("PASS")), "n_warn": len(by("WARNING")),
            "n_fail": len(by("FAIL")), "n_missing_data": len(by("MISSING_DATA")),
            "n_missing_rule": len(by("MISSING_RULE")),
            "n_review": sum(1 for r in allr if r.engineer_review_required),
            "fail_text": "؛ ".join(uniq(r.rule_name or r.finding for r in by("FAIL"))),
            "missing_text": "، ".join(uniq((r.rule_name or "").replace(" ثبت نشده", "") for r in by("MISSING_DATA"))),
            "missing_rule_text": "، ".join(miss_rule),
            "rec_coord_total": len(rc), "rec_coord_bad": sum(1 for r in rc if r.status == "FAIL"),
            "secz_total": len(sz), "secz_ok": sum(1 for r in sz if r.status == "PASS"),
            "secz_dev": sum(1 for r in sz if r.status == "WARNING"),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def render(text: str, vars_: dict[str, Any]) -> str:
        return _VAR.sub(lambda m: str(vars_.get(m.group(1), MISSING)), text)

    def refs_for(self, template_id: str, results: dict) -> list[str]:
        prefix = next((p for p in REF_PREFIXES if template_id.startswith(p)), "")
        wanted = REF_PREFIXES.get(prefix, ())
        allr = [r for rows in results.values() for r in rows]
        if template_id.startswith("conclusion."):
            return [r.rule_key for r in allr if r.status != "PASS"][:30]
        return [r.rule_key for r in allr if wanted and r.rule_key.startswith(wanted)]

    def section(self, key: str, vars_: dict[str, Any], results: dict) -> list[RefParagraph]:
        out: list[RefParagraph] = []
        for t in self.templates.get(key, []):
            if not safe_eval_bool(t.get("when", "true"), vars_):
                continue
            text = self.render(t.get("text", ""), vars_).strip()
            if text:
                out.append(RefParagraph(text=text, refs=self.refs_for(t["id"], results),
                                        template_id=t["id"]))
        return out
