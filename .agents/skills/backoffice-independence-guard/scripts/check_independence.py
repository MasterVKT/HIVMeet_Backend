#!/usr/bin/env python3
"""Garde d'indépendance du back-office HIVMeet.

Le back-office ne doit jamais modifier le fonctionnement existant de l'application.
Ce script empreint (SHA-256) tous les fichiers situés hors des zones d'écriture
autorisées, puis détecte tout écart.

Commandes :
  snapshot  Écrit la baseline (refuse d'écraser sans --force).
  verify    Compare l'arbre courant à la baseline (code retour 1 si écart).
  report    Comme verify, avec le détail de chaque écart.
  rebase    Régénère la baseline après accord EXPLICITE de l'utilisateur
            (par exemple parce qu'il a lui-même modifié l'application).

Aucune dépendance externe. N'écrit que dans docs/backoffice/.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASELINE = ROOT / "docs" / "backoffice" / "independence-baseline.json"
MAX_BYTES = 50 * 1024 * 1024

# Zones où l'écriture est autorisée : jamais empreintées.
WRITABLE_PREFIXES = (
    "backoffice/",
    "docs/backoffice/",
)
WRITABLE_GLOBS = (
    ".agents/skills/backoffice-*/*",
    ".claude/skills/backoffice-*/*",
    "docker-compose.backoffice.yml",
)
# Fichiers de gouvernance où seules des lignes peuvent être ajoutées (sans effet runtime).
# Empreintés quand même ; un écart est signalé comme "gouvernance" et non comme violation.
GOVERNANCE_APPEND_ONLY = (
    ".agents/skills/task-router/SKILL.md",
    ".agents/skills/BACKEND_SKILLS_CATALOG.md",
)
# Artefacts générés par l'exécution ou l'outillage : ignorés.
IGNORED_DIR_NAMES = {
    ".git", "__pycache__", ".venv", ".pytest_cache", ".runtime", ".code-review-graph",
    "media", "private_uploads", "node_modules", ".mypy_cache", ".ruff_cache",
}
IGNORED_GLOBS = (
    "*.pyc", "*.pyo", "*.log", ".coverage", "celerybeat-schedule*", "staticfiles*",
    "*.tmp", ".venv_install.log",
)


def posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_writable_zone(rel: str) -> bool:
    return rel.startswith(WRITABLE_PREFIXES) or any(fnmatch.fnmatch(rel, g) for g in WRITABLE_GLOBS)


def is_ignored(rel: str, parts: tuple[str, ...]) -> bool:
    if any(part in IGNORED_DIR_NAMES for part in parts[:-1]):
        return True
    name = parts[-1]
    return any(fnmatch.fnmatch(name, g) for g in IGNORED_GLOBS)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> dict[str, str]:
    files: dict[str, str] = {}
    stack = [ROOT]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name in IGNORED_DIR_NAMES or any(
                    fnmatch.fnmatch(entry.name, g) for g in IGNORED_GLOBS
                ):
                    continue
                stack.append(entry)
                continue
            rel = posix(entry)
            parts = tuple(rel.split("/"))
            if is_ignored(rel, parts) or is_writable_zone(rel):
                continue
            try:
                if entry.stat().st_size > MAX_BYTES:
                    files[rel] = "oversize"
                    continue
                files[rel] = digest(entry)
            except OSError:
                files[rel] = "unreadable"
    return dict(sorted(files.items()))


def write_baseline(files: dict[str, str]) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_count": len(files),
        "files": files,
    }
    BASELINE.write_text(json.dumps(payload, indent=0, sort_keys=True) + "\n", encoding="utf-8")


def load_baseline() -> dict:
    if not BASELINE.exists():
        raise SystemExit("Baseline absente : exécuter d'abord `snapshot`.")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def diff(old: dict[str, str], new: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])
    return added, removed, changed


def cmd_snapshot(force: bool) -> int:
    if BASELINE.exists() and not force:
        print(f"Baseline déjà présente ({BASELINE.relative_to(ROOT).as_posix()}). Utiliser --force seulement si justifié.")
        return 1
    files = collect()
    write_baseline(files)
    print(f"Baseline écrite : {len(files)} fichiers empreintés hors zones d'écriture autorisées.")
    return 0


def cmd_verify(detail: bool) -> int:
    base = load_baseline()
    added, removed, changed = diff(base["files"], collect())
    governance = [p for p in changed if p in GOVERNANCE_APPEND_ONLY]
    violations_changed = [p for p in changed if p not in GOVERNANCE_APPEND_ONLY]
    total = len(added) + len(removed) + len(violations_changed)
    print(f"Baseline du {base['created_at']} ({base['file_count']} fichiers).")
    if governance:
        print(f"Gouvernance (ajouts autorisés, à relire) : {', '.join(governance)}")
    if total == 0:
        print("INDEPENDENCE: PASS - aucun fichier hors zone autorisée n'a changé.")
        return 0
    print(f"INDEPENDENCE: FAIL - {total} écart(s) hors zones autorisées "
          f"(ajoutés={len(added)}, supprimés={len(removed)}, modifiés={len(violations_changed)}).")
    limit = None if detail else 25
    for label, items in (("AJOUTÉ", added), ("SUPPRIMÉ", removed), ("MODIFIÉ", violations_changed)):
        for item in items[:limit]:
            print(f"  {label} {item}")
        if limit and len(items) > limit:
            print(f"  ... {len(items) - limit} autre(s) {label.lower()}(s), voir `report`.")
    print("Procédure : identifier l'auteur de l'écart. Annuler uniquement ses propres changements; "
          "si l'utilisateur a modifié ces fichiers, le signaler puis `rebase` avec son accord.")
    return 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--force", action="store_true")
    sub.add_parser("verify")
    sub.add_parser("report")
    sub.add_parser("rebase")
    args = parser.parse_args()
    if args.command == "snapshot":
        return cmd_snapshot(args.force)
    if args.command == "verify":
        return cmd_verify(detail=False)
    if args.command == "report":
        return cmd_verify(detail=True)
    return cmd_snapshot(force=True)


if __name__ == "__main__":
    sys.exit(main())
