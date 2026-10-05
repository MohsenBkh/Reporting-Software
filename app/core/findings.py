# -*- coding: utf-8 -*-
"""Finding ها و تصمیمات بازبینی مهندس (Engineer Review) — v1.0.3.

هر نتیجه‌گیری مهندسی که از Rule Engine می‌آید یک Finding است. مهندس می‌تواند آن را
Accept / Edit / Reject / Override کند و Comment بگذارد. تصمیمات در project.reviews
ذخیره می‌شوند و هنگام Generate مجدد حفظ می‌گردند. کلید Finding پایدار است:
«<domain>:<feeder_uid>» یا «conclusion».
هوش مصنوعی هیچ تصمیم مهندسی نمی‌گیرد؛ فقط Rule Engine + تصمیم مهندس.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.models import (Project, ReviewDecision, REVIEW_ACCEPTED,
                             REVIEW_EDITED, REVIEW_OVERRIDDEN, REVIEW_PENDING,
                             REVIEW_REJECTED)

SEV_NORMAL = "normal"
SEV_WARNING = "warning"
SEV_ERROR = "error"
SEV_REVIEW = "review"

SEVERITY_LABELS = {SEV_NORMAL: "Normal", SEV_WARNING: "Warning",
                   SEV_ERROR: "Error", SEV_REVIEW: "Requires Review"}
SEVERITY_LABELS_FA = {SEV_NORMAL: "عادی", SEV_WARNING: "هشدار",
                      SEV_ERROR: "خطا", SEV_REVIEW: "نیازمند بررسی"}
STATUS_LABELS_FA = {REVIEW_PENDING: "در انتظار بازبینی", REVIEW_ACCEPTED: "تأیید شده",
                    REVIEW_EDITED: "ویرایش شده", REVIEW_REJECTED: "رد شده",
                    REVIEW_OVERRIDDEN: "Override شده"}
DOMAIN_LABELS_FA = {"loading": "بارگذاری", "after_voltage": "ولتاژ", "current": "جریان",
                    "loss": "تلفات", "forecast": "پیش‌بینی", "conclusion": "نتیجه‌گیری و پیشنهادات"}


_REF_RE = re.compile(r"(شکل|جدول)(‌?های)?\s*[\d۰-۹—،و\s]+")


def text_hash(text: str) -> str:
    """خلاصه متن خودکار؛ شماره شکل/جدول نادیده گرفته می‌شود تا افزودن تصویر
    باعث «کهنه» شدن تصمیم مهندس نشود (ولی تغییر اعداد فنی کهنه‌شدن را نشان می‌دهد)."""
    norm = _REF_RE.sub(r"\1 #", text or "")
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def finding_key(domain: str, feeder_uid: str = "") -> str:
    return f"{domain}:{feeder_uid}" if feeder_uid else domain


@dataclass
class Finding:
    key: str
    domain: str
    feeder_name: str
    rule_id: str
    rule_name: str
    severity: str
    auto_text: str                 # متن تولیدشده از Rule + Template
    status: str = REVIEW_PENDING
    comment: str = ""
    final_text: str = ""           # متنی که در گزارش می‌آید ("" = حذف‌شده)
    stale: bool = False            # متن خودکار پس از تصمیم تغییر کرده است

    @property
    def included(self) -> bool:
        return self.status != REVIEW_REJECTED

    @property
    def needs_attention(self) -> bool:
        return (self.status == REVIEW_PENDING
                and self.severity in (SEV_ERROR, SEV_WARNING, SEV_REVIEW)) or self.stale


def resolve(project: Project, key: str, auto_text: str) -> tuple[str, ReviewDecision, bool]:
    """متن نهایی یک Finding با لحاظ تصمیم مهندس. خروجی: (متن، تصمیم، کهنه؟)."""
    dec = project.reviews.get(key) or ReviewDecision()
    stale = bool(dec.auto_text_hash) and dec.auto_text_hash != text_hash(auto_text) \
        and dec.status != REVIEW_PENDING
    if dec.status == REVIEW_REJECTED:
        return "", dec, stale
    if dec.status in (REVIEW_EDITED, REVIEW_OVERRIDDEN) and dec.replacement_text.strip():
        return dec.replacement_text.strip(), dec, stale
    return auto_text, dec, stale


def set_decision(project: Project, finding: Finding, status: str,
                 comment: Optional[str] = None, replacement: str = "") -> ReviewDecision:
    """ثبت تصمیم مهندس؛ Comment قبلی در صورت ندادن مقدار جدید حفظ می‌شود."""
    old = project.reviews.get(finding.key) or ReviewDecision()
    dec = ReviewDecision(
        status=status,
        comment=old.comment if comment is None else comment.strip(),
        replacement_text=replacement.strip() if status in (REVIEW_EDITED, REVIEW_OVERRIDDEN) else "",
        auto_text_hash=text_hash(finding.auto_text),
        updated_at=datetime.now().isoformat(timespec="seconds"))
    if status in (REVIEW_EDITED, REVIEW_OVERRIDDEN) and not dec.replacement_text:
        raise ValueError("متن جایگزین نمی‌تواند خالی باشد.")
    project.reviews[finding.key] = dec
    return dec


def unresolved(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.needs_attention]
