#!/usr/bin/env python3
"""Skill_Find — index and search local Python tools and skills by their docstrings.

Skill_Find walks a directory tree, extracts the leading docstring from every
.py file and the headings from every README.md, and writes a lightweight
index.json. You can then search that index by token overlap and substring
matching, or list everything that was indexed — a local, offline,
zero-dependency skill/tool finder for any agent or developer workspace.

Domains: Agentic AI · Developer Tooling · Knowledge Management.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time

DEFAULT_INDEX = "index.json"

# Matches Markdown ATX headings (e.g. "# Title", "### Subsection").
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# Matches a leading triple-quoted string literal (used only as a fallback).
_TRIPLE_QUOTE_RE = re.compile(r"^\s*(?:\'\'\'|\"\"\")(.*?)(?:\'\'\'|\"\"\")", re.DOTALL)


def _tokenize(text):
    """Return lowercase alphanumeric tokens from free text (punctuation stripped)."""
    return re.findall(r"[a-z0-9_]+", (text or "").lower())


def _extract_python(path):
    """Return (summary, full_docstring) for a .py file, or (None, None).

    Uses ast for the module docstring; falls back to a regex scan when the
    source does not parse (stray bytes, non-Python content, etc.).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return None, None
    doc = None
    try:
        doc = ast.get_docstring(ast.parse(src))  # clean=True normalises indentation
    except (SyntaxError, ValueError):
        m = _TRIPLE_QUOTE_RE.search(src)
        if m:
            doc = m.group(1)
    if not doc:
        return None, None
    doc = doc.strip()
    summary = doc.split("\n", 1)[0].strip()
    return summary or None, doc


def _extract_readme(path):
    """Extract the title, headings and opening blurb from a README.md file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.strip() for ln in fh.read().splitlines()]
    except OSError:
        return None
    title = None
    headings = []
    blurb = []
    for ln in lines:
        m = _HEADING_RE.match(ln)
        if m:
            text = m.group(2).strip()
            if title is None:
                title = text
            headings.append(text)
            continue
        # Only the opening paragraph (before the first heading) becomes the blurb.
        if ln and not headings:
            blurb.append(ln)
    return {"title": title, "headings": headings, "blurb": " ".join(blurb)}


def _walk_and_extract(root):
    """Walk a directory tree and build the list of index items."""
    items = []
    # Directories that are almost always noise for a skill/tool search.
    skip_dirs = {".git", "__pycache__", "node_modules", "venv", ".venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs and not d.startswith("."))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if fn.endswith(".py"):
                summary, doc = _extract_python(full)
                items.append({
                    "path": rel,
                    "type": "python",
                    "name": fn[:-3],
                    "description": summary or "(no docstring)",
                    "text": doc or "",
                })
            elif fn.lower() == "readme.md":
                rd = _extract_readme(full)
                if rd is None:
                    continue
                items.append({
                    "path": rel,
                    "type": "readme",
                    "name": rd["title"] or os.path.basename(dirpath),
                    "description": rd["blurb"] or rd["title"] or "(readme)",
                    "text": " ".join([rd["title"] or "", rd["blurb"], " ".join(rd["headings"])]),
                })
    return items


def _load_index(path):
    """Load an index.json, printing a clean error and returning None on failure."""
    if not os.path.isfile(path):
        print(f"Error: index not found: {path}. Run 'index <dir>' first.", file=sys.stderr)
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: could not read index {path}: {exc}", file=sys.stderr)
        return None


def _score(query, item):
    """Score an item against a query.

    Signals, strongest to weakest: exact phrase / whole-query substring,
    whole-word token overlap, partial substring, and name-only matches.
    """
    q = (query or "").lower().strip()
    q_tokens = _tokenize(q)
    name = item.get("name", "").lower()
    corpus = " ".join([name, item.get("description", ""), item.get("text", "")]).lower()
    corpus_tokens = set(_tokenize(corpus))

    score = 0.0
    if q and q in corpus:          # whole query appears verbatim
        score += 5.0
    for tok in q_tokens:
        if tok in corpus_tokens:   # whole-word match
            score += 2.0
        elif tok in corpus:        # partial/embedded substring
            score += 0.5
        if tok in name:            # name hits are weighted up
            score += 1.0
    return score


def _emit_json(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_index(args):
    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        print(f"Error: not a directory: {args.dir}", file=sys.stderr)
        return 1
    items = _walk_and_extract(root)
    payload = {
        "root": root,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(items),
        "items": items,
    }
    try:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
    except OSError as exc:
        print(f"Error: could not write {args.output}: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        _emit_json({"output": args.output, "root": root, "indexed": len(items)})
    else:
        print(f"Indexed {len(items)} item(s) from {root} -> {args.output}")
    return 0


def cmd_search(args):
    data = _load_index(args.index)
    if data is None:
        return 1
    items = data.get("items", [])
    scored = [(s, it) for it in items if (s := _score(args.query, it)) > 0]
    # Highest score first; ties broken deterministically by path.
    scored.sort(key=lambda t: (-t[0], t[1].get("path", "")))
    top = scored[: args.top]
    out = [
        {
            "rank": rank,
            "score": round(s, 2),
            "path": it.get("path", ""),
            "type": it.get("type", ""),
            "name": it.get("name", ""),
            "description": it.get("description", ""),
        }
        for rank, (s, it) in enumerate(top, 1)
    ]
    if args.format == "json":
        _emit_json({"query": args.query, "results": out})
    else:
        if not out:
            print(f"No matches for '{args.query}'.")
        for r in out:
            desc = r["description"].replace("\n", " ")[:60]
            print(f"{r['rank']:>2}. [{r['score']:>5.2f}] {r['path']:30} ({r['type']:6}) {desc}")
    return 0


def cmd_list(args):
    data = _load_index(args.index)
    if data is None:
        return 1
    items = data.get("items", [])
    if args.format == "json":
        _emit_json({"count": len(items), "items": items})
    else:
        print(f"{len(items)} indexed item(s):")
        for it in items:
            desc = (it.get("description") or "").replace("\n", " ")[:60]
            print(f"  [{it.get('type'):6}] {it.get('path'):30} - {desc}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="Skill_Find",
        description=__doc__.split("\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Shared parent parser so --format is accepted after every subcommand
    # (putting it only on the top-level parser would break `skill_find search x --format json`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")

    sub = p.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", parents=[common],
                             help="Walk a directory and write an index.json")
    p_index.add_argument("dir", help="Directory tree to index")
    p_index.add_argument("-o", "--output", default=DEFAULT_INDEX,
                         help=f"Index file to write (default: {DEFAULT_INDEX})")
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", parents=[common],
                              help="Search the index for a query")
    p_search.add_argument("query", help="Search terms")
    p_search.add_argument("-i", "--index", default=DEFAULT_INDEX,
                          help=f"Index file to read (default: {DEFAULT_INDEX})")
    p_search.add_argument("-n", "--top", type=int, default=10,
                          help="Maximum results to return (default: 10)")
    p_search.set_defaults(func=cmd_search)

    p_list = sub.add_parser("list", parents=[common],
                            help="List every indexed item")
    p_list.add_argument("-i", "--index", default=DEFAULT_INDEX,
                        help=f"Index file to read (default: {DEFAULT_INDEX})")
    p_list.set_defaults(func=cmd_list)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)  # parse exactly once
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
