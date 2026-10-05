# -*- coding: utf-8 -*-
"""مدیریت پروژه — New / Open / Save / Save As + پوشه استاندارد پروژه (بخش ۶ و ۳۳ سند).

ساختار پوشه پروژه:
    ProjectDir/
        project.json      ← مدل کامل پروژه
        profiles/         ← پروفیل بار هر فیدر (CSV)
        images/           ← تصاویر کپی‌شده کاربر
        charts/           ← نمودارهای تولیدی
        output/           ← گزارش‌های Word خروجی
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.core.models import Feeder, Project, project_from_dict, to_dict
from app.core.settings import AppSettings

PROJECT_FILE = "project.json"


class ProjectManager:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.project: Project | None = None
        self.project_dir: Path | None = None
        self.dirty = False

    # ------------------------------------------------------------------
    @staticmethod
    def init_project_dir(path: str | Path) -> Path:
        p = Path(path)
        for sub in ("profiles", "images", "charts", "output"):
            (p / sub).mkdir(parents=True, exist_ok=True)
        return p

    def new_project(self, path: str | Path, project: Project | None = None) -> Project:
        self.project_dir = self.init_project_dir(path)
        self.project = project or Project()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.project.created_at = now
        self.project.updated_at = now
        self.save()
        self.settings.add_recent(str(self.project_dir / PROJECT_FILE))
        return self.project

    def open_project(self, project_file: str | Path) -> Project:
        project_file = Path(project_file)
        if project_file.name != PROJECT_FILE:
            project_file = project_file / PROJECT_FILE
        data = json.loads(project_file.read_text(encoding="utf-8"))
        self.project = project_from_dict(data)
        self.project_dir = project_file.parent
        self.dirty = False
        self.settings.add_recent(str(project_file))
        return self.project

    def save(self, target_dir: str | Path | None = None) -> None:
        """ذخیره پروژه + پروفیل‌ها. target_dir برای Save As."""
        if self.project is None:
            return
        if target_dir is not None:
            new_dir = self.init_project_dir(target_dir)
            if self.project_dir and new_dir != self.project_dir:
                # انتقال محتویات پروژه فعلی به مقصد جدید
                for sub in ("profiles", "images", "charts"):
                    src, dst = self.project_dir / sub, new_dir / sub
                    if src.exists():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
            self.project_dir = new_dir
            self.settings.add_recent(str(new_dir / PROJECT_FILE))
        assert self.project_dir is not None
        self.project.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        # پروفیل‌ها → CSV
        for feeder in self.project.feeders:
            if getattr(feeder, "_profile_df", None) is not None:
                self._write_profile(feeder)

        path = self.project_dir / PROJECT_FILE
        path.write_text(json.dumps(to_dict(self.project), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        self.dirty = False

    # ------------------------------------------------------------------
    # پروفیل بار
    # ------------------------------------------------------------------
    def set_profile(self, feeder: Feeder, df: pd.DataFrame) -> None:
        """نمونه DataFrame پروفیل را روی فیدر نگه می‌دارد تا هنگام Save ذخیره شود."""
        feeder._profile_df = df  # noqa: SLF001 — نمونه گذرا؛ سریال‌سازی جدا است
        self.dirty = True

    def get_profile(self, feeder: Feeder) -> pd.DataFrame | None:
        """DataFrame پروفیل فیدر — از حافظه یا از فایل پروژه."""
        if getattr(feeder, "_profile_df", None) is not None:
            return feeder._profile_df  # noqa: SLF001
        if self.project_dir and feeder.profile_file:
            path = self.project_dir / "profiles" / feeder.profile_file
            if path.exists():
                try:
                    df = pd.read_csv(path, encoding="utf-8-sig")
                    feeder._profile_df = df  # noqa: SLF001
                    return df
                except OSError:
                    return None
        return None

    def _write_profile(self, feeder: Feeder) -> None:
        assert self.project_dir is not None
        df = getattr(feeder, "_profile_df", None)
        if df is None:
            return
        if not feeder.profile_file:
            feeder.profile_file = f"profile_{feeder.uid}.csv"
        path = self.project_dir / "profiles" / feeder.profile_file
        df.to_csv(path, index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------------
    # تصاویر
    # ------------------------------------------------------------------
    def import_image(self, source: str | Path, title: str, kind: str,
                     section_key: str = "", order: int = 0,
                     caption: str = "") -> bool:
        """کپی تصویر به پوشه images پروژه.

        ``section_key``/``order``/``caption`` (v1.2.0) محل قرارگیری، اولویت و کپشن
        مستقل شکل را ثبت می‌کنند؛ مقدار پیش‌فرض، رفتار نسخه‌های قبل است.
        """
        from app.core.models import ProjectImage
        if self.project is None or self.project_dir is None:
            return False
        src = Path(source)
        if not src.exists():
            return False
        dst_dir = self.project_dir / "images"
        dst_dir.mkdir(exist_ok=True)
        img = ProjectImage(file_name=f"img_{ProjectImage().uid}{src.suffix.lower()}",
                           title=title, kind=kind, section_key=section_key or "",
                           order=int(order or 0), caption=caption or "")
        shutil.copy2(src, dst_dir / img.file_name)
        self.project.images.append(img)
        self.dirty = True
        return True

    def remove_image(self, uid: str) -> None:
        if self.project is None:
            return
        self.project.images = [i for i in self.project.images if i.uid != uid]
        self.dirty = True

    def image_path(self, image) -> Path | None:
        if self.project_dir is None:
            return None
        p = self.project_dir / "images" / image.file_name
        return p if p.exists() else None

    # ------------------------------------------------------------------
    @property
    def output_dir(self) -> Path:
        assert self.project_dir is not None
        out = self.project_dir / "output"
        out.mkdir(exist_ok=True)
        return out

    def charts_dir(self) -> Path:
        assert self.project_dir is not None
        d = self.project_dir / "charts"
        d.mkdir(exist_ok=True)
        return d
