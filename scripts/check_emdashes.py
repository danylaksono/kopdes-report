#!/usr/bin/env python3
"""
Detect and list em-dashes (—) in the public-facing pages of the report site.

Background: the published report is written without em-dashes in prose — they
are paraphrased away (see AGENTS.md, "No em-dashes in published copy"). This
script is the enforcement tool. It scans the public-facing pages, lists every
occurrence with file, line and the containing sentence, and exits non-zero if
any are found so it can gate a pre-commit hook or CI check.

What it scans by default — the published pages:
  * every *.html in the site tree (/, /explore/, /tabel/, /periksa/,
    /findings/, /methods/, /data/, /about/)
  * methods/_content/**/*.md     — the runtime-rendered method prose
  * methods/_figures/**/*.svg    — hand-authored diagrams

With --code it also scans app/**/*.js for em-dashes *inside string literals*
(UI copy that renders: tooltips, hints, inspector text). Comments are skipped,
so comment prose never counts. Best-effort: a JS regex literal containing a
quote could be misread as a string start — that only ever produces a false
positive for manual review, never a missed em-dash.

Deliberate non-prose uses (a "no data" cell, the rail placeholder) are listed
too; they are not sentences and are not meant to be paraphrased.

Usage:
  python scripts/check_emdashes.py            # scan pages, exit 1 if any found
  python scripts/check_emdashes.py --code     # also check JS UI strings
  python scripts/check_emdashes.py --report   # always exit 0 (reporting mode)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EMDASH = "\u2014"
# HTML entity forms that render as an em-dash
ENTITIES = ("&mdash;", "&#8212;", "&#x2014;")

PAGE_GLOBS = [
    "*.html",
    "explore/**/*.html",
    "tabel/**/*.html",
    "periksa/**/*.html",
    "findings/**/*.html",
    "methods/**/*.html",
    "data/**/*.html",
    "about/**/*.html",
    "methods/_content/**/*.md",
    "methods/_figures/**/*.svg",
]

CODE_GLOBS = ["app/**/*.js"]


def iter_files(globs):
    for pattern in globs:
        yield from ROOT.glob(pattern)


def split_sentences(line):
    """Split a physical line into sentence-ish segments, keeping the
    terminator. A trailing segment with no terminator is kept too."""
    parts = []
    buf = ""
    for ch in line:
        buf += ch
        if ch in ".!?\u2026":
            parts.append(buf)
            buf = ""
    if buf.strip():
        parts.append(buf)
    return parts


def containing_sentence(line, col):
    """Return the sentence segment of `line` that contains column `col`
    (0-based), falling back to the trimmed line."""
    parts = split_sentences(line)
    if len(parts) <= 1:
        return line.strip()
    acc = 0
    for part in parts:
        if acc <= col < acc + len(part):
            return part.strip()
        acc += len(part)
    return line.strip()


def find_emdashes(text):
    """Yield (line_no, col, sentence) for every em-dash / em-dash entity in
    `text`. line_no is 1-based."""
    lines = text.splitlines(keepends=True)
    offset = 0
    for line_no, line in enumerate(lines, start=1):
        for ch in (EMDASH,) + ENTITIES:
            start = 0
            while True:
                col = line.find(ch, start)
                if col == -1:
                    break
                yield line_no, col, containing_sentence(line, col)
                start = col + 1
        offset += len(line)


def _is_regex_start(text, i):
    """Best-effort: is the '/' at index i the start of a regex literal rather
    than a division? Looks at the previous significant character."""
    j = i - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    if j < 0:
        return True
    return text[j] in "(,=:[!&|?{};+*%^~<>'\"`"


def scan_regex(text, i, n):
    """Consume a regex literal beginning at the '/' at index i; return the
    index just past the closing '/'. Handles escapes and [...] classes."""
    j = i + 1
    in_class = False
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            return j + 1
        elif ch == "\n":
            return j  # malformed; stop at the line break
        j += 1
    return n


def scan_js(text):
    """Yield (line_no, col, sentence) for every em-dash inside a JS string
    literal ('...', "...", `...`), including multi-line template literals and
    nested ${...} interpolations.

    Frames on a stack: code | line | block | str | tpl | interp(depth).
    Comments are consumed as their own states, so a quote or backtick inside a
    comment can never open a string. Regex literals are recognised (best
    effort) so a { } or quote inside one cannot derail the brace or string
    tracking; the one weak spot is a regex after a `return`-style keyword,
    which only ever adds a line for manual review, never hides a rendered
    em-dash.
    """
    i, n = 0, len(text)
    stack = [("code", 0)]
    hits = []

    while i < n:
        kind, extra = stack[-1]
        ch = text[i]

        if kind == "line":
            if ch == "\n":
                stack.pop()
            i += 1
            continue
        if kind == "block":
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                stack.pop()
                i += 2
                continue
            i += 1
            continue
        if kind == "str":
            if ch == "\\":
                i += 2
                continue
            if ch == extra:  # closing quote
                stack.pop()
                i += 1
                continue
            if ch == "\n":  # unterminated ' or " ends at the line break
                stack.pop()
                continue
            if ch == EMDASH:
                hits.append(i)
            i += 1
            continue
        if kind == "tpl":
            if ch == "\\":
                i += 2
                continue
            if ch == "`":
                stack.pop()
                i += 1
                continue
            if ch == "$" and i + 1 < n and text[i + 1] == "{":
                stack.append(("interp", 1))
                i += 2
                continue
            if ch == EMDASH:
                hits.append(i)
            i += 1
            continue
        if kind == "interp":
            if ch == "/" and i + 1 < n and text[i + 1] in ("/", "*"):
                stack.append(("line" if text[i + 1] == "/" else "block", 0))
                i += 2
                continue
            if ch == "/" and _is_regex_start(text, i):
                i = scan_regex(text, i, n)
                continue
            if ch == "{":
                stack[-1] = ("interp", extra + 1)
                i += 1
                continue
            if ch == "}":
                if extra == 1:
                    stack.pop()
                else:
                    stack[-1] = ("interp", extra - 1)
                i += 1
                continue
            if ch in ("'", '"', "`"):
                stack.append(("str" if ch != "`" else "tpl", ch if ch != "`" else 0))
                i += 1
                continue
            i += 1
            continue
        # code
        if ch == "/" and i + 1 < n and text[i + 1] in ("/", "*"):
            stack.append(("line" if text[i + 1] == "/" else "block", 0))
            i += 2
            continue
        if ch == "/" and _is_regex_start(text, i):
            i = scan_regex(text, i, n)
            continue
        if ch in ("'", '"', "`"):
            stack.append(("str" if ch != "`" else "tpl", ch if ch != "`" else 0))
            i += 1
            continue
        i += 1

    lines = text.splitlines()
    results = []
    for i_abs in hits:
        line_no = text.count("\n", 0, i_abs) + 1
        line_start = text.rfind("\n", 0, i_abs) + 1
        col = i_abs - line_start
        line_text = lines[line_no - 1] if line_no - 1 < len(lines) else ""
        results.append((line_no, col, containing_sentence(line_text, col)))
    return results



def scan_file(path):
    """Return (file, [ (line, col, sentence), ... ])."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"!! cannot read {path}: {exc}", file=sys.stderr)
        return path, []
    if path.suffix == ".js":
        return path, list(scan_js(text))
    return path, list(find_emdashes(text))


def main(argv=None):
    # Force UTF-8 output: without this, a cp1252 Windows console renders the
    # em-dash (and curly quotes) as mojibake.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--code",
        action="store_true",
        help="also scan app/**/*.js for em-dashes inside string literals",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="always exit 0 (reporting mode, for documentation use)",
    )
    args = parser.parse_args(argv)

    globs = list(PAGE_GLOBS)
    if args.code:
        globs += CODE_GLOBS

    results = {}
    total = 0
    for path in sorted(iter_files(globs)):
        _, hits = scan_file(path)
        if hits:
            results[path] = hits
            total += len(hits)

    if not results:
        print("No em-dashes found in public-facing pages.")
        return 0 if not args.report else 0

    for path in sorted(results):
        hits = results[path]
        print(f"\n{path}  ({len(hits)})\n" + "-" * 60)
        for line_no, col, sentence in hits:
            print(f"  {line_no}:{col + 1}  {sentence}")

    print(f"\n{'=' * 60}\n{total} em-dash occurrence(s) in "
          f"{len(results)} public-facing file(s).")
    if not args.report:
        print("Rewrite the prose without em-dashes (see AGENTS.md).")
    return 0 if args.report else 1


if __name__ == "__main__":
    sys.exit(main())
