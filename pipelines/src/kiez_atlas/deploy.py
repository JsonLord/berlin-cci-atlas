"""Enforce the public/internal boundary for a future Pages deployment.

The allowlist alone is advisory: nothing stops someone adding a file to
data/internal/ and having it published. This module makes the boundary
*executable* so Phase 4/5 can call it, and so a test can prove it works before
any deployment exists.

Two independent guards:

1. `resolve_deploy_set()` — expands the allowlist into concrete files and
   refuses if any path is missing or if any path resolves outside the repo.
2. `assert_no_internal_leak()` — takes a staged directory (what a deploy would
   actually publish) and fails if anything from data/internal/ is present.

The second guard is the important one: it inspects the *output*, not the
intention. A misconfigured copy step is caught even if the allowlist looks right.
"""

from __future__ import annotations

from pathlib import Path

ALLOWLIST = Path("data/deploy-allowlist.txt")

# Paths that must never be published, whatever the allowlist says.
FORBIDDEN_PREFIXES: tuple[str, ...] = ("data/internal/",)
FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "venue_inventory.json", "classification.json", "review_queue.json",
    "sources.json", "source_runs.json",
})


class DeployBoundaryError(RuntimeError):
    pass


def read_allowlist(repo: Path) -> list[str]:
    path = repo / ALLOWLIST
    if not path.exists():
        raise DeployBoundaryError(f"allowlist missing: {path}")
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


def resolve_deploy_set(repo: Path) -> list[Path]:
    """Expand the allowlist to real files, refusing anything unsafe."""
    repo = repo.resolve()
    resolved: list[Path] = []
    problems: list[str] = []

    for entry in read_allowlist(repo):
        target = (repo / entry).resolve()
        # path traversal / absolute escape
        if not str(target).startswith(str(repo) + "/") and target != repo:
            problems.append(f"{entry}: resolves outside the repository")
            continue
        if any(entry.startswith(p) for p in FORBIDDEN_PREFIXES):
            problems.append(f"{entry}: internal path in allowlist")
            continue
        if Path(entry).name in FORBIDDEN_NAMES:
            problems.append(f"{entry}: forbidden filename in allowlist")
            continue
        if not target.exists():
            problems.append(f"{entry}: listed but does not exist")
            continue
        resolved.append(target)

    if problems:
        raise DeployBoundaryError("; ".join(problems))
    return resolved


def assert_no_internal_leak(staged: Path) -> None:
    """Fail if a staged deploy directory contains internal artefacts."""
    staged = staged.resolve()
    leaks: list[str] = []
    for f in staged.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(staged).as_posix()
        if any(rel.startswith(p) for p in FORBIDDEN_PREFIXES):
            leaks.append(rel)
        elif f.name in FORBIDDEN_NAMES:
            leaks.append(rel)
    if leaks:
        raise DeployBoundaryError(
            "internal artefacts would be published: " + ", ".join(sorted(leaks)))


def internal_files(repo: Path) -> list[Path]:
    d = repo / "data" / "internal"
    return sorted(p for p in d.rglob("*") if p.is_file()) if d.exists() else []
