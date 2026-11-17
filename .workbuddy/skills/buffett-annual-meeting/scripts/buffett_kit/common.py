# -*- coding: utf-8 -*-
"""Shared helpers for the Buffett annual-meeting toolkit."""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("BUFFETT_ROOT", os.getcwd()))
OUTPUT_ROOT = "annual_meeting"

# 1994-2024 is the span whose CNBC pages carry official transcripts.
# 2025+ pages have chapter titles only, so this toolkit refuses them.
YEAR_MIN, YEAR_MAX = 1994, 2024


def root_path(root: str | os.PathLike | None = None) -> Path:
    return Path(root).resolve() if root else DEFAULT_ROOT.resolve()


def check_year(year: int) -> int:
    if not YEAR_MIN <= year <= YEAR_MAX:
        raise SystemExit(
            f"year {year} is out of scope: this toolkit covers {YEAR_MIN}-{YEAR_MAX}, "
            f"the years whose CNBC pages include an official transcript. "
            f"{YEAR_MAX + 1}+ pages have chapter titles only; stop and tell the user."
        )
    return year


def load_json(path: str | os.PathLike) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path: str | os.PathLike) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def out_dir(root: str | os.PathLike | None, year: int) -> Path:
    return root_path(root) / OUTPUT_ROOT / str(year)


def config_path(root: str | os.PathLike | None, year: int) -> Path:
    """Year config lives beside the year's Chinese data: data/<year>/config.json."""
    return root_path(root) / "data" / str(year) / "config.json"


def load_config(root: str | os.PathLike | None, year: int) -> dict:
    check_year(year)
    return load_json(config_path(root, year))


def year_paths(cfg: dict, year: int) -> dict:
    """Chinese-data locations; the config may omit `paths` and take the convention.

    Convention: one self-contained directory per year under data/ —
        data/<year>/morning_zh.json, afternoon_zh.json, appendix_zh.json, qa_scaffold.json
        data/<year>/zh/*.json             问答逐轮译文（可分片，按 glob 合并）
        data/<year>/letter_zh/part*.json  信件逐段译文
    The config `paths` block only exists for genuine per-year deviations.
    """
    p = dict(cfg.get("paths") or {})
    base = f"data/{year}"
    p.setdefault("morning_meta", f"{base}/morning_zh.json")
    p.setdefault("afternoon_meta", f"{base}/afternoon_zh.json")
    p.setdefault("appendix_meta", f"{base}/appendix_zh.json")
    p.setdefault("scaffold", f"{base}/qa_scaffold.json")
    p.setdefault("translations", f"{base}/zh")
    p.setdefault("letter_translations", f"{base}/letter_zh")
    return p


def ts(sec) -> str:
    sec = int(float(sec))
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def clean(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def neg(x: str) -> str:
    x = str(x).strip()
    return "-" + x[1:-1] if x.startswith("(") and x.endswith(")") else x


def cell(x: str) -> str:
    return str(x).replace("|", "\\|")


def gist(s: str) -> str:
    s = s.replace("**", "").replace("`", "")
    first = re.split(r"[。；]", s)[0]
    return first if len(first) >= 12 else s


def safe_slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "item"


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")
