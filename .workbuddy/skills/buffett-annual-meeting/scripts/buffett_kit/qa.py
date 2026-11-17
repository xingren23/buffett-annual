# -*- coding: utf-8 -*-
"""Build one-question-per-file Q&A pages and session indexes."""
from __future__ import annotations

import glob
import json
from pathlib import Path

from .cnbc import parse_ref, question_span, question_turns, refkey
from .common import clean, gist, load_config, out_dir, root_path, ts, year_paths


def _meta(path: Path) -> dict:
    obj = json.load(open(path, encoding="utf-8"))
    if isinstance(obj, list):
        return {str(x["n"]): x for x in obj}
    return {str(k): v for k, v in obj.items()}


def _trans(path: Path) -> dict:
    out = {}
    for f in sorted(glob.glob(str(path / "*.json"))):
        out.update(json.load(open(f, encoding="utf-8")))
    return out


def _trans_ok(zt, turns) -> bool:
    """A translation array is usable only if it is a non-empty-string list aligned to turns."""
    return (isinstance(zt, list) and len(zt) == len(turns)
            and all(isinstance(x, str) and x.strip() for x in zt))


def _session(root: Path, year: int, cfg: dict, session: str, chapters: dict,
             meta: dict, trans: dict) -> list[dict]:
    sc = cfg["sessions"][session]
    label = sc["label"]
    url = cfg["meeting"][f"{session}_url"]
    outdir = out_dir(root, year) / session
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    base = 0 if session == "morning" else len(cfg["sessions"]["morning"]["questions"])
    cont = {int(k): v for k, v in sc.get("continuations", {}).items()}
    splits = sc.get("splits", {})
    for idx, ref in enumerate(sc["questions"], 1):
        qref = refkey(ref)
        c, z = chapters[parse_ref(ref)[0]], meta[qref]
        turns = question_turns(chapters, ref, cont, splits)
        zt = trans.get(qref)
        tr_ok = _trans_ok(zt, turns)
        if not tr_ok:
            got = len(zt) if isinstance(zt, list) else "none"
            print(f"warn: {session} Q{qref} translation unusable ({got} vs {len(turns)} turns); "
                  f"English-only page")
        gq = base + idx
        fname = f"q{idx:02d}-{z['slug']}.md"
        t0 = ts(turns[0]["ts"])
        span_in, span_out = question_span(chapters, ref, turns, cont, splits)
        conts = sorted(k for k, v in cont.items() if refkey(v) == qref)
        span_note = ("，含第 " + "、".join(f"{k}" for k in conts) + " 章延续") if conts else ""
        rows.append({"n": idx, "gq": gq, "qn": qref, "title": z["title_zh"], "asker": z["asker_zh"],
                     "t": t0, "file": fname, "gist": gist(z["points"][0])})
        L = [f"# 第 {idx:02d} 问 · {z['title_zh']}\n",
             "| 项目 | 内容 |", "|---|---|",
             f"| 场次 | {label}（全场第 {gq} 问） |",
             f"| 时间戳 | {t0} |",
             f"| 提问者 | {z['asker_zh']} |",
             f"| CNBC 章节 | {clean(c['title'])}（{ts(span_in)}–{ts(span_out)}）{span_note} |",
             f"| 视频 | [{label}完整视频]({url}) |",
             "| 主题标签 | " + " ".join(f"`#{x}`" for x in z["tags"]) + " |",
             "", "## 问题\n", z["question_zh"] + "\n", "## 回答要点\n"]
        L += [f"{i}. {p}" for i, p in enumerate(z["points"], 1)]
        L += ["", "## 关键引述\n"]
        for q in z["quotes"]:
            L.append(f"> **“{q['en']}”**\n>\n> 「{q['zh']}」\n")
        if tr_ok:
            L += ["## 中文全文（逐段翻译）\n",
                  "> 与下方「英文原文」逐段对应，按发言顺序排列；术语与专名首次出现时保留英文。\n"]
            for tr, zh in zip(turns, zt):
                L.append(f"**{clean(tr['speaker'])}**（{ts(tr['ts'])}）：{zh}\n")
        else:
            L += ["", "> 译文缺失或与原文轮次不匹配，本页仅保留英文原文。\n"]
        L += ["## 英文原文（CNBC 官方逐字稿）\n"]
        for tr in turns:
            L.append(f"**{clean(tr['speaker'])}**（{ts(tr['ts'])}）：{clean(tr['text'])}\n")
        L += ["---\n", f"[← 返回{label}索引](index.md) · 来源：[CNBC {year} 年会]({cfg['meeting']['hub_url']})\n"]
        (outdir / fname).write_text("\n".join(L), encoding="utf-8")

    L = [f"# {year} 年伯克希尔股东大会 · {label}{'问答索引' if rows else ''}\n",
         f"- 会议时间：{cfg['meeting']['date_zh']}· {cfg['meeting'].get('venue_zh', '奥马哈 CHI Health Center')}",
         f"- 场次视频：[{label}完整视频]({url})"]
    if not rows:
        L.append(f"- {sc.get('no_qa_note', '本场无问答环节')}")
        L += ["", "返回：[年度概览](../index.md)\n"]
        (outdir / "index.md").write_text("\n".join(L), encoding="utf-8")
        return rows
    L += [f"- 本场共整理 **{len(rows)} 个问答片段**（全场第 {rows[0]['gq']}–{rows[-1]['gq']} 问），一个片段对应一个提问",
         f"- 索引与片段均按 CNBC 官方章节时间轴对齐；{cfg.get('transcript_note', '英文原文照录官方逐字稿，仅做分段与发言人整理')}",
         "", "## 索引\n",
         "| # | 主题 | 时间戳 | 提问者 | 核心要点（首条） | 片段 |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['n']:02d} | {r['title']} | {r['t']} | {r['asker']} | {r['gist']} | [{r['n']:02d}]({r['file']}) |")
    back = "返回：[年度概览](../index.md)"
    if cfg.get("letter"):
        back += " · [致股东信·中文](../shareholder-letter-zh.md) · [致股东信·英文](../shareholder-letter-en.md)"
    L += ["", back + "\n"]
    (outdir / "index.md").write_text("\n".join(L), encoding="utf-8")
    return rows


