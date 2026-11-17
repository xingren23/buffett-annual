# -*- coding: utf-8 -*-
"""Pre-build content checks and post-build link/coverage validation."""
from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

from .cnbc import parse_ref, question_turns, refkey
from .common import load_config, out_dir, root_path, year_paths

LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
REQUIRED = ("n", "slug", "title_zh", "asker_zh", "question_zh", "points", "quotes", "tags")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _by_n(obj) -> dict:
    items = obj.get("questions") if isinstance(obj, dict) else obj
    return {str(x["n"]): x for x in items}


def _trans_dir(tdir: Path) -> dict:
    out = {}
    for f in sorted(glob.glob(str(tdir / "*.json"))):
        out.update(_load(Path(f)))
    return out


def content(root: Path, year: int) -> tuple[list[str], list[str]]:
    """Everything that must be right before a build: names, shapes, turn alignment, quotes."""
    cfg = load_config(root, year)
    paths = year_paths(cfg, year)
    errors: list[str] = []
    warnings: list[str] = []
    ch_path = root / "_source" / str(year) / "transcript" / "chapters.json"
    if not ch_path.exists():
        return [f"missing {ch_path}; run prepare first"], warnings
    chapters = {c["n"]: c for c in _load(ch_path)}
    trans = _trans_dir(root / paths["translations"])
    slugs: dict[str, str] = {}

    for session, sc in cfg["sessions"].items():
        meta_path = root / paths[f"{session}_meta"]
        if not meta_path.exists():
            errors.append(f"missing {paths[f'{session}_meta']} ({len(sc['questions'])} questions)")
            continue
        meta = _by_n(_load(meta_path))
        cont = {int(k): v for k, v in sc.get("continuations", {}).items()}
        splits = sc.get("splits", {})
        for ref in sc["questions"]:
            q = refkey(ref)
            z = meta.get(q)
            if not z:
                errors.append(f"{session} {q}: no metadata entry")
                continue
            missing = [k for k in REQUIRED if not z.get(k)]
            if missing:
                errors.append(f"{session} {q}: missing {', '.join(missing)}")
            if not 3 <= len(z.get("points") or []) <= 8:
                warnings.append(f"{session} {q}: points={len(z.get('points') or [])} (target 4-6)")
            slug = z.get("slug", "")
            if slug and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
                errors.append(f"{session} {q}: slug must be lowercase-hyphen ASCII")
            if slug in slugs:
                errors.append(f"duplicate slug {slug}: {slugs[slug]} and {q}")
            slugs[slug] = q
            turns = question_turns(chapters, ref, cont, splits)
            zt = trans.get(q)
            if not isinstance(zt, list) or not all(isinstance(x, str) and x.strip() for x in zt):
                warnings.append(f"{session} {q}: no usable translation in {paths['translations']}/ "
                                f"(page keeps English only)")
            elif len(zt) != len(turns):
                warnings.append(f"{session} {q}: {len(zt)} translations != {len(turns)} turns "
                                f"(page keeps English only)")
            text = " ".join(t["text"] for t in turns)
            for i, quote in enumerate(z.get("quotes") or [], 1):
                if quote.get("en") and quote["en"] not in text:
                    errors.append(f"{session} {q}: quote {i} is not verbatim")

    app_path = root / paths["appendix_meta"]
    if app_path.exists():
        app = _load(app_path)
        for sc in cfg["sessions"].values():
            for key, a in sc.get("appendix", {}).items():
                z = app.get(a["data_key"])
                if not z:
                    errors.append(f"appendix {key}: no data for key {a['data_key']}")
                    continue
                ch = chapters[int(key)]
                want = len(ch["turns"])
                for extra in a.get("also", []):
                    want += len(chapters[int(extra)]["turns"])
                got = len(z.get("translation") or [])
                if got != want:
                    warnings.append(f"appendix {key}: {got} translations != {want} turns "
                                    f"(page keeps English only)")

    letter = cfg.get("letter") or {}
    if letter:
        secs_path = root / "_source" / str(year) / "letter" / "derived" / "letter_structure.json"
        if not secs_path.exists():
            errors.append("missing letter_structure.json; run letter-extract")
        else:
            trans_letter = {}
            for f in sorted(glob.glob(str(root / paths["letter_translations"] / "part*.json"))):
                trans_letter.update(_load(Path(f)))
            need = [f"{s['id']}-{i:03d}" for s in _load(secs_path)["sections"]
                    for i, p in enumerate(s["paras"]) if p != "---"]
            miss = [k for k in need if not str(trans_letter.get(k, "")).strip()]
            if miss:
                warnings.append(f"letter: {len(miss)} paragraphs untranslated, English kept "
                                f"(e.g. {', '.join(miss[:5])})")
    return errors, warnings


