#!/usr/bin/env python3
"""Create a self-contained `dist/` directory for the standalone web app.

This copies the HTML entry points plus their local dependencies so the app can
be opened directly in a local browser (no server required).

Usage:
  python3 scripts/make_dist.py

Output:
  dist/
    index.html
    msa.html
    web/
    py2Dmol/resources/
    resources/

Notes:
- Minification is intentionally ignored (copies files as-is).
- External CDN dependencies referenced in the HTML remain external.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Missing directory: {src_dir}")
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, dst_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local-openable dist/ folder")
    parser.add_argument(
        "--out",
        default="dist",
        help="Output directory (relative to repo root). Default: dist",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete the output directory if it already exists.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = (repo_root / args.out).resolve()

    if out_dir.exists() and not args.no_clean:
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Entry points
    for filename in ("index.html", "msa.html"):
        src = repo_root / filename
        if not src.is_file():
            raise FileNotFoundError(f"Missing file: {src}")
        _copy_file(src, out_dir / filename)

    # Local dependencies referenced by the HTML
    _copy_tree(repo_root / "web", out_dir / "web")
    _copy_tree(repo_root / "py2Dmol" / "resources", out_dir / "py2Dmol" / "resources")


    # Nice-to-have docs
    for optional in ("LICENSE", "README.md"):
        src = repo_root / optional
        if src.is_file():
            _copy_file(src, out_dir / optional)

    print(f"Wrote: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