def build(root: Path, year: int) -> None:
    cfg = load_config(root, year)
    chapters = {c["n"]: c for c in json.loads(
        (root / "_source" / str(year) / "transcript" / "chapters.json").read_text(encoding="utf-8"))}
    paths = year_paths(cfg, year)
    meta_m = _meta(root / paths["morning_meta"])
    meta_a = _meta(root / paths["afternoon_meta"])
    trans = _trans(root / paths["translations"])
    for session, meta in (("morning", meta_m), ("afternoon", meta_a)):
        rows = _session(root, year, cfg, session, chapters, meta, trans)
        print(f"{session}: {len(rows)}")

    app_path = root / paths["appendix_meta"]
    if not app_path.exists():
        return
    app = json.load(open(app_path, encoding="utf-8"))
    for session, sc in cfg["sessions"].items():
        for key, a in sc.get("appendix", {}).items():
            c = chapters[int(key)]
            z = app[a["data_key"]]
            # An appendix may span several chapters (e.g. a multi-slide opening review).
            turns = list(c["turns"])
            span_out = c["out"]
            also = [int(x) for x in a.get("also", [])]
            for extra in also:
                turns += chapters[extra]["turns"]
                span_out = max(span_out, chapters[extra]["out"])
            span_note = ("，含第 " + "、".join(str(x) for x in also) + " 章延续") if also else ""
            tr_ok = _trans_ok(z.get("translation"), turns)
            if not tr_ok:
                got = len(z.get("translation") or []) if isinstance(z.get("translation"), list) else "none"
                print(f"warn: appendix {key} translation unusable ({got} vs {len(turns)} turns); "
                      f"English-only page")
            label = a["label"]
            url = cfg["meeting"][f"{session}_url"]
            L = [f"# {label}\n", "| 项目 | 内容 |", "|---|---|",
                 f"| 场次 | {sc['label']}（非提问环节） |",
                 f"| 时间戳 | {ts(c['in'])}–{ts(span_out)} |",
                 f"| CNBC 章节 | {clean(c['title'])}（{ts(c['in'])}–{ts(span_out)}）{span_note} |",
                 f"| 视频 | [{sc['label']}完整视频]({url}) |",
                 "| 主题标签 | " + " ".join(f"`#{x}`" for x in z.get("tags", [])) + " |",
                 "", "## 背景\n", z.get("intro_zh", "") + "\n", "## 要点\n"]
            L += [f"{i}. {p}" for i, p in enumerate(z["points"], 1)]
            L += ["", "## 关键引述\n"]
            for q in z["quotes"]:
                L.append(f"> **“{q['en']}”**\n>\n> 「{q['zh']}」\n")
            if tr_ok:
                L += ["## 中文全文（逐段翻译）\n", "> 与下方「英文原文」逐段对应。\n"]
                for tr, zh in zip(turns, z["translation"]):
                    L.append(f"**{clean(tr['speaker'])}**（{ts(tr['ts'])}）：{zh}\n")
            else:
                L += ["", "> 译文缺失或与原文轮次不匹配，本页仅保留英文原文。\n"]
            L += ["## 英文原文（CNBC 官方逐字稿）\n"]
            for tr in turns:
                L.append(f"**{clean(tr['speaker'])}**（{ts(tr['ts'])}）：{clean(tr['text'])}\n")
            L += ["---\n", f"返回：[{sc['label']}索引](index.md)\n"]
            (out_dir(root, year) / session / a["file"]).write_text("\n".join(L), encoding="utf-8")
            print(f"appendix {key} -> {a['file']}")
