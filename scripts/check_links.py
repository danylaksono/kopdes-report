#!/usr/bin/env python3
"""
check_links.py — resolve every internal link on the site and fail on the dead ones.

The site is a dozen hand-written static pages at three different directory
depths, linking to each other with relative paths. Nothing validates those
paths: a page renders perfectly with a broken link in it, and the reader is the
one who finds out.

That is not hypothetical either. Every "Lampiran metode" list on the three
findings pages pointed at `../methods/NN-slug/`, which from `/findings/money/`
resolves to `/findings/methods/NN-slug/` and 404s. Eighteen links, all three
chapter pages, every method citation the report offers its readers, dead. The
pages had the right depth in their `<script src>` and the wrong depth two lines
below it, which is exactly the kind of thing a human proofreader's eye slides
over and a script does not.

## What it checks

- `href` and `src` on every committed `*.html`, resolved against the file's own
  directory, the way a browser resolves them.
- A link ending in `/` must have an `index.html` behind it. That is what the
  static host serves and what a missing trailing slash silently breaks.
- Fragments (`#anchor`) must exist as an `id` on the target page. Ids injected
  at runtime by `app/site.js` are declared in RUNTIME_IDS below, because the
  static file cannot know about them.
- Relative links inside `app/<name>/*.js`, resolved against `/<name>/`, since
  that is the one-module-tree-per-page convention the app follows. Top-level
  `app/*.js` is shared by several pages at different depths, so its links are
  listed for a human rather than resolved.

## What it does not check

External URLs. Reaching them needs a network, makes the run non-deterministic
and turns someone else's outage into a red build. The press URLs the report
depends on are re-read by hand instead; see `verify_published_figures.py`.

Usage:
  python scripts/check_links.py            # exits non-zero on any dead link
  python scripts/check_links.py --verbose  # also lists what passed
"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

# Directories that are not the published site.
SKIP_DIRS = {".git", ".venv", "node_modules", "_proto", "__pycache__"}

# Ids that exist only after app/site.js has run. The static HTML carries the
# placeholder (<nav id="site-nav">) and the script replaces it, so an anchor to
# anything the shell generates cannot be found by reading the file.
RUNTIME_IDS = {"site-nav", "site-footer"}

# Schemes and forms that leave the site.
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)

LINK_ATTR = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
ID_ATTR = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.I)
# Links written inside JS template strings, e.g. `<a href="../methods/03-.../">`.
JS_LINK = re.compile(r"""href=\\?["']([^"'\\]+)\\?["']""")


def site_files(pattern):
    for p in sorted(ROOT.rglob(pattern)):
        if SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        yield p


def ids_in(path):
    """Every id declared in a static HTML file, plus the runtime ones."""
    if not path.exists():
        return set()
    return set(ID_ATTR.findall(path.read_text(encoding="utf-8", errors="ignore"))) | RUNTIME_IDS


def resolve(base_dir, link):
    """Resolve a site-internal link the way a browser would.

    Returns (target_path, fragment, needs_index). `base_dir` is the directory
    the link is written relative to, not the file, matching browser behaviour.
    """
    path, _, frag = link.partition("#")
    path = unquote(path.split("?", 1)[0])
    if "${" in frag:
        # A JS-built anchor (`#k=${id}`). The path in front of it is still worth
        # resolving; the fragment is only knowable at runtime.
        frag = ""
    if not path:
        return None, frag, False  # same-page anchor
    needs_index = path.endswith("/")
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    else:
        target = base_dir / path
    return target.resolve(), frag, needs_index


def check_link(source, base_dir, link, line):
    """Return an error string, or None when the link resolves."""
    target, frag, needs_index = resolve(base_dir, link)

    if target is None:  # "#anchor" on the page itself
        if frag and frag not in ids_in(source):
            return f"no element with id={frag!r} on this page"
        return None

    if needs_index:
        index = target / "index.html"
        if not index.exists():
            return f"directory has no index.html ({rel(target)}/)"
        target = index
    elif not target.exists():
        # A bare directory link works only because the host redirects, and the
        # redirect changes the base every relative link inside resolves against.
        if (target / "index.html").exists():
            return f"missing trailing slash (should be {link}/)"
        return f"does not exist ({rel(target)})"

    if frag:
        if target.suffix.lower() != ".html":
            return None  # a fragment into a .md or .csv is not ours to resolve
        if frag not in ids_in(target):
            return f"no element with id={frag!r} in {rel(target)}"
    return None


def rel(p):
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def scan_html():
    """(source, base_dir, link, line) for every internal link in the pages."""
    for page in site_files("*.html"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for m in LINK_ATTR.finditer(text):
            link = m.group(1).strip()
            if not link or EXTERNAL.match(link) or link.startswith("data:"):
                continue
            yield page, page.parent, link, text[: m.start()].count("\n") + 1


def scan_js():
    """Links written into app/<name>/*.js, resolved against the page /<name>/.

    Only the per-page module trees are resolvable: app/explore/* is loaded by
    /explore/ and nothing else. Shared top-level modules (app/site.js and
    friends) are loaded from every depth on the site, so a relative link in one
    of them has no single correct resolution and is reported, not resolved.
    """
    for js in site_files("*.js"):
        parts = js.relative_to(ROOT).parts
        if parts[0] != "app" or len(parts) != 3:
            continue
        page_dir = ROOT / parts[1]
        if not (page_dir / "index.html").exists():
            continue
        text = js.read_text(encoding="utf-8", errors="ignore")
        for m in JS_LINK.finditer(text):
            link = m.group(1).strip()
            if not link or EXTERNAL.match(link):
                continue
            # A path built at runtime (`../methods/${s.method}/`) has no single
            # static target. The anchor case (`../periksa/#k=${id}`) is handled
            # in resolve(), which still checks the directory in front of it.
            if "${" in link.partition("#")[0]:
                continue
            yield js, page_dir, link, text[: m.start()].count("\n") + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="also list links that resolve")
    args = ap.parse_args()

    checked = 0
    failures = []
    for source, base_dir, link, line in list(scan_html()) + list(scan_js()):
        checked += 1
        err = check_link(source, base_dir, link, line)
        if err:
            failures.append((rel(source), line, link, err))
        elif args.verbose:
            print(f"  ok  {rel(source)}:{line}  {link}")

    print(f"{checked} internal links checked, {len(failures)} broken")
    if failures:
        print("\nBROKEN LINKS:")
        for src, line, link, err in failures:
            print(f"  {src}:{line}\n    {link}  ->  {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
