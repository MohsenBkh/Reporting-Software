# -*- coding: utf-8 -*-
"""v2.0.0 — دستیار هوش مصنوعی: بستهٔ ارسال، درخواست ارائه‌دهندگان، پاسخ، نگهبان عدد، ثبت متن."""
from __future__ import annotations

import io
import json
import urllib.error
import zipfile

from app.ai import keystore
from app.ai.package import REDACTED, build_package, sections_from_report
from app.ai.parser import parse_response, unverified_numbers
from app.ai.providers import PROVIDERS, AIError, send_request
from app.ai.service import (apply_section, check_ready, recommend_provider, request_suggestions)
from app.ai.settings import AISettings
from app.core.settings import AppSettings
from app.core.studies import StudyKind
from app.report.composer import ReportComposer
from test_v200_protection_rules import _khalkhal

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\x9c\x1b\x00\x00\x00\x00IEND\xaeB`\x82")


class _Img:
    def __init__(self, i=1, kind="tcc", section_key="prot_coordination", enabled=True):
        self.uid, self.title, self.kind, self.section_key = f"u{i}", f"شکل {i}", kind, section_key
        self.caption, self.order, self.enabled, self.file_name = "", i, enabled, f"i{i}.png"


def _setup(tmp_path, monkeypatch=None, n_images=2):
    p, ws = _khalkhal()
    p.applicant_name, p.expert_name, p.last_report_path = "شرکت محرمانه", "کارشناس الف", "C:/Users/x/out.docx"
    imgs = [_Img(i) for i in range(1, n_images + 1)]
    p.__class__ = type("P", (p.__class__,), {"active_images": property(
        lambda self: [i for i in imgs if i.enabled])})
    (tmp_path / "i1.png").write_bytes(PNG)
    (tmp_path / "i2.png").write_bytes(PNG)
    composer = ReportComposer()
    report = composer.compose(p, ws, [StudyKind.RECLOSER])
    results = composer.analyse(p, ws, [StudyKind.RECLOSER])
    resolver = lambda img: tmp_path / img.file_name                    # noqa: E731
    return p, ws, report, results, resolver


def test_package_contains_all_inputs_findings_sections_images_and_task(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    pkg = build_package(p, ws, report, results, AISettings(), resolver, ["prot_intro", "prot_coordination"])
    names = set(pkg.files)
    assert {"project.json", "workspace.json", "findings.json", "sections.json", "images.json",
            "task.md", "manifest.json"} <= names
    assert sum(n.startswith("images/") for n in names) == 2 and pkg.n_images == 2
    assert pkg.requested == ["prot_intro", "prot_coordination"]
    sections = json.loads(pkg.files["sections.json"])
    assert sections["prot_intro"]["requested"] and not sections["prot_network"]["requested"]
    finds = json.loads(pkg.files["findings.json"])
    assert finds and all({"rule", "status", "source", "fix_location"} <= set(f) for f in finds)
    assert "الزامی" in pkg.files["task.md"].decode("utf-8") or "قواعد" in pkg.files["task.md"].decode("utf-8")


def test_package_anonymizes_people_and_strips_local_paths(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    pkg = build_package(p, ws, report, results, AISettings(), resolver)
    proj = json.loads(pkg.files["project.json"])
    assert proj["applicant_name"] == REDACTED and proj["expert_name"] == REDACTED
    assert "last_report_path" not in proj
    assert "شرکت محرمانه" not in pkg.data_text and "C:/Users" not in pkg.data_text
    pkg2 = build_package(p, ws, report, results, AISettings(anonymize_people=False), resolver)
    assert json.loads(pkg2.files["project.json"])["applicant_name"] == "شرکت محرمانه"


def test_package_respects_image_and_findings_switches(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    pkg = build_package(p, ws, report, results, AISettings(send_images=False, include_findings=False), resolver)
    assert pkg.n_images == 0 and not any(n.startswith("images/") for n in pkg.files)
    assert json.loads(pkg.files["findings.json"]) == []
    pkg = build_package(p, ws, report, results, AISettings(max_images=1), resolver)
    assert pkg.n_images == 1


def test_oversized_image_is_skipped_with_warning(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    (tmp_path / "i1.png").write_bytes(PNG + b"\x00" * 600_000)
    pkg = build_package(p, ws, report, results, AISettings(max_image_kb=100), resolver)
    assert any("بزرگ" in w for w in pkg.warnings) and pkg.n_images == 1


def test_zip_export_roundtrip(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    pkg = build_package(p, ws, report, results, AISettings(), resolver)
    out = pkg.to_zip(tmp_path / "pkg.zip")
    with zipfile.ZipFile(out) as z:
        assert set(z.namelist()) == set(pkg.files) and z.testzip() is None
    assert zipfile.ZipFile(io.BytesIO(pkg.to_zip_bytes())).namelist() == list(pkg.files)


def test_sections_text_includes_tables_for_context(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    secs = {s.key: s for s in sections_from_report(report)}
    assert "[جدول" in secs["prot_recloser"].text and "|" in secs["prot_recloser"].text


# ---------------------------------------------------------------------------
# ارائه‌دهندگان
# ---------------------------------------------------------------------------
def _pkg(tmp_path):
    p, ws, report, results, resolver = _setup(tmp_path)
    return build_package(p, ws, report, results, AISettings(), resolver, ["prot_intro"])


def test_anthropic_request_shape(tmp_path):
    ai = AISettings(provider="anthropic")
    req = PROVIDERS["anthropic"].build(_pkg(tmp_path), ai, "KEY")
    body = json.loads(req.body)
    assert req.url.endswith("/v1/messages") and req.headers["x-api-key"] == "KEY"
    assert req.headers["anthropic-version"] and body["model"] == ai.model() and body["system"] == ai.instructions
    kinds = [c["type"] for c in body["messages"][0]["content"]]
    assert kinds.count("image") == 2 and kinds[0] == "text"
    assert body["messages"][0]["content"][2]["source"]["type"] == "base64"


def test_openai_and_custom_request_shape(tmp_path):
    pkg = _pkg(tmp_path)
    req = PROVIDERS["openai"].build(pkg, AISettings(provider="openai"), "K")
    body = json.loads(req.body)
    assert req.url == "https://api.openai.com/v1/chat/completions" and req.headers["Authorization"] == "Bearer K"
    assert body["messages"][0]["role"] == "system"
    assert any(c.get("type") == "image_url" and c["image_url"]["url"].startswith("data:image/")
               for c in body["messages"][1]["content"])
    ai = AISettings(provider="custom", custom_base_url="https://x.example/v1/")
    assert PROVIDERS["custom"].build(pkg, ai, "K").url == "https://x.example/v1/chat/completions"
    try:
        PROVIDERS["custom"].build(pkg, AISettings(provider="custom"), "K")
    except AIError as e:
        assert "Base URL" in str(e)
    else:
        raise AssertionError


def test_gemini_request_shape(tmp_path):
    ai = AISettings(provider="gemini")
    req = PROVIDERS["gemini"].build(_pkg(tmp_path), ai, "G")
    body = json.loads(req.body)
    assert req.url.endswith(f"{ai.model()}:generateContent") and req.headers["x-goog-api-key"] == "G"
    assert any("inline_data" in part for part in body["contents"][0]["parts"])
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_response_parsers():
    a = PROVIDERS["anthropic"].parse({"content": [{"type": "text", "text": "الف"}, {"type": "text", "text": "ب"}]})
    assert a == "الفب"
    assert PROVIDERS["openai"].parse({"choices": [{"message": {"content": "x"}}]}) == "x"
    assert PROVIDERS["gemini"].parse({"candidates": [{"content": {"parts": [{"text": "y"}]}}]}) == "y"
    for prov, bad in (("anthropic", {"content": []}), ("openai", {}), ("gemini", {"candidates": []})):
        try:
            PROVIDERS[prov].parse(bad)
        except AIError:
            continue
        raise AssertionError(prov)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return self._p


def test_send_request_http_errors_become_persian_messages():
    from app.ai.providers import HttpRequest
    req = HttpRequest("https://x", {}, b"{}")

    def raiser(code, body=b'{"error":{"message":"boom"}}'):
        def op(request, timeout=0):
            raise urllib.error.HTTPError("https://x", code, "m", {}, io.BytesIO(body))
        return op
    for code, word in ((401, "کلید"), (429, "سقف"), (404, "مدل"), (500, "سرور")):
        try:
            send_request(req, opener=raiser(code))
        except AIError as e:
            assert word in str(e) and "boom" in str(e)
        else:
            raise AssertionError(code)

    def offline(request, timeout=0):
        raise urllib.error.URLError("no route")
    try:
        send_request(req, opener=offline)
    except AIError as e:
        assert "اتصال" in str(e)
    try:
        send_request(req, opener=lambda r, timeout=0: _Resp(b"<html>"))
    except AIError as e:
        assert "JSON" in str(e)


# ---------------------------------------------------------------------------
# پارس پاسخ و نگهبان عدد
# ---------------------------------------------------------------------------
def test_parse_response_variants_and_key_filtering():
    r = parse_response('```json\n{"sections": {"a": "متن الف", "zzz": "نباید"}, "notes": "ن"}\n```', ["a", "b"])
    assert r.sections == {"a": "متن الف"} and r.notes == "ن"
    r = parse_response('توضیح اضافه {"sections": {"b": "ب"}} پایان', ["a", "b"])
    assert r.sections == {"b": "ب"}
    for bad in ("not json", '{"x": 1}', '{"sections": {"zzz": "q"}}', '{"sections": {"a": "  "}}'):
        try:
            parse_response(bad, ["a"])
        except AIError:
            continue
        raise AssertionError(bad)


def test_unverified_numbers_detects_invented_values_and_normalizes_digits():
    corpus = "Pickup 250 A و TMS 5% و ۳۰۰ ثانیه و 0.18"
    assert unverified_numbers("Pickup ۲۵۰ آمپر، reclaim 300 s، TMS 5", corpus) == []
    assert unverified_numbers("Pickup 275 A و 0.180", corpus) == ["275"]
    assert unverified_numbers("بدون عدد", corpus) == []


# ---------------------------------------------------------------------------
# کلید، سرویس و ثبت متن
# ---------------------------------------------------------------------------
def test_keystore_env_overrides_file_and_never_in_settings(tmp_path, monkeypatch=None):
    import os
    os.environ["REPORTFORGE_AI_KEYS"] = str(tmp_path / "keys.json")
    os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        assert keystore.get_key("anthropic") is None and not keystore.has_key("anthropic")
        keystore.set_key("anthropic", " sk-file-123456 ")
        assert keystore.get_key("anthropic") == "sk-file-123456"
        os.environ["ANTHROPIC_API_KEY"] = "sk-env-999999"
        assert keystore.get_key("anthropic") == "sk-env-999999"
        keystore.set_key("anthropic", "")
        os.environ.pop("ANTHROPIC_API_KEY")
        assert keystore.get_key("anthropic") is None
        assert keystore.mask("sk-abcdefghijkl") == "sk-a…jkl"
        from dataclasses import asdict
        assert "sk-" not in json.dumps(asdict(AppSettings()))
    finally:
        os.environ.pop("REPORTFORGE_AI_KEYS", None)


def _with_key(tmp_path, provider="anthropic"):
    import os
    os.environ["REPORTFORGE_AI_KEYS"] = str(tmp_path / "keys.json")
    keystore.set_key(provider, "sk-test-123456")


def test_check_ready_and_recommend_provider(tmp_path):
    import os
    os.environ["REPORTFORGE_AI_KEYS"] = str(tmp_path / "k.json")
    for n in keystore.ENV_NAMES.values():
        os.environ.pop(n, None)
    try:
        assert "کلید" in check_ready(AISettings())
        keystore.set_key("openai", "k-openai-12345")
        assert recommend_provider(AISettings(provider="anthropic")) == "openai"
        assert check_ready(AISettings(provider="openai")) == ""
        keystore.set_key("custom", "k-custom-12345")
        assert "مدل" in check_ready(AISettings(provider="custom", models={"custom": ""}))
    finally:
        os.environ.pop("REPORTFORGE_AI_KEYS", None)


def test_request_suggestions_end_to_end_with_fake_transport(tmp_path):
    import os
    _with_key(tmp_path)
    try:
        p, ws, report, results, resolver = _setup(tmp_path)
        pkg = build_package(p, ws, report, results, AISettings(), resolver, ["prot_intro", "prot_coordination"])
        sent = {}

        def opener(request, timeout=0):
            sent["url"], sent["body"] = request.full_url, json.loads(request.data)
            answer = {"sections": {"prot_intro": "مقدمهٔ اصلاح‌شده برای فیدر F4 خلخال با Pickup 999 A.",
                                   "prot_coordination": "هماهنگی بررسی شد."}, "notes": "اصلاح نگارشی"}
            return _Resp(json.dumps({"content": [{"type": "text", "text": json.dumps(answer, ensure_ascii=False)}]}).encode())
        prop = request_suggestions(pkg, AISettings(), opener)
        assert sent["url"].endswith("/v1/messages") and prop.notes == "اصلاح نگارشی"
        by = {s.key: s for s in prop.sections}
        assert by["prot_intro"].unverified == ["999"] and by["prot_coordination"].unverified == []
        assert by["prot_intro"].original and by["prot_intro"].changed
        assert "prot_intro" not in p.manual_texts                  # تا تأیید مهندس چیزی ذخیره نمی‌شود
        apply_section(p, by["prot_intro"], "متن نهایی ویرایش‌شدهٔ مهندس")
        assert p.manual_texts["prot_intro"] == "متن نهایی ویرایش‌شدهٔ مهندس" and by["prot_intro"].accepted
        rep = ReportComposer().compose(p, ws, [StudyKind.RECLOSER])
        intro = next(s for s in rep.sections if s.key == "prot_intro")
        assert [b.text for b in intro.blocks][0] == "متن نهایی ویرایش‌شدهٔ مهندس" and intro.manual
    finally:
        os.environ.pop("REPORTFORGE_AI_KEYS", None)


def test_request_suggestions_requires_key_and_selection(tmp_path):
    import os
    os.environ["REPORTFORGE_AI_KEYS"] = str(tmp_path / "none.json")
    for n in keystore.ENV_NAMES.values():
        os.environ.pop(n, None)
    try:
        p, ws, report, results, resolver = _setup(tmp_path)
        pkg = build_package(p, ws, report, results, AISettings(), resolver, [])
        try:
            request_suggestions(pkg, AISettings(), lambda r, timeout=0: _Resp(b"{}"))
        except AIError as e:
            assert "کلید" in str(e)
        keystore.set_key("anthropic", "sk-x-123456")
        try:
            request_suggestions(pkg, AISettings(), lambda r, timeout=0: _Resp(b"{}"))
        except AIError as e:
            assert "بخشی" in str(e)
    finally:
        os.environ.pop("REPORTFORGE_AI_KEYS", None)


def test_ai_settings_persist_in_app_settings_without_keys():
    from dataclasses import asdict
    s = AppSettings()
    s._apply({"ai": {"provider": "gemini", "send_images": False, "models": {"gemini": "m-x"}}})
    assert s.ai.provider == "gemini" and s.ai.send_images is False and s.ai.model() == "m-x"
    assert s.ai.models["anthropic"]                                   # ادغام: مدل‌های دیگر حفظ می‌شود
    d = asdict(s)["ai"]
    assert "api_key" not in json.dumps(d).lower()
