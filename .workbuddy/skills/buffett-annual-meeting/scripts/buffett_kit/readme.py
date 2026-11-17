# -*- coding: utf-8 -*-
"""Build the annual README (overview, directory, theme index, sources)."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .common import load_config, out_dir, year_paths


def build(root: Path, year: int) -> None:
    cfg = load_config(root, year)
    m = cfg["meeting"]
    paths = year_paths(cfg, year)
    meta_m = json.load(open(root / paths["morning_meta"], encoding="utf-8"))
    meta_a = json.load(open(root / paths["afternoon_meta"], encoding="utf-8"))
    if isinstance(meta_m, dict):
        meta_m = [meta_m[k] for k in sorted(meta_m, key=int)]
    if isinstance(meta_a, dict):
        meta_a = [meta_a[k] for k in sorted(meta_a, key=int)]

    n_m = len(cfg["sessions"]["morning"]["questions"])
    n_a = len(cfg["sessions"]["afternoon"]["questions"])
    rows = []
    for i, v in enumerate(meta_m, 1):
        rows.append((i, "morning", v))
    for i, v in enumerate(meta_a, 1):
        rows.append((n_m + i, "afternoon", v))
    tagmap = defaultdict(list)
    for gq, sess, v in rows:
        local = gq if sess == "morning" else gq - n_m
        fn = f"{sess}/q{local:02d}-{v['slug']}.md"
        for t in v["tags"]:
            tagmap[t].append((gq, sess, v["title_zh"], fn))

    lc = cfg.get("letter") or {}
    quick = []
    if lc:
        quick.append(
            f"| 致股东信（{lc['source_year']} 年报信，"
            f"{lc.get('published_zh', lc.get('published', ''))}） "
            "| [中文译文](shareholder-letter-zh.md) · [英文全文](shareholder-letter-en.md) |")
    for session in ("morning", "afternoon"):
        sc = cfg["sessions"][session]
        n = len(sc["questions"])
        row = (f"{sc['label']}问答索引（{n} 问）" if n else f"{sc['label']}（无问答环节）")
        quick.append(f"| {row} | [{session}/index.md]({session}/index.md) |")
    # Appendices are not in the session index tables, so list them here or they lose their entry point.
    for session, sc in cfg["sessions"].items():
        for a in sc.get("appendix", {}).values():
            label = a["label"].replace("附件 · ", "附件：")
            quick.append(f"| {sc['label']}·{label} | [{a['file']}]({session}/{a['file']}) |")

    L = [f"# {year} 年伯克希尔·哈撒韦股东大会\n",
         "| 项目 | 内容 |", "|---|---|",
         f"| 时间 | {m['date_zh']} |",
         f"| 地点 | {m['location']} |",
         f"| 特殊背景 | {m['note']} |",
         f"| 台上 | {m['stage']} |",
         f"| 主持／提问 | {m['host']} |",
         f"| 议程 | {m['agenda']} |",
         f"| 官方页面 | [CNBC · {year} Annual Meeting]({m['hub_url']}) |",
         "", "## 快速入口\n",
         "| 资源 | 链接 |", "|---|---|"] + quick + ["", "## 本届的关键事件\n"]
    L += [f"{i}. {x}" for i, x in enumerate(cfg["readme"]["key_events"], 1)]
    L += ["", "## 目录\n", "```", f"{year}/",
          "├── index.md                     # 本文件：年度概览"]
    if lc:
        L += [f"├── shareholder-letter-zh.md     # {lc['source_year']} 年致股东信：完整中文译文",
              f"├── shareholder-letter-en.md     # {lc['source_year']} 年致股东信：英文全文"]
    L += ["├── morning/                     # 上午场",
          f"│   ├── index.md                 # 索引：{n_m} 个问答（主题、时间戳、要点）",
          f"│   ├── q01…q{n_m:02d}-*.md             # 每个文件 = 一个提问"]
    app_m = cfg["sessions"]["morning"].get("appendix", {})
    for i, a in enumerate(app_m.values()):
        branch = "│   └──" if i == len(app_m) - 1 else "│   ├──"
        L.append(f"{branch} {a['file']:<25}# {a['label'].replace(' · ', '：')}")
    L += ["└── afternoon/                   # 下午场",
          f"    ├── index.md                 # 索引：{n_a} 个问答（主题、时间戳、要点）",
          f"    ├── q01…q{n_a:02d}-*.md"]
    app_a = cfg["sessions"]["afternoon"].get("appendix", {})
    for i, a in enumerate(app_a.values()):
        branch = "    └──" if i == len(app_a) - 1 else "    ├──"
        L.append(f"{branch} {a['file']:<25}# {a['label'].replace(' · ', '：')}")
    pairs = [(cfg["sessions"]["morning"]["label"], n_m), (cfg["sessions"]["afternoon"]["label"], n_a)]
    scale = f"**规模**：{' + '.join(f'{lbl} {n} 问' for lbl, n in pairs if n)} = " \
            f"**{n_m + n_a} 个问答片段**"
    zero = [lbl for lbl, n in pairs if not n]
    if zero:
        scale += f"（{'、'.join(zero)}无问答环节）"
    L += ["```", "", scale + f"，另有 {len(app_m) + len(app_a)} 个非问答附件。", "",
          "## 主题索引\n", "| 主题 | 相关片段 |", "|---|---|"]
    for t in sorted([x for x in tagmap if len(tagmap[x]) >= 2], key=lambda x: (-len(tagmap[x]), x)):
        items = "、".join(
            f"[{'上午' if sess == 'morning' else '下午'} Q{(gq if sess == 'morning' else gq - n_m):02d}]({fn})"
            for gq, sess, _, fn in tagmap[t])
        L.append(f"| `#{t}` | {items} |")
    L += ["", "## 数据来源与口径（重要）\n"]
    L += cfg["readme"]["sources"]
    L += ["", "## 已知缺口\n"]
    L += [f"- {x}" for x in cfg["readme"]["gaps"]]
    L += ["", "返回：[历年股东大会索引](../index.md) · [资料集总说明](../../README.md)"]
    target = out_dir(root, year) / "index.md"
    target.write_text("\n".join(L), encoding="utf-8")
    print(f"readme -> {target} ({len(tagmap)} tags)")
