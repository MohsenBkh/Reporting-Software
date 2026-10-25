# -*- coding: utf-8 -*-
"""سرویس سطح‌بالا: ساخت بسته ← ارسال ← پیشنهاد هر بخش ← ثبت پس از تأیید مهندس."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.ai import keystore
from app.ai.package import AIPackage, build_package
from app.ai.parser import AIResult, parse_response, unverified_numbers
from app.ai.providers import PROVIDERS, AIError, send_request
from app.ai.settings import AISettings


@dataclass
class SectionProposal:
    key: str
    title: str
    original: str
    suggested: str
    unverified: list[str] = field(default_factory=list)
    accepted: bool = False

    @property
    def changed(self) -> bool:
        return self.suggested.strip() != self.original.strip()


@dataclass
class Proposal:
    sections: list[SectionProposal] = field(default_factory=list)
    notes: str = ""
    package: Optional[AIPackage] = None


def recommend_provider(ai: AISettings) -> str:
    """ارائه‌دهنده‌ای که کلیدش موجود است (ترجیح: انتخاب فعلی، سپس Claude، OpenAI، Gemini)."""
    order = [ai.provider, "anthropic", "openai", "gemini", "custom"]
    return next((p for p in order if keystore.has_key(p)), ai.provider)


def check_ready(ai: AISettings) -> str:
    """پیام خطای آمادگی؛ رشتهٔ خالی = آماده."""
    if ai.provider not in PROVIDERS:
        return "ارائه‌دهنده نامعتبر است."
    if not keystore.get_key(ai.provider):
        return "کلید API این ارائه‌دهنده ثبت نشده است."
    if not ai.model():
        return "نام مدل را وارد کنید."
    return ""


def proposal_from_text(text: str, pkg: AIPackage) -> Proposal:
    """ساخت پیشنهاد بخش‌ها از متن پاسخ مدل — مشترک بین مسیر API و فایل ذخیره‌شده.

    مسیر آفلاین (v2.4.1): بسته ZIP در هر ابزار هوش مصنوعی بارگذاری می‌شود و پاسخ
    JSON آن (مثلاً فایل ``ReportForge_AI_revised.json``) با همین تابع وارد می‌شود؛
    همان اعتبارسنجی JSON، فیلتر کلیدهای درخواست‌شده و نگهبان عددهای ناشناخته اجرا
    می‌شود. هیچ داده‌ای در پروژه تغییر نمی‌کند تا مهندس پیشنهادها را بپذیرد.
    """
    result: AIResult = parse_response(text, pkg.requested)
    by_key = {s.key: s for s in pkg.sections}
    corpus = pkg.data_text
    proposal = Proposal(notes=result.notes, package=pkg)
    for key in pkg.requested:
        if key not in result.sections:
            continue
        orig = by_key[key]
        sug = result.sections[key]
        proposal.sections.append(SectionProposal(
            key, orig.title, orig.text, sug, unverified_numbers(sug, corpus, orig.text)))
    return proposal


def request_suggestions(pkg: AIPackage, ai: AISettings,
                        opener: Optional[Callable] = None) -> Proposal:
    """ارسال بسته و ساخت پیشنهاد برای هر بخش. هیچ داده‌ای در پروژه تغییر نمی‌کند."""
    problem = check_ready(ai)
    if problem:
        raise AIError(problem)
    if not pkg.requested:
        raise AIError("هیچ بخشی برای اصلاح انتخاب نشده است.")
    provider = PROVIDERS[ai.provider]
    req = provider.build(pkg, ai, keystore.get_key(ai.provider) or "")
    text = provider.parse(send_request(req, ai.timeout_s, opener))
    return proposal_from_text(text, pkg)


def apply_section(project: Any, proposal: SectionProposal, text: Optional[str] = None) -> None:
    """ثبت متن پذیرفته‌شده (قابل ویرایش توسط مهندس) در ``project.manual_texts``."""
    final = (text if text is not None else proposal.suggested).strip()
    if final:
        project.manual_texts[proposal.key] = final
        proposal.accepted = True
