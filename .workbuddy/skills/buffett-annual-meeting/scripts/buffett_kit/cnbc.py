# -*- coding: utf-8 -*-
"""Fetch CNBC pages and normalize chapters / speaker turns."""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
from pathlib import Path

from .common import check_year, clean, config_path, dump_json, load_config, root_path, ts, year_paths

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SPEAKER = re.compile(r"^([A-Z][A-Z .'\-]{2,40}):\s*")
ASKERS = ("Becky Quick", "Audience Member", "Audience Question", "Audience", "Shareholder")
SPEAKER_FIX = {"Audince Member": "Audience Member", "Audince Question": "Audience Question"}


def fetch(url: str, dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force:
        print(f"skip  {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception as e:
        raise SystemExit(f"fetch failed: {url}\n  {e}")
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    dest.write_bytes(data)
    print(f"fetch {dest}  {len(data)/1024:.0f} KB")
    return dest


def cache(html: str) -> dict:
    i = html.find("window.__c_data=")
    if i < 0:
        raise ValueError("window.__c_data not found; CNBC page layout changed")
    obj, _ = json.JSONDecoder().raw_decode(html[i + len("window.__c_data="):])
    return obj


def repair(s: str) -> str:
    """Undo CNBC's UTF-8-as-cp1252 mojibake (e.g. â€™ -> ’)."""
    if "â" not in s and "Ã" not in s:
        return s
    for enc in ("latin-1", "cp1252"):
        try:
            out = s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if out.count("\ufffd") <= s.count("\ufffd"):
            return out
    return s


def transcript_obj(data: dict) -> dict:
    keys = [k for k in data if k.endswith(".transcript")]
    if not keys:
        raise ValueError("no transcript object in page cache")
    for k in keys:
        v = data[k]
        if isinstance(v, dict) and v.get("chapters"):
            return v
    raise ValueError("transcript object has no chapters")


def chapters(data: dict) -> list[dict]:
    v = transcript_obj(data)
    out = []
    for ref in v["chapters"]:
        obj = data.get(ref.get("id")) if isinstance(ref, dict) and "id" in ref else ref
        if not obj:
            raise ValueError(f"unresolved chapter ref: {ref}")
        out.append(obj)
    return out


def turns(ch: dict) -> list[dict]:
    out: list[dict] = []
    for seg in (ch.get("transcript") or {}).get("json") or []:
        text = clean(repair(str(seg.get("title", ""))))
        if not text:
            continue
        m = SPEAKER.match(text)
        if m:
            name = m.group(1).title()
            out.append({"ts": seg.get("in", 0), "speaker": SPEAKER_FIX.get(name, name),
                        "text": text[m.end():].strip()})
        elif out:
            out[-1]["text"] = (out[-1]["text"] + " " + text).strip()
        else:
            out.append({"ts": seg.get("in", 0), "speaker": "Unknown", "text": text})
    return out


def extract_page(path: Path, session: str, start_n: int) -> list[dict]:
    data = cache(path.read_text(encoding="utf-8", errors="ignore"))
    out = []
    for i, ch in enumerate(chapters(data), 1):
        out.append({
            "n": start_n + i - 1,
            "session": session,
            "title": clean(repair(str(ch.get("title", "")))),
            "in": ch.get("in", 0),
            "out": ch.get("out", 0),
            "turns": turns(ch),
        })
    return out


def cmd_fetch(args) -> None:
    root = root_path(args.root)
    cfg = load_config(root, args.year)
    m = cfg["meeting"]
    base = root / "_source" / str(args.year)
    fetch(m["hub_url"], base / "cnbc" / "hub.html", args.force)
    fetch(m["morning_url"], base / "cnbc" / "morning.html", args.force)
    fetch(m["afternoon_url"], base / "cnbc" / "afternoon.html", args.force)
    letter = cfg.get("letter") or {}
    if letter.get("url"):
        fetch(letter["url"], base / "letter" / letter["pdf"], args.force)


# --- question references -----------------------------------------------------
# A question is a chapter number (12) or, for a chapter that packs several
# questions, a chapter plus a 1-based part ("12.2") backed by `splits`.


def parse_ref(ref) -> tuple[int, int]:
    text = str(ref).strip()
    if "." in text:
        ch, part = text.split(".", 1)
        return int(ch), int(part)
    return int(text), 0


def refkey(ref) -> str:
    ch, part = parse_ref(ref)
    return f"{ch}.{part}" if part else str(ch)


def question_turns(chapters: dict, ref, cont: dict | None = None,
                   splits: dict | None = None) -> list[dict]:
    """Turns for one question: the chapter (or its part) plus continuation chapters."""
    ch_n, part = parse_ref(ref)
    if ch_n not in chapters:
        raise SystemExit(f"chapter {ch_n} not in chapters.json (question {refkey(ref)})")
    turns = list(chapters[ch_n]["turns"])
    if part:
        ranges = (splits or {}).get(str(ch_n)) or []
        if not 1 <= part <= len(ranges):
            raise SystemExit(f"question {refkey(ref)} has no splits[{ch_n}][{part - 1}]")
        a, b = ranges[part - 1]
        turns = turns[int(a):int(b) if b is not None else None]
    key = refkey(ref)
    for k, v in (cont or {}).items():
        if refkey(v) == key:
            turns += chapters[int(k)]["turns"]
    return turns


def question_span(chapters: dict, ref, q_turns: list[dict],
                  cont: dict | None = None, splits: dict | None = None) -> tuple[int, int]:
    """Video span: whole chapters use chapter bounds, split parts stop at the next part."""
    ch_n, part = parse_ref(ref)
    c = chapters[ch_n]
    if part:
        ranges = (splits or {}).get(str(ch_n)) or []
        start = int(q_turns[0]["ts"]) if q_turns else c["in"]
        end = (int(c["turns"][int(ranges[part][0])]["ts"]) if part < len(ranges)
               else c["out"])
        return start, end
    conts = [int(k) for k, v in (cont or {}).items() if refkey(v) == refkey(ref)]
    return c["in"], max([c["out"]] + [chapters[k]["out"] for k in conts])


def cmd_extract(args) -> None:
    root = root_path(args.root)
    year = check_year(args.year)
    cfg = load_config(root, year)
    base = root / "_source" / str(year) / "cnbc"
    allch: list[dict] = []
    n = 1
    for session in ("morning", "afternoon"):
        part = extract_page(base / f"{session}.html", session, n)
        allch.extend(part)
        n += len(part)
    if not any(c["turns"] for c in allch):
        raise SystemExit(
            f"{year}: chapters carry no transcript segments. CNBC only has official "
            f"transcripts for {1994}-{2024}; this year needs an external transcript, "
            f"which this toolkit does not handle."
        )
    out = root / "_source" / str(year) / "transcript" / "chapters.json"
    dump_json(allch, out)
    print(f"chapters {len(allch)} -> {out}")
    for c in allch:
        print(f"{c['n']:02d} {c['session'][:1].upper()} {ts(c['in'])}-{ts(c['out'])} "
              f"{len(c['turns']):2d}t {c['title'][:60]}")


def _asker(turns: list[dict]) -> dict:
    for t in turns:
        if t["speaker"] in ASKERS:
            return t
    return turns[0] if turns else {"speaker": "", "text": ""}


SESSION_URL = re.compile(
    r"https://buffett\.cnbc\.com/video/\d{4}/\d{2}/\d{2}/"
    r"(morning-session|afternoon-session|part-1|part-2)[^\"']*\.html")
# CNBC renamed the two session videos over time; both spellings mean morning/afternoon.
SESSION_ALIAS = {"morning-session": "morning", "afternoon-session": "afternoon",
                 "part-1": "morning", "part-2": "afternoon"}


def cmd_init(args) -> None:
    """Write a year-config skeleton, reading the two session URLs off the CNBC hub."""
    root = root_path(args.root)
    year = check_year(args.year)
    dest = config_path(root, year)
    if dest.exists() and not getattr(args, "force", False):
        raise SystemExit(f"{dest} exists; pass --force to overwrite")
    hub = getattr(args, "hub", None) or \
        f"https://buffett.cnbc.com/{year}-berkshire-hathaway-annual-meeting/"
    page = root / "_source" / str(year) / "cnbc" / "hub.html"
    html = fetch(hub, page, True).read_text(encoding="utf-8", errors="ignore")
    urls = {}
    for m in SESSION_URL.finditer(html):
        urls.setdefault(SESSION_ALIAS[m.group(1)], m.group(0))
    missing = [s for s in ("morning", "afternoon") if s not in urls]
    if missing:
        raise SystemExit(f"no {'/'.join(missing)} session link on {hub}; pass --hub explicitly")
    cfg = {
        "year": year,
        "meeting": {
            "date": "", "date_zh": "", "location": "美国内布拉斯加州奥马哈 · CHI Health Center",
            "note": "", "stage": "", "host": "", "agenda": "",
            "hub_url": hub, "morning_url": urls["morning"], "afternoon_url": urls["afternoon"],
        },
        "sessions": {
            "morning": {"label": "上午场", "questions": [], "appendix": {}, "non_qa": {}},
            "afternoon": {"label": "下午场", "questions": [], "appendix": {}, "non_qa": {}},
        },
        "readme": {"key_events": [], "sources": [], "gaps": []},
        "transcript_note": f"{year} 年页面含官方逐字稿，英文原文照录，仅做分段与发言人整理",
    }
    dump_json(cfg, dest)
    print(f"config {dest}")
    print(f"  morning   {urls['morning']}")
    print(f"  afternoon {urls['afternoon']}")
    print("Fill meeting date/stage/host/agenda and readme, then run prepare.")


def cmd_scaffold(args) -> None:
    """Write English question candidates plus a batching plan."""
    root = root_path(args.root)
    year = check_year(args.year)
    cfg = load_config(root, year)
    chs = {c["n"]: c for c in json.loads(
        (root / "_source" / str(year) / "transcript" / "chapters.json").read_text(encoding="utf-8"))}
    items, plan = [], []
    for session, sc in cfg["sessions"].items():
        cont = {int(k): v for k, v in sc.get("continuations", {}).items()}
        splits = sc.get("splits", {})
        ns = []
        for ref in sc["questions"]:
            turns = question_turns(chs, ref, cont, splits)
            a = _asker(turns)
            items.append({
                "n": refkey(ref), "session": session,
                "chapter_title": chs[parse_ref(ref)[0]]["title"],
                "asker": a["speaker"], "question_en": a["text"],
                "turn_count": len(turns),
                "words": sum(len(t["text"].split()) for t in turns),
            })
            ns.append(refkey(ref))
        for i in range(0, len(ns), 7):
            plan.append({"file": f"{session[:1]}{i // 7 + 1:02d}.json", "n": ns[i:i + 7]})
    out = root / year_paths(cfg, year)["scaffold"]
    dump_json({"questions": items, "batches": plan}, out)
    print(f"scaffold {len(items)} questions, {len(plan)} batches -> {out}")
    for b in plan:
        print(f"  {b['file']:<8} {b['n'][0]}..{b['n'][-1]}")
