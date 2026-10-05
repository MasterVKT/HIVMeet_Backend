"""Adaptateur backend vers le moteur de gouvernance partagé."""
from __future__ import annotations

import runpy
from pathlib import Path


def shared_engine() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".agents" / "hooks" / "lifecycle_hook.py"
        if candidate.exists() and candidate.resolve() != Path(__file__).resolve():
            return candidate
    raise SystemExit("Gouvernance HIVMeet introuvable : remonter depuis une racine de composant valide.")


runpy.run_path(str(shared_engine()), run_name="__main__")
