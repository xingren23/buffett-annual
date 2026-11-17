# -*- coding: utf-8 -*-
"""CLI entry point for the Buffett annual-meeting toolkit."""
from __future__ import annotations

import argparse
import sys

from . import cnbc, letter, qa, quality, readme, validate
from .common import YEAR_MAX, YEAR_MIN, load_config, root_path


def _year(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("year must be an integer, e.g. 2024")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="buffett",
        description=f"Build a Buffett annual-meeting Markdown dataset ({YEAR_MIN}-{YEAR_MAX}).")
    p.add_argument("--root", default=None, help="workspace root (default: cwd)")
    p.add_argument("--year", type=_year, required=True, help="meeting year, e.g. 2024")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="write a year-config skeleton from the CNBC hub")
    i.add_argument("--hub", default=None, help="override the CNBC hub URL")
    i.add_argument("--force", action="store_true", help="overwrite an existing config")
    i.set_defaults(func=cnbc.cmd_init)

    pr = sub.add_parser("prepare", help="fetch + extract + letter-extract in one pass")
    pr.add_argument("--force", action="store_true", help="re-download sources")
    pr.set_defaults(func=cmd_prepare)

    c = sub.add_parser("check", help="verify the Chinese JSON before building")
    c.set_defaults(func=validate.cmd_check)

    b = sub.add_parser("build", help="check + write pages/indexes/letter/index + validate")
    b.add_argument("--no-validate", action="store_true")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("validate", help="check links and output coverage after a build")
    v.set_defaults(func=validate.cmd_validate)

    li = sub.add_parser("lint", help="readability pass over data/<year>/zh (dash/sentence/paragraph/quote/ratio)")
    li.set_defaults(func=quality.cmd_lint)

    no = sub.add_parser("normalize", help="unify person names in data/<year>/zh to the canonical table")
    no.set_defaults(func=quality.cmd_normalize)

    # Granular steps, for repairing one stage without redoing the rest.
    for name, func, help_text in (
        ("fetch", cnbc.cmd_fetch, "download CNBC pages and the letter PDF"),
        ("extract", cnbc.cmd_extract, "parse CNBC chapters/transcripts into chapters.json"),
        ("scaffold", cnbc.cmd_scaffold, "write English question candidates + batch plan"),
        ("letter-extract", letter.cmd_extract, "parse the letter PDF into sections/paragraphs"),
    ):
        s = sub.add_parser(name, help=help_text)
        s.set_defaults(func=func)
        if name == "fetch":
            s.add_argument("--force", action="store_true")
    return p


def cmd_prepare(args) -> None:
    root = root_path(args.root)
    cfg = load_config(root, args.year)
    cnbc.cmd_fetch(argparse.Namespace(root=args.root, year=args.year, force=args.force))
    cnbc.cmd_extract(args)
    if cfg.get("letter"):
        letter.cmd_extract(args)
    print(f"\nprepared {args.year}. Next: choose question chapters into "
          f"data/{args.year}/config.json, then run scaffold.")


def cmd_build(args) -> None:
    root = root_path(args.root)
    cfg = load_config(root, args.year)
    errors, warnings = validate.content(root, args.year)
    for w in warnings:
        print(f"check: warn {w}")
    if errors:
        print(f"check: FAIL ({len(errors)})")
        for e in errors[:40]:
            print(" -", e)
        if len(errors) > 40:
            print(f" ... and {len(errors) - 40} more")
        raise SystemExit(1)
    print("check: OK")
    qa.build(root, args.year)
    if cfg.get("letter"):
        letter.build(root, args.year)
    readme.build(root, args.year)
    if not args.no_validate:
        errs, _ = validate.build(root, args.year)
        if errs:
            print("validate: FAIL")
            for e in errs:
                print(" -", e)
            raise SystemExit(1)
        print("validate: OK")


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