def _links(root: Path) -> tuple[int, list[tuple[str, str]]]:
    broken, total = [], 0
    for f in glob.glob(str(root / "**" / "*.md"), recursive=True):
        if ".workbuddy" in f or "_archive" in f or "_source" in f:
            continue  # backups and raw sources are not part of the linked site
        text = Path(f).read_text(encoding="utf-8")
        for m in LINK.finditer(text):
            target = m.group(1).split("#")[0].split("?")[0]
            if not target or "://" in target:
                continue
            total += 1
            if not (Path(f).parent / target).resolve().exists():
                broken.append((os.path.relpath(f, root), target))
    return total, broken


def build(root: Path, year: int) -> tuple[list[str], list[str]]:
    cfg = load_config(root, year)
    errors, warnings = [], []
    ydir = out_dir(root, year)
    if not ydir.exists():
        return [f"missing year directory: {ydir}"], []

    for session, sc in cfg["sessions"].items():
        files = sorted(glob.glob(str(ydir / session / "q*.md")))
        if len(files) != len(sc["questions"]):
            errors.append(f"{session}: {len(files)} q-files != {len(sc['questions'])} configured")
        for f in files:
            t = Path(f).read_text(encoding="utf-8")
            if "## 英文原文" not in t:
                errors.append(f"{os.path.relpath(f, root)}: missing 英文原文")
            if "## 中文全文" not in t and "仅保留英文原文" not in t:
                errors.append(f"{os.path.relpath(f, root)}: missing 中文全文（也没有仅保留英文标记）")
            if "译文待补" in t:
                errors.append(f"{os.path.relpath(f, root)}: contains 译文待补")

    lf = ydir / "shareholder-letter-zh.md"
    if cfg.get("letter"):
        if not lf.exists():
            errors.append("missing shareholder-letter-zh.md")
        elif "译文待补" in lf.read_text(encoding="utf-8"):
            errors.append("shareholder-letter-zh.md: contains 译文待补")

    total, broken = _links(root)
    if broken:
        errors.append(f"{len(broken)} broken links (of {total})")
        for f, t in broken[:10]:
            errors.append(f"  {f} -> {t}")

    qa_words = 0
    ch_path = root / "_source" / str(year) / "transcript" / "chapters.json"
    if ch_path.exists():
        chapters = {c["n"]: c for c in _load(ch_path)}
        for sc in cfg["sessions"].values():
            cont = {int(k): v for k, v in sc.get("continuations", {}).items()}
            for ref in sc["questions"]:
                qa_words += sum(len(t["text"].split())
                                for t in question_turns(chapters, ref, cont, sc.get("splits", {})))
    print(f"year {year}: {len(cfg['sessions']['morning']['questions'])} + "
          f"{len(cfg['sessions']['afternoon']['questions'])} questions, "
          f"{qa_words:,} EN words, {total} links")
    return errors, warnings


def _report(title: str, errors: list[str], warnings: list[str] | None = None) -> None:
    for w in warnings or []:
        print(f"{title}: warn {w}")
    if errors:
        print(f"{title}: FAIL ({len(errors)})")
        for e in errors[:40]:
            print(" -", e)
        if len(errors) > 40:
            print(f" ... and {len(errors) - 40} more")
        raise SystemExit(1)
    print(f"{title}: OK")


def cmd_check(args) -> None:
    errors, warnings = content(root_path(args.root), args.year)
    _report("check", errors, warnings)


def cmd_validate(args) -> None:
    errors, _ = build(root_path(args.root), args.year)
    _report("validate", errors)
