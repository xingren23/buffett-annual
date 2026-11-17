# -*- coding: utf-8 -*-
"""Extract a Berkshire shareholder letter PDF and build bilingual Markdown."""
from __future__ import annotations

import glob
import json
import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from .common import dump_json, load_config, neg, out_dir, root_path, year_paths


def _blocks(pdf: Path) -> list[str]:
    out = []
    for page in PdfReader(str(pdf)).pages:
        text = page.extract_text(extraction_mode="layout") or ""
        for block in re.split(r"\n\s*\n", text):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if lines:
                out.append("\n".join(lines))
    return out


_TABLE_HEADER = re.compile(
    r"^(?:\d{1,2}/\d{1,2}/\d{2,4}|Percentage of|Company|Shares .*|\(in millions\)|"
    r"Cost\*?|Market|Amount)$")


def _prose(block: str) -> str:
    """Recover the prose printed above a dot-leader table.

    Layout-mode extraction puts a lead-in paragraph and the table grid in one block, with
    the grid's columns padded out by long runs of spaces. The paragraph starts at the first
    full-width line above the dot leaders and ends where the header cells begin, so the
    trailing wrapped line (often short) still belongs to the sentence.
    """
    lines = [re.sub(r"\s{3,}", " ", l).strip() for l in block.split("\n")]
    first = next((i for i, l in enumerate(lines) if re.search(r"\.{4,}", l)), len(lines))
    keep: list[str] = []
    for line in lines[:first]:
        if _TABLE_HEADER.match(line) or re.fullmatch(r"[\d,.()*—\-\s]+", line or ""):
            break
        if not keep and len(line) <= 60:
            continue
        keep.append(line)
    lead = " ".join(keep).strip()
    return lead if len(lead) > 60 else ""


