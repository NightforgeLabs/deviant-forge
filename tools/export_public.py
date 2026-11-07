"""Copy the app into a public repo checkout, leaving private things behind.

    python3 tools/export_public.py <checkout> [--name WORD ...]

  - never copies data/ (saved gear, recordings), research/, desktop/, caches, dist/
  - in text files, local home paths (/home/<user>/...) become ~/...; each --name WORD becomes "the owner"
  - a file whose checksum is quoted anywhere in the app (evidence chains) is copied unchanged,
    since editing it would break that check
  - files deleted from the app are deleted from the checkout too (except .git)
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = {"data", "research", "desktop", "__pycache__", ".git", "dist"}
TEXT = {".py", ".json", ".md", ".js", ".cjs", ".html", ".css", ".sh", ".txt", ".bat", ".service", ".desktop", ".svg", ""}
HOME = re.compile(r"/home/[A-Za-z0-9_.-]+/")


def wanted(rel: Path) -> bool:
    return not any(p in PRIVATE for p in rel.parts) and rel.suffix != ".pyc"


def clean(text: str, names: list[str]) -> str:
    text = HOME.sub("~/", text)
    for n in names:
        text = re.sub(rf"\b{re.escape(n)}\b", "the owner", text)
    return text


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("dest")
    a.add_argument("--name", action="append", default=[])
    args = a.parse_args()
    dest = Path(args.dest).resolve()
    if not (dest / ".git").is_dir():
        sys.exit(f"{dest} is not a git checkout")
    srcs = [p for p in sorted(ROOT.rglob("*")) if p.is_file() and wanted(p.relative_to(ROOT))]
    blob = b"\n".join(p.read_bytes() for p in srcs if p.suffix.lower() in TEXT)
    pinned = set()
    for p in srcs:
        if p.suffix.lower() in TEXT and HOME.search(p.read_bytes().decode("utf-8", "replace")):
            if hashlib.sha256(p.read_bytes()).hexdigest().encode() in blob:
                pinned.add(p)
    keep = set()
    changed = 0
    for p in srcs:
        rel = p.relative_to(ROOT)
        if not p.is_file() or not wanted(rel):
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        keep.add(rel.as_posix())
        if p.suffix.lower() in TEXT and p not in pinned:
            raw = p.read_bytes()
            try:
                data = clean(raw.decode("utf-8"), args.name).encode("utf-8")
            except UnicodeDecodeError:
                data = raw
        else:
            data = p.read_bytes()
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            shutil.copymode(p, out)
            changed += 1
    removed = 0
    for q in sorted(dest.rglob("*"), reverse=True):
        rel = q.relative_to(dest)
        if rel.parts and rel.parts[0] == ".git":
            continue
        if q.is_file() and rel.as_posix() not in keep and rel.as_posix() != ".gitignore":
            q.unlink(); removed += 1
        elif q.is_dir() and not any(q.iterdir()):
            q.rmdir()
    print(f"exported to {dest}: {changed} written, {removed} removed, {len(keep)} files, "
          f"{len(pinned)} checksum-pinned files copied unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
