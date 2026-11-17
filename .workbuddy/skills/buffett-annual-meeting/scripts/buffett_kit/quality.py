# -*- coding: utf-8 -*-
"""Translation quality gates: `lint` (readability defects) and `normalize` (canonical names).

The build pipeline happily accepts a translation that is turn-aligned and
verbatim-quoted yet reads like an English sentence with Chinese words in it.
These two commands target exactly that gap:

  lint       report per-turn readability defects (dash asides, monster sentences,
             unsplit paragraphs, shredded quotes, mixed name spellings)
  normalize  rewrite person names to the canonical table, idempotently
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from pathlib import Path

from .common import config_path, dump_json, load_json, root_path, year_paths, load_config

# --- thresholds (tuned on the 2020-2024 corpus; see SKILL.md 中文表达规范) ---
DASH_MAX = 4          # "——" occurrences per turn (2 pairs)
SENT_MAX = 90         # chars per sentence before it counts as a monster
PARA_MAX = 400        # chars per paragraph before it needs a break
TURN_MAX = 600        # chars per turn before it needs a paragraph break
RATIO_LO, RATIO_HI = 1.05, 2.30  # idiomatic spoken-EN -> zh lands around 1.1-1.8   # zh chars / en word

# Canonical person names. Longest pattern first so "Greg Abel" wins over "Greg".
NAMES = {
    "Warren Buffett": "沃伦·巴菲特",
    "Greg Abel": "格雷格·阿贝尔",
    "Ajit Jain": "阿吉特·贾因",
    "Charlie Munger": "查理·芒格",
    "Becky Quick": "贝基·奎克",
    "Ted Weschler": "泰德·韦施勒",
    "Todd Combs": "托德·康姆斯",
    "Elon Musk": "埃隆·马斯克",
    "Jim Simons": "吉姆·西蒙斯",
    "Jack Ringwalt": "杰克·林沃特",
    "Bill Gates": "比尔·盖茨",
    "Greg": "格雷格",
    "Ajit": "阿吉特",
    "Becky": "贝基",
    "Charlie": "查理",
    "Elon": "埃隆",
    "Jack": "杰克",
    "Leo": "利奥",
}
# Known variant spellings that must collapse into the canonical form.
VARIANTS = {
    "亚伯": "阿贝尔",
    "埃布尔": "阿贝尔",
    "杰恩": "贾因",
    "波克夏": "伯克希尔",
    "盖可保险": "GEICO",
    "盖可": "GEICO",
}

# English that is allowed to stay in the Chinese text.
LATIN_OK = {
    "GEICO", "BNSF", "BHE", "Pilot", "GAAP", "S&P", "AI", "CEO", "GDP", "FDIC",
    "TTI", "NFM", "PacifiCorp", "Progressive", "Alleghany", "NetJets", "Markel",
    "OXY", "Occidental", "Paramount", "Global", "Snowflake", "Activision",
    "Microsoft", "Apple", "Coca-Cola", "American", "Express", "Moody", "Moodys",
    "Dairy", "Queen", "Clayton", "Homes", "McLane", "Lubrizol", "Marmon",
    "Precision", "Castparts", "Shaw", "Walmart", "Costco", "Amazon", "Tesla",
    "Bitcoin", "bitcoin", "CNBC", "Yahoo", "HomeServices", "Garan", "Garanimals",
    "Berkshire", "Hathaway", "US", "SUV", "CPI", "IRA", "ETF", "See's",
    "Pacific", "Union", "Canadian", "National", "Bank", "America", "Home",
    "Services", "General", "Lee", "Airlines", "State", "Farm", "JPMorgan", "codicil",
    "Wells", "Fargo", "Goldman", "Sachs", "Kraft", "Heinz", "Verizon", "IBM",
    "Kroger", "Mars", "Wrigley", "Brooks", "Russell", "Johns", "Manville",
}
# Bare English given names left inside Chinese prose = the translator forgot to
# transliterate; these are the real defects, company names are not.
PERSON = {"Greg", "Becky", "Charlie", "Ajit", "Jack", "Ted", "Todd", "Leo",
          "Elon", "Warren", "Bill", "Joe", "Susan", "Carol", "Don", "Dave",
          "Steve", "Mark", "Paul", "Tom", "Jim", "Bob", "Ron", "Ben", "Lou"}

SENT_SPLIT = re.compile(r"(?<=[。！？；])")
NAME_RUN = re.compile(r"[A-Z][A-Za-z.&'\-]*(?:\s+[A-Z][A-Za-z.&'\-]*)*")
LOWER_WORD = re.compile(r"(?<![A-Za-z])[a-z][a-z'\-]{2,}(?![A-Za-z])")
# Swapping an English token for Chinese leaves the spaces that used to separate
# words; Chinese needs none between CJK characters.
_CJK = "\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
_SPACE_FIX = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}])")


def _trans_files(root: Path, year: int) -> list[Path]:
    # Prefer the config's convention path; lint/normalize also work on years
    # outside the toolkit scope (e.g. frozen 2025) that have no config.
    cfg_path = config_path(root, year)
    cfg = load_json(cfg_path) if cfg_path.exists() else {}
    return sorted(glob.glob(str(root / year_paths(cfg, year)["translations"] / "*.json")))


def _chapters(root: Path, year: int) -> dict:
    p = root / "_source" / str(year) / "transcript" / "chapters.json"
    if not p.exists():
        return {}
    return {c["n"]: c for c in load_json(p)}


def _turns_of(chapters: dict, key: str) -> list[dict] | None:
    """Translation arrays are keyed by chapter number, sometimes '12.1' for a split."""
    n = int(str(key).split(".")[0])
    c = chapters.get(n)
    return c["turns"] if c else None


def lint(root: Path, year: int) -> dict:
    chapters = _chapters(root, year)
    stats = Counter()
    details: dict[str, list[str]] = {
        "dash": [], "sentence": [], "paragraph": [], "quote": [], "latin": [],
        "ratio": [], "empty": [],
    }
    latin_seen: Counter = Counter()
    ratio_samples: list[float] = []

    for f in _trans_files(root, year):
        for key, arr in load_json(Path(f)).items():
            turns = _turns_of(chapters, key)
            for i, zh in enumerate(arr):
                stats["turns"] += 1
                zh = (zh or "").strip()
                if not zh:
                    details["empty"].append(f"{Path(f).name}:{key}[{i}]")
                    continue
                chars = len(re.sub(r"\s", "", zh))
                stats["chars"] += chars

                if zh.count("——") > DASH_MAX:
                    details["dash"].append(f"{Path(f).name}:{key}[{i}] ——×{zh.count('——')}")
                    stats["bad_dash"] += 1

                sents = [s for s in SENT_SPLIT.split(zh) if s.strip()]
                long_sents = [s for s in sents if len(re.sub(r"\s", "", s)) > SENT_MAX]
                if long_sents:
                    details["sentence"].append(
                        f"{Path(f).name}:{key}[{i}] 最长句 {max(len(s) for s in long_sents)} 字")
                    stats["bad_sentence"] += 1

                paras = [p for p in zh.split("\n\n") if p.strip()]
                if chars > TURN_MAX and len(paras) == 1:
                    details["paragraph"].append(f"{Path(f).name}:{key}[{i}] {chars} 字未分段")
                    stats["bad_paragraph"] += 1
                if max((len(re.sub(r"\s", "", p)) for p in paras), default=0) > PARA_MAX:
                    stats["bad_paragraph_block"] += 1

                if '」「' in zh:
                    details["quote"].append(f"{Path(f).name}:{key}[{i}] 引语被切碎")
                    stats["bad_quote"] += 1

                bad = []
                for run in NAME_RUN.findall(zh):
                    # a lone given name left in English is a miss; full names
                    # (e.g. shareholder "Ben Knoll") legitimately stay in English
                    if " " not in run.strip() and run.strip().rstrip(".") in PERSON:
                        bad.append(run)
                for w in LOWER_WORD.findall(zh):
                    if w not in LATIN_OK:
                        bad.append(w)
                for w in bad:
                    latin_seen[w] += 1
                    stats["latin_hits"] += 1

                if turns and i < len(turns):
                    words = len(turns[i]["text"].split())
                    if words >= 20:
                        r = chars / words
                        ratio_samples.append(r)
                        if not RATIO_LO <= r <= RATIO_HI:
                            details["ratio"].append(
                                f"{Path(f).name}:{key}[{i}] {chars}字/{words}词={r:.2f}")
                            stats["bad_ratio"] += 1

    if ratio_samples:
        ratio_samples.sort()
        stats["ratio_median"] = round(ratio_samples[len(ratio_samples) // 2], 2)
    details["latin"] = [f"{w}×{c}" for w, c in latin_seen.most_common(30)]
    return {"stats": stats, "details": details}


def _report(year: int, res: dict) -> None:
    s, d = res["stats"], res["details"]
    turns = max(s["turns"], 1)
    print(f"lint {year}: {s['turns']} 轮 / {s['chars']} 字 / 中英比中位 {s.get('ratio_median')}")
    for key, label in (("bad_dash", "破折号成灾"), ("bad_sentence", "超长句"),
                       ("bad_paragraph", "整轮不分段"), ("bad_quote", "引语拆碎"),
                       ("bad_ratio", "长度比异常"), ("empty", "空译文")):
        n = s.get(key, 0)
        flag = "!" if n else " "
        print(f" {flag} {label:8s} {n:4d} 轮  {n / turns * 100:5.1f}%")
    if d["latin"]:
        print(f"   残留英文（前三）{'、'.join(d['latin'][:3])}")
    for group in ("empty", "quote", "dash", "paragraph", "sentence", "ratio"):
        if d[group]:
            print(f"   {group} 例：")
            for line in d[group][:5]:
                print(f"     - {line}")


def cmd_lint(args) -> None:
    root = root_path(args.root)
    _report(args.year, lint(root, args.year))


def _apply(text: str, table: dict[str, str]) -> str:
    """Replace names outside of （...） spans: the parenthetical usually IS the original
    English beside a transliterated name, e.g. 查理·王（Charlie Wang）."""
    parts = re.split(r"(（[^）]*）)", text)
    for idx in range(0, len(parts), 2):          # even indexes are outside parens
        for src in sorted(table, key=len, reverse=True):
            parts[idx] = re.sub(rf"(?<![A-Za-z]){re.escape(src)}(?![A-Za-z])",
                                table[src], parts[idx])
    return _SPACE_FIX.sub("", "".join(parts))


def cmd_normalize(args) -> None:
    """Rewrite names in the translation JSON (never the md) and report the diff count."""
    root = root_path(args.root)
    changed_files = 0
    changed_turns = 0
    for f in _trans_files(root, args.year):
        data = load_json(Path(f))
        touched = False
        for key, arr in data.items():
            for i, zh in enumerate(arr):
                new = _apply(zh, VARIANTS)
                new = _apply(new, NAMES)
                new = new.replace("阿吉特·贾因·贾因", "阿吉特·贾因")
                if new != zh:
                    arr[i] = new
                    changed_turns += 1
                    touched = True
        if touched:
            dump_json(data, f)
            changed_files += 1
    print(f"normalize {args.year}: {changed_turns} 轮改写，{changed_files} 个文件")
