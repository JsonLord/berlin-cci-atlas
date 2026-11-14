"""Command line entry point:  python -m kiez_atlas.cli build|validate"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .publish import build
from .validate import run as run_validation


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiez_atlas")
    ap.add_argument("cmd", choices=["build", "validate", "all"])
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()

    if args.cmd in ("build", "all"):
        meta = build(repo / "index.html", repo / "data")
        print(f"built. counts={meta['counts']}")

    if args.cmd in ("validate", "all"):
        res = run_validation(repo)
        width = max(len(n) for n, _, _ in res.results)
        for name, ok, detail in res.results:
            print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
        failed = res.failed
        print(f"\n{len(res.results) - len(failed)}/{len(res.results)} checks passed")
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