def parse(pdf: Path, sections_cfg: list[dict], split_bullets: bool = False) -> tuple[list[dict], list[tuple]]:
    sec_map = {s["title_en"].replace("’", "'"): s for s in sections_cfg}
    secs = [{"id": sections_cfg[0]["id"], "title_en": sections_cfg[0]["title_en"], "paras": []}]
    perf: list[tuple] = []
    for block in _blocks(pdf):
        one = re.sub(r"\s+", " ", block).strip()
        if not one or re.fullmatch(r"\d{1,2}", one):
            continue
        if one.startswith("(in $ millions)"):
            continue
        if one.startswith("Earnings in $ billions"):
            continue
        # Scorecard rows first: some PDFs keep the header and rows in one block, so the
        # header-only skips below would otherwise swallow the rows.
        if re.search(r"(?m)^\d{4}\s*\.{3,}", block):
            lines = block.split("\n")
            first = next((i for i, l in enumerate(lines)
                          if re.match(r"^\d{4}\s*\.{3,}", l.strip())), 0)
            # Prose printed above the rows (e.g. a holdings-table lead-in) belongs to the
            # body: keep it, then drop the header cells and the rows themselves.
            lead = _prose(block)
            if lead:
                secs[-1]["paras"].append(lead)
            for line in lines:
                m = re.match(r"^(\d{4})\s*\.{3,}\s*(.+)$", line.strip())
                if not m:
                    continue
                # PDF sometimes spaces out digits ("8 . 1"), so re-join them first.
                cells = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", m.group(2))
                nums = re.findall(r"\(?[\d,]+(?:\.\d+)?\)?", cells)
                if len(nums) >= 2:
                    perf.append((m.group(1), nums[0], nums[1]))
            continue
        if one.startswith("Annual Percentage Change") or one.startswith("in Per-Share"):
            continue
        if one.startswith("Compounded Annual Gain") or one.startswith("Overall Gain") \
                or one.startswith("Note: Data are"):
            continue
        if re.search(r"\.{4,}", one):
            lead = _prose(block)
            if lead:
                secs[-1]["paras"].append(lead)
            continue
        key = one.replace("’", "'")
        head, rest = None, ""
        if len(one) < 80 and key in sec_map:
            head = sec_map[key]
        else:
            # The PDF sometimes glues a heading and the next paragraph into one block.
            for k, s in sec_map.items():
                if len(k) >= 8 and key.startswith(k + " "):
                    head, rest = s, one[len(k):].strip()
                    break
        if head is not None:
            # A heading repeated back-to-back (e.g. a standalone "Berkshire Hathaway
            # Energy" line followed by the same heading glued to its first sentence)
            # must not spawn a duplicate empty section. Reuse the current section.
            if head["id"] != secs[0]["id"] and head["id"] != secs[-1]["id"]:
                secs.append({"id": head["id"], "title_en": head["title_en"], "paras": []})
            if not rest:
                continue
            one, block = rest, rest
        text = re.sub(r"(?:\*\s){4,}\*?", "---", block.replace("\n", " "))
        text = re.sub(r"\*(?:\s*\*){2,}", "---", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Fraction glyphs come out of the PDF as "61⁄ 2" / "3⁄4"; rebuild them.
        text = re.sub(r"(\d)\s*1⁄\s*2", r"\1 1/2", text)
        text = re.sub(r"(\d)\s*⁄\s*(\d)", r"\1/\2", text)
        text = text.replace(" 1⁄ 2 ", " 1/2 ").replace("1    1⁄   2", "1 1/2")
        if not text:
            continue
        for j, part in enumerate(text.split("---")):
            if j:
                secs[-1]["paras"].append("---")
            part = part.strip()
            if not part:
                continue
            # Bullet glyphs survive extraction as U+0081; split them into list items
            # so each point gets its own paragraph (and its own translation).
            if split_bullets and "\x81" in part:
                for k, item in enumerate(part.split("\x81")):
                    item = item.strip()
                    if item:
                        secs[-1]["paras"].append(item if k == 0 else "- " + item)
                continue
            secs[-1]["paras"].append(part)
    return secs, perf


def load_trans(root: Path, year: int) -> dict:
    trans = {}
    d = root / year_paths(load_config(root, year), year)["letter_translations"]
    for f in sorted(glob.glob(str(d / "part*.json"))):
        trans.update(json.load(open(f, encoding="utf-8")))
    return trans


def cmd_extract(args) -> None:
    root = root_path(args.root)
    cfg = load_config(root, args.year)["letter"]
    src = root / "_source" / str(args.year) / "letter"
    secs, perf = parse(src / cfg["pdf"], cfg["sections"], bool(cfg.get("split_bullets")))
    # PDF extraction mangles a few paragraphs beyond what the generic rules can recover;
    # `text_fixups` repairs wording globally and `para_fixups` replaces or drops one
    # paragraph (a null value deletes it, and indices shift accordingly).
    for old_text, new_text in cfg.get("text_fixups") or []:
        for s in secs:
            s["paras"] = [p.replace(old_text, new_text) for p in s["paras"]]
    para_fix = cfg.get("para_fixups") or {}
    if para_fix:
        for s in secs:
            keep = []
            for i, p in enumerate(s["paras"]):
                key = f"{s['id']}-{i:03d}"
                if key in para_fix:
                    repl = para_fix[key]
                    if repl is None:
                        continue
                    p = repl
                keep.append(p)
            s["paras"] = keep
    out = src / "derived" / "letter_structure.json"
    dump_json({"sections": secs, "perf": perf}, out)
    numbered = src / "derived" / "letter_numbered.txt"
    with open(numbered, "w", encoding="utf-8") as f:
        for s in secs:
            f.write(f"===== {s['id']} {s['title_en']}\n")
            for i, p in enumerate(s["paras"]):
                f.write(f"[{s['id']}-{i:03d}] {p}\n\n")
    print(f"letter {cfg['source_year']}: " +
          ", ".join(f"{s['id']}={len(s['paras'])}" for s in secs) +
          f"; perf={len(perf)} -> {out}")


def _perf_table(cfg: dict, perf: list[tuple], zh: bool = False) -> str:
    head = ("| 年份 | 伯克希尔每股市场价值变动 | 标普 500（含股息） |" if zh
            else "| Year | Berkshire per-share market value | S&P 500 incl. dividends |")
    L = [head, "|---|---:|---:|"]
    for y, a, b in perf:
        L.append(f"| {y} | {neg(a)}% | {neg(b)}% |")
    c, o = cfg["compounded"], cfg["overall"]
    if zh:
        L.append(f"| **{cfg['years'][0]}–{cfg['years'][1]} 年化** | **{c[0]}** | **{c[1]}** |")
        L.append(f"| **{cfg['years'][0] - 1}–{cfg['years'][1]} 累计** | **{o[0]}** | **{o[1]}** |")
    else:
        L.append(f"| **{cfg['years'][0]}–{cfg['years'][1]} compounded** | **{c[0]}** | **{c[1]}** |")
        L.append(f"| **{cfg['years'][0] - 1}–{cfg['years'][1]} cumulative** | **{o[0]}** | **{o[1]}** |")
    return "\n".join(L)


def _earn_table(cfg: dict, zh: bool = False) -> str:
    ncol = len(cfg["columns"])
    sep = "|---|" + "---:|" * ncol
    if zh:
        head = cfg.get("heading_zh", "项目")
        cols = cfg.get("columns_zh") or cfg["columns"]
        L = [f"| {head} | " + " | ".join(cols) + " |", sep]
        for row in cfg["rows"]:
            L.append("| " + " | ".join([row[1]] + [neg(x) for x in row[2:2 + ncol]]) + " |")
    else:
        L = [f"| {cfg['heading_en']} | " + " | ".join(cfg["columns"]) + " |", sep]
        for row in cfg["rows"]:
            L.append("| " + " | ".join([row[0]] + [neg(x) for x in row[2:2 + ncol]]) + " |")
    return "\n".join(L)


def build(root: Path, year: int) -> None:
    cfg = load_config(root, year)
    lc = cfg["letter"]
    src = root / "_source" / str(year) / "letter" / "derived" / "letter_structure.json"
    data = json.load(open(src, encoding="utf-8"))
    secs, perf = data["sections"], data["perf"]
    trans = load_trans(root, year)
    # A letter without a quarterly earnings table (e.g. 2021ltr.pdf) simply omits the key.
    et = lc.get("earnings_table")
    missing = [f"{s['id']}-{i:03d}" for s in secs for i, p in enumerate(s["paras"])
               if p != "---" and not str(trans.get(f"{s['id']}-{i:03d}", "")).strip()]
    print(f"letter translations: {len(trans)}; missing: {len(missing)}")
    if missing:
        print("  " + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""))

    out = out_dir(root, year)
    out.mkdir(parents=True, exist_ok=True)
    dt = datetime.strptime(lc["published"], "%Y-%m-%d")
    pub_en = f"{dt:%B} {dt.day}, {dt.year}"
    meeting = cfg["meeting"]

    # Some letters (e.g. 2022) print the scorecard on page 1 without a body heading,
    # so emit it as a generated trailing section when the PDF has no such heading.
    perf_cfg = lc["performance_table"]
    perf_sid = perf_cfg.get("section_id", "08")
    perf_title_en = perf_cfg.get("title_en", "Berkshire’s Performance vs. the S&P 500")
    perf_title_zh = perf_cfg.get("title_zh", "伯克希尔 vs. 标普 500")
    perf_in_body = any(s["id"] == perf_sid for s in secs)

    E = [f"# {lc['source_year']} Letter to Shareholders (published {pub_en})\n",
         f"> Warren E. Buffett · Berkshire Hathaway Inc. {lc['intro_en']}\n",
         f"- Source: [berkshirehathaway.com/letters/{lc['pdf']}]({lc['url']})",
         f"- Archive: [CNBC · {year} Annual Meeting]({meeting['hub_url']})",
         "- This is the original English text, reflowed from the PDF. "
         "[中文版本](shareholder-letter-zh.md) · [年度概览](index.md)\n",
         "## Contents\n"]
    E += [f"- {s['title_en']}" for s in secs[1:]]
    if not perf_in_body:
        E.append(f"- {perf_title_en}")
    E += ["", "---\n"]
    for s in secs:
        E.append(f"## {s['title_en']}\n")
        for i, p in enumerate(s["paras"]):
            if p == "---":
                E.append("\n---\n")
                continue
            E.append(p + "\n")
            if et and s["id"] == et["insert_after"]["section"] \
                    and i == et["insert_after"]["index"]:
                E.append(_earn_table(et) + "\n")
        if s["id"] == perf_sid:
            E.append("> " + perf_cfg["note_en"] + "\n")
            E.append(_perf_table(perf_cfg, perf) + "\n")
    if not perf_in_body:
        E.append(f"## {perf_title_en}\n")
        E.append("> " + perf_cfg["note_en"] + "\n")
        E.append(_perf_table(perf_cfg, perf) + "\n")
    E.append(f"\n---\n\nBack: [年度概览](index.md) · [中文版本](shareholder-letter-zh.md)\n")
    (out / "shareholder-letter-en.md").write_text("\n".join(E), encoding="utf-8")

    Z = [f"# {lc['source_year']} 年致股东的信（{lc['published_zh']}发布）\n",
         f"> 沃伦·巴菲特署名 · 伯克希尔·哈撒韦年度报告。{lc['intro_zh']}\n",
         f"- 原文：[berkshirehathaway.com/letters/{lc['pdf']}]({lc['url']})",
         f"- 年会页面（CNBC）：[{year} Berkshire Hathaway Annual Meeting]({meeting['hub_url']})",
         "- 本文件为**完整中文译文**，按英文原信分节、分段；"
         "[英文版本](shareholder-letter-en.md) · [年度概览](index.md)\n"]
    if missing:
        Z.append(f"- 注：{len(missing)} 个段落译文暂缺，对应段落仅保留英文原文。\n")
    Z += ["## 目录\n"]
    Z += [f"- {s['title_zh']}" for s in lc["sections"][1:]]
    if not perf_in_body:
        Z.append(f"- {perf_title_zh}")
    Z += ["", "---\n"]
    for s in secs:
        title = next((x["title_zh"] for x in lc["sections"] if x["id"] == s["id"]), s["title_en"])
        Z.append(f"## {title}\n")
        for i, p in enumerate(s["paras"]):
            if p == "---":
                Z.append("\n---\n")
                continue
            zh = trans.get(f"{s['id']}-{i:03d}")
            Z.append((zh if isinstance(zh, str) and zh.strip() else p) + "\n")
            if et and s["id"] == et["insert_after"]["section"] \
                    and i == et["insert_after"]["index"]:
                Z.append(et["zh_caption"] + "\n")
                Z.append(_earn_table(et, zh=True) + "\n")
        if s["id"] == perf_sid:
            Z.append("> " + perf_cfg["note_zh"] + "\n")
            Z.append(_perf_table(perf_cfg, perf, zh=True) + "\n")
    if not perf_in_body:
        Z.append(f"## {perf_title_zh}\n")
        Z.append("> " + perf_cfg["note_zh"] + "\n")
        Z.append(_perf_table(perf_cfg, perf, zh=True) + "\n")
    Z.append(f"\n---\n\n返回：[年度概览](index.md) · [英文版本](shareholder-letter-en.md)\n")
    (out / "shareholder-letter-zh.md").write_text("\n".join(Z), encoding="utf-8")
    print(f"wrote {out/'shareholder-letter-en.md'} / -zh.md")
