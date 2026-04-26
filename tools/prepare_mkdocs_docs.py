#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ENGLISH_DOCS_DIR = ROOT / "docs"
CHINESE_DOCS_DIR = ROOT / "docs-zh"

ASSET_FILES = ("favicon.png", "cover.svg")
ASSET_DIRS = ("stylesheets", "javascripts")

ENGLISH_PATTERNS = (
    re.compile(r"^\d{2}-(?!.*-zh\.md$).+\.md$"),
    re.compile(r"^A-(?!.*-zh\.md$).+\.md$"),
    re.compile(r"^B-(?!.*-zh\.md$).+\.md$"),
    re.compile(r"^index\.md$"),
)

CHINESE_PATTERNS = (
    re.compile(r"^\d{2}-.*-zh\.md$"),
    re.compile(r"^A-.*-zh\.md$"),
    re.compile(r"^B-.*-zh\.md$"),
    re.compile(r"^index-zh\.md$"),
)


def safe_remove(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def reset_directory(path: Path) -> None:
    safe_remove(path)
    path.mkdir(parents=True, exist_ok=True)


def link_or_copy(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel_target = os.path.relpath(src, dst.parent)
    try:
        dst.symlink_to(rel_target, target_is_directory=src.is_dir())
        return "linked"
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return "copied"


def select_files(patterns: tuple[re.Pattern[str], ...]) -> list[Path]:
    selected: list[Path] = []
    for entry in sorted(ROOT.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        if any(pattern.match(entry.name) for pattern in patterns):
            selected.append(entry)
    return selected


def prepare_docs_dir(dest_dir: Path, patterns: tuple[re.Pattern[str], ...]) -> None:
    reset_directory(dest_dir)

    files = select_files(patterns)
    linked = 0
    copied = 0

    for src in files:
        result = link_or_copy(src, dest_dir / src.name)
        linked += result == "linked"
        copied += result == "copied"

    for asset in ASSET_FILES:
        src = ROOT / asset
        if not src.exists():
            continue
        result = link_or_copy(src, dest_dir / src.name)
        linked += result == "linked"
        copied += result == "copied"

    for asset_dir in ASSET_DIRS:
        src = ROOT / asset_dir
        if not src.exists():
            continue
        result = link_or_copy(src, dest_dir / asset_dir)
        linked += result == "linked"
        copied += result == "copied"

    print(f"{dest_dir.name}: {len(files)} content files, {linked} linked, {copied} copied")


def main() -> None:
    prepare_docs_dir(ENGLISH_DOCS_DIR, ENGLISH_PATTERNS)
    prepare_docs_dir(CHINESE_DOCS_DIR, CHINESE_PATTERNS)


if __name__ == "__main__":
    main()
