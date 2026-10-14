# -*- coding: utf-8 -*-
"""ساخت «بستهٔ ارسال» برای هوش مصنوعی: همهٔ ورودی‌های لازم + یافته‌ها + تصاویر + دستورالعمل.

بسته به‌صورت ZIP قابل ذخیره است (برای بایگانی، بازرسی یا بارگذاری دستی در هر ابزار هوش مصنوعی)
و همان محتوا برای ارسال مستقیم به API استفاده می‌شود.
"""
from __future__ import annotations

import io
import json
import mimetypes
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.ai.settings import AISettings
from app.core.models import to_dict
from app.report.sections import FigureBlock, Paragraph, TableSpec

PEOPLE_FIELDS = ("applicant_name", "expert_name")
REDACTED = "[حذف‌شده برای حریم خصوصی]"


@dataclass
class SectionText:
    key: str
    title: str
    text: str
    manual: bool = False


@dataclass
class AIPackage:
    files: dict[str, bytes] = field(default_factory=dict)         # مسیر در ZIP ← محتوا
    images: list[tuple[str, bytes, str, dict]] = field(default_factory=list)  # (نام، بایت، mime، متا)
    sections: list[SectionText] = field(default_factory=list)
    requested: list[str] = field(default_factory=list)
    data_text: str = ""                                            # JSON داده‌ها برای پیام API
    warnings: list[str] = field(default_factory=list)

    @property
    def n_images(self) -> int:
        return len(self.images)

    @property
    def size_bytes(self) -> int:
        return sum(len(v) for v in self.files.values())

    def summary(self) -> str:
        return (f"{len(self.requested)} بخش برای اصلاح، {self.n_images} تصویر، "
                f"{len(self.files)} فایل، حدود {self.size_bytes / 1024:.0f} کیلوبایت")

    def to_zip(self, path: Path | str) -> Path:
        path = Path(path)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in self.files.items():
                z.writestr(name, data)
        return path

    def to_zip_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in self.files.items():
                z.writestr(name, data)
        return buf.getvalue()


def sections_from_report(report: Any) -> list[SectionText]:
    """متن فعلی هر بخش گزارش (پاراگراف‌ها + خلاصهٔ جدول‌ها) — همان چیزی که کاربر در گزارش می‌بیند."""
    out = []
    for sec in report.sections:
        lines = []
        for b in sec.blocks:
            if isinstance(b, Paragraph):
                lines.append(b.text)
            elif isinstance(b, TableSpec):
                lines.append(f"[{b.caption}]")
                for row in list(b.header_rows) + list(b.body_rows):
                    lines.append(" | ".join(str(c) for c in row))
            elif isinstance(b, FigureBlock):
                lines.append(f"[شکل: {b.caption}]")
        out.append(SectionText(sec.key, sec.title, "\n".join(lines), bool(getattr(sec, "manual", False))))
    return out


def _sanitize_project(project: Any, anonymize: bool) -> dict:
    d = to_dict(project)
    d.pop("last_report_path", None)           # مسیر محلی کاربر ارسال نشود
    d.pop("uid", None)
    if anonymize:
        for f in PEOPLE_FIELDS:
            if d.get(f):
                d[f] = REDACTED
    return d


def _findings_json(results: Optional[dict]) -> list[dict]:
    from app.rules.trace import trace_link
    out = []
    for kind, rows in (results or {}).items():
        for r in rows:
            t = trace_link(r, kind)
            out.append({"study": getattr(kind, "value", str(kind)), "rule": r.rule_key,
                        "status": r.status, "finding": r.finding, "evidence": r.evidence,
                        "source": r.source, "source_page": r.source_page,
                        "missing": list(r.missing or []), "needs_engineer_review": r.engineer_review_required,
                        "fix_location": f"{t.route} ← {t.field}" if t.route else ""})
    return out


def _prepare_image(path: Path, max_kb: int) -> Optional[tuple[bytes, str]]:
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    if len(data) <= max_kb * 1024:
        return data, mime
    try:                                       # کوچک‌سازی با Pillow در صورت وجود
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        if len(buf.getvalue()) <= max_kb * 1024:
            return buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001
        pass
    return None


def build_package(project: Any, workspace: Any, report: Any, results: Optional[dict],
                  ai: AISettings, image_resolver: Optional[Callable] = None,
                  selected_keys: Optional[list[str]] = None) -> AIPackage:
    pkg = AIPackage()
    pkg.sections = sections_from_report(report)
    known = {s.key for s in pkg.sections}
    pkg.requested = [k for k in (selected_keys if selected_keys is not None else
                                 [s.key for s in pkg.sections]) if k in known]
    sections_json = {s.key: {"title": s.title, "current_text": s.text, "manual_edit": s.manual,
                             "requested": s.key in pkg.requested} for s in pkg.sections}
    proj = _sanitize_project(project, ai.anonymize_people)
    work = workspace.to_dict() if workspace is not None else {}
    finds = _findings_json(results) if ai.include_findings else []

    def dump(o):
        return json.dumps(o, ensure_ascii=False, indent=2).encode("utf-8")

    pkg.files["project.json"] = dump(proj)
    pkg.files["workspace.json"] = dump(work)
    pkg.files["findings.json"] = dump(finds)
    pkg.files["sections.json"] = dump(sections_json)

    imgs_meta = []
    if ai.send_images and image_resolver is not None:
        for img in [i for i in getattr(project, "active_images", [])][: max(0, ai.max_images)]:
            path = image_resolver(img)
            if not path:
                continue
            prepared = _prepare_image(Path(path), ai.max_image_kb)
            if prepared is None:
                pkg.warnings.append(f"تصویر «{img.title or img.file_name}» بزرگ است و ارسال نشد.")
                continue
            data, mime = prepared
            ext = mimetypes.guess_extension(mime) or ".png"
            name = f"images/{len(pkg.images) + 1:02d}_{img.kind}{ext}"
            meta = {"file": name, "title": img.title, "caption": img.caption, "kind": img.kind,
                    "section": img.section_key}
            pkg.images.append((name, data, mime, meta))
            pkg.files[name] = data
            imgs_meta.append(meta)
    pkg.files["images.json"] = dump(imgs_meta)
    pkg.data_text = json.dumps({"project": proj, "workspace": work, "findings": finds,
                                "sections": sections_json, "images": imgs_meta},
                               ensure_ascii=False)
    task = (f"# دستورالعمل\n\n{ai.instructions}\n\n## بخش‌های درخواست‌شده\n"
            + "\n".join(f"- {k}" for k in pkg.requested)
            + "\n\n## فایل‌ها\n- project.json، workspace.json: ورودی‌ها\n- findings.json: یافته‌های موتور قواعد "
              "(با منبع و محل اصلاح)\n- sections.json: متن فعلی بخش‌ها\n- images/: تصاویر پروژه\n")
    pkg.files["task.md"] = task.encode("utf-8")
    pkg.files["manifest.json"] = dump({"format": "reportforge-ai-package/1", "requested": pkg.requested,
                                        "anonymized": ai.anonymize_people, "n_images": pkg.n_images,
                                        "warnings": pkg.warnings})
    return pkg
