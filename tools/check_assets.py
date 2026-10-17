#!/usr/bin/env python3
"""Pre-submission checker for the Smart Land static site (stdlib only, Python 3.8+).

    python3 tools/check_assets.py            # errors + warnings + per-role TODO summary
    python3 tools/check_assets.py --strict   # also fails on missing videos / placeholder images / TODOs

What it enforces (from the assignment brief):
  * still images must be real WEBP or AVIF files (no png/jpg/gif/ico/bmp, and no renamed files)
  * images / videos must have web-friendly sizes
  * every local reference in HTML/CSS must resolve; every <img> needs an alt attribute
Exit code: 0 = no errors, 1 = errors found.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"tools", "docs", ".git", "node_modules", "__pycache__"}

FORBIDDEN_IMG = {".png", ".jpg", ".jpeg", ".jfif", ".gif", ".bmp", ".tif", ".tiff", ".ico", ".heic"}
ALLOWED_IMG = {".webp", ".avif"}
SVG_EXT = ".svg"
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv"}

IMG_WARN_KB = 250
IMG_ERR_KB = 600
VIDEO_WARN_MB = 25
VIDEO_ERR_MB = 60

# Files that are expected to arrive later from teammates (missing = "pending", not "broken").
PENDING_OK = {"assets/video/intro.mp4", "assets/video/projects.mp4"}

# Which role owns each placeholder (for the progress summary).
ROLE_BY_ASSET = {
    "logo-main.webp": "R3", "favicon.webp": "R3",
    "hero.webp": "R4", "about-team.webp": "R4",
    "project-smart-signal.webp": "R4", "project-mykey.webp": "R4", "project-sada.webp": "R4",
    "project-welcome.webp": "R4", "project-hospital.webp": "R4",
    "poster-intro.webp": "R5", "poster-projects.webp": "R6",
    "intro.mp4": "R5", "projects.mp4": "R6",
}
# Literal placeholder strings that must not ship.
PLACEHOLDER_STRINGS = [("smartland.example", "R7"), ("+000 000 000 000", "R7")]

errors, warnings, pending, infos = [], [], [], []


def rel(p):
    return p.relative_to(ROOT).as_posix()


def iter_files():
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and not (set(p.relative_to(ROOT).parts[:-1]) & SKIP_DIRS):
            yield p


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs, self.ids, self.alt_missing, self.dup_ids = [], set(), [], []
        self.title, self._in_title = "", False
        self.root_attrs = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if tag == "html":
            self.root_attrs = a
        if tag == "title":
            self._in_title = True
        if "id" in a:
            if a["id"] in self.ids:
                self.dup_ids.append((a["id"], line))
            self.ids.add(a["id"])
        if tag == "img" and "alt" not in a:
            self.alt_missing.append(line)
        for attr in ("src", "poster", "href"):
            if attr in a and a[attr]:
                # <use href="#i-x"> and in-page anchors are handled separately
                self.refs.append((tag, attr, a[attr], line))
        for attr in ("srcset",):
            if attr in a and a[attr]:
                for part in a[attr].split(","):
                    tok = part.strip().split(" ")[0]
                    if tok:
                        self.refs.append((tag, attr, tok, line))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def is_external(ref):
    return bool(re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", ref, re.I))


def check_magic(path):
    ext = path.suffix.lower()
    head = path.read_bytes()[:32]
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == ".avif":
        return head[4:8] == b"ftyp" and (b"avif" in head[8:32] or b"avis" in head[8:32])
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="treat pending items and TODO markers as errors")
    args = ap.parse_args()

    files = list(iter_files())
    by_rel = {rel(p): p for p in files}
    total_bytes = sum(p.stat().st_size for p in files)

    # ---------- 1) image / video files on disk ----------
    for p in files:
        ext, r = p.suffix.lower(), rel(p)
        kb = p.stat().st_size / 1024
        if ext in FORBIDDEN_IMG:
            errors.append(f"{r}: forbidden image format '{ext}' (still images must be WEBP or AVIF only)")
        elif ext == SVG_EXT:
            warnings.append(f"{r}: SVG found. The brief says still images must be WEBP/AVIF only; confirm with the instructor or convert.")
        elif ext in ALLOWED_IMG:
            if not check_magic(p):
                errors.append(f"{r}: extension is {ext} but the file content is NOT a real {ext[1:].upper()} (renamed file?). Re-export it properly.")
            if kb > IMG_ERR_KB:
                errors.append(f"{r}: {kb:.0f} KB is too heavy for the web (limit {IMG_ERR_KB} KB). Resize/compress.")
            elif kb > IMG_WARN_KB:
                warnings.append(f"{r}: {kb:.0f} KB (aim for <= {IMG_WARN_KB} KB)")
        elif ext in VIDEO_EXT:
            mb = kb / 1024
            if mb > VIDEO_ERR_MB:
                errors.append(f"{r}: {mb:.1f} MB video is too heavy (limit {VIDEO_ERR_MB} MB).")
            elif mb > VIDEO_WARN_MB:
                warnings.append(f"{r}: {mb:.1f} MB video (aim for <= {VIDEO_WARN_MB} MB).")
            if ext == ".mp4" and p.read_bytes()[4:8] != b"ftyp":
                errors.append(f"{r}: not a valid MP4 container.")
            if shutil.which("ffprobe"):
                try:
                    out = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height",
                         "-show_entries", "format=duration", "-of", "json", str(p)],
                        capture_output=True, text=True, timeout=30).stdout
                    meta = json.loads(out or "{}")
                    streams = meta.get("streams", [])
                    v = next((s for s in streams if s.get("codec_type") == "video"), {})
                    has_audio = any(s.get("codec_type") == "audio" for s in streams)
                    dur = float(meta.get("format", {}).get("duration", 0) or 0)
                    infos.append(f"{r}: {v.get('codec_name')} {v.get('width')}x{v.get('height')}, {dur:.0f}s, audio={'yes' if has_audio else 'NO'}")
                    if not has_audio:
                        errors.append(f"{r}: no audio track (the brief requires suitable audio).")
                    if (v.get("width") or 0) > 1920:
                        warnings.append(f"{r}: width {v.get('width')} px; 1280x720 is enough for this site.")
                    if v.get("codec_name") not in (None, "h264"):
                        warnings.append(f"{r}: codec {v.get('codec_name')}; H.264 plays everywhere.")
                except Exception as exc:  # ffprobe is optional
                    infos.append(f"{r}: ffprobe skipped ({exc})")

    # ---------- 2) HTML pages ----------
    pages = {rel(p): p for p in files if p.suffix.lower() == ".html"}
    parsed = {}
    for r, p in pages.items():
        parser = PageParser()
        parser.feed(p.read_text(encoding="utf-8", errors="replace"))
        parsed[r] = parser
        if not parser.title.strip():
            errors.append(f"{r}: empty <title>")
        if parser.root_attrs.get("lang") != "ar" or parser.root_attrs.get("dir") != "rtl":
            warnings.append(f"{r}: <html> should have lang=\"ar\" dir=\"rtl\"")
        for line in parser.alt_missing:
            errors.append(f"{r}:{line}: <img> without alt attribute")
        for i, line in parser.dup_ids:
            errors.append(f"{r}:{line}: duplicate id '{i}'")

    referenced = set()
    for r, parser in parsed.items():
        base = pages[r].parent
        for tag, attr, ref, line in parser.refs:
            if is_external(ref) or ref.startswith(("data:", "javascript:")):
                continue
            path_part, _, frag = ref.partition("#")
            path_part = path_part.split("?")[0]
            if not path_part:  # same-page anchor
                if frag and tag != "use" and frag not in parser.ids:
                    errors.append(f"{r}:{line}: anchor #{frag} has no matching id")
                continue
            target = (base / path_part).resolve()
            try:
                trel = target.relative_to(ROOT).as_posix()
            except ValueError:
                errors.append(f"{r}:{line}: reference leaves the project folder: {ref}")
                continue
            referenced.add(trel)
            if trel not in by_rel:
                if trel in PENDING_OK:
                    pending.append(f"{trel}: referenced by {r} but not delivered yet ({ROLE_BY_ASSET.get(Path(trel).name, '?')})")
                else:
                    errors.append(f"{r}:{line}: broken reference -> {ref}")
            elif frag and trel in parsed and frag not in parsed[trel].ids:
                errors.append(f"{r}:{line}: {ref} points to a missing id in {trel}")

    # ---------- 3) CSS url(...) references ----------
    for p in files:
        if p.suffix.lower() != ".css":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text):
            ref = m.group(1)
            if is_external(ref) or ref.startswith("data:"):
                continue
            target = (p.parent / ref.split("?")[0].split("#")[0]).resolve()
            try:
                trel = target.relative_to(ROOT).as_posix()
            except ValueError:
                continue
            referenced.add(trel)
            if trel not in by_rel:
                errors.append(f"{rel(p)}: broken url() -> {ref}")

    # ---------- 4) assets that nothing uses ----------
    for r in sorted(by_rel):
        if r.startswith("assets/images/") and r not in referenced:
            warnings.append(f"{r}: not referenced by any page or stylesheet (delete it or use it)")

    # ---------- 5) placeholder images still in place ----------
    manifest_path = ROOT / "tools" / "placeholders.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, digest in manifest.items():
            f = by_rel.get(f"assets/images/{name}")
            if f and hashlib.sha256(f.read_bytes()).hexdigest() == digest:
                pending.append(f"assets/images/{name}: still the PLACEHOLDER image ({ROLE_BY_ASSET.get(name, '?')})")

    # ---------- 6) TODO markers + literal placeholder strings, per role ----------
    todo = {}
    lit = {}
    for p in files:
        if p.suffix.lower() not in {".html", ".css", ".js", ".vtt", ".md"}:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"TODO((?:\[R\d\])+)", text):
            for role in re.findall(r"R\d", m.group(1)):
                todo[role] = todo.get(role, 0) + 1
        if p.suffix.lower() in {".html", ".js", ".vtt"}:
            for s, role in PLACEHOLDER_STRINGS:
                n = text.count(s)
                if n:
                    lit[(s, role)] = lit.get((s, role), 0) + n

    # ---------- report ----------
    def block(title, items):
        if items:
            print(f"\n== {title} ({len(items)}) ==")
            for it in items:
                print("  -", it)

    print(f"Smart Land site check  |  {len(files)} files, {total_bytes / 1024 / 1024:.2f} MB total")
    block("ERRORS (must fix)", errors)
    block("WARNINGS", warnings)
    block("PENDING (waiting for teammates)", pending)
    if lit:
        block("PLACEHOLDER TEXT STILL IN PAGES", [f"'{s}' x{n} ({role})" for (s, role), n in sorted(lit.items())])
    if todo:
        print("\n== OPEN TODO MARKERS PER ROLE ==")
        for role in sorted(todo):
            print(f"  - {role}: {todo[role]}")
    block("INFO", infos)

    strict_fail = bool(args.strict and (pending or todo or lit))
    if args.strict and strict_fail:
        errors.append("strict mode: pending items / TODO markers / placeholder text remain")
    print()
    if errors:
        print(f"RESULT: FAIL ({len(errors)} error(s))")
        return 1
    print("RESULT: OK" + ("" if args.strict else "  (run with --strict before submitting)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
