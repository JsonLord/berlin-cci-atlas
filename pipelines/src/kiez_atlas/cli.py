"""Command line entry point:  python -m kiez_atlas.cli build|validate|metrics"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .publish import build
from .validate import run as run_validation
from .metrics import main as run_metrics


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiez_atlas")
    ap.add_argument("cmd", choices=["build", "validate", "metrics", "all"])
    ap.add_argument("--repo", default=".")
    # metrics-specific args
    ap.add_argument("--output", help="Output file (metrics only)")
    ap.add_argument("--format", choices=["json", "summary"], default="json", help="Output format (metrics only)")
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
        if failed:
            return 1

    if args.cmd == "metrics":
        # Reconstruct argv for the metrics module and pass it explicitly.
        # Swapping `sys.argv` would work, but it mutates process-global state
        # that a caller (a test, a nested invocation) may be relying on, and it
        # hides the arguments from anyone reading this function.
        metrics_argv = ["--repo", str(repo)]
        if args.output:
            metrics_argv += ["--output", args.output]
        if args.format:
            metrics_argv += ["--format", args.format]
        return run_metrics(metrics_argv)

    return 0


if __name__ == "__main__":
    sys.exit(main())
