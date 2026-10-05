"""Route un serveur code-review-graph global vers un workspace autorisé.

Ce routeur est conçu pour les clients MCP (notamment Cline/VS Code) qui ne
fournissent pas de configuration projet fiable. Il identifie le workspace actif
à partir du répertoire de travail ou de l'arbre des processus VS Code, puis
ne lance le serveur code-review-graph que si le workspace appartient à une
allowlist explicite. Dans le cas contraire, il sort avec un code non nul sans
démarrer de serveur (fail-closed).

Voir le guide du projet : CODE_REVIEW_GRAPH_MULTI_AGENT_SETUP.md
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


# Allowlist des dépôts autorisés avec l'exécutable code-review-graph dédié.
# Chaque entrée est un tuple (racine_git, exécutable_crg).
PROJECTS = (
    (
        Path(r"D:\Projets\HIVMeet\env\hivmeet_backend"),
        Path(r"D:\Projets\HIVMeet\env\hivmeet_backend\.venv\Scripts\code-review-graph.exe"),
    ),
)


def is_within(candidate: Path, root: Path) -> bool:
    """Vérifie que candidate se trouve sous root (comparaison insensible à la casse sur Windows)."""
    candidate_norm = os.path.normcase(str(candidate.resolve()))
    root_norm = os.path.normcase(str(root.resolve()))
    try:
        return os.path.commonpath((candidate_norm, root_norm)) == root_norm
    except ValueError:
        return False


def file_uri_to_path(value: str) -> Path | None:
    """Convertit une URI file:// en chemin Windows/POSIX."""
    parsed = urlparse(value)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    decoded = unquote(parsed.path)
    if os.name == "nt" and re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    return Path(decoded.replace("/", os.sep))


def vscode_data_roots() -> tuple[Path, ...]:
    """Retourne les dossiers de données VS Code possibles pour la distribution actuelle."""
    home = Path.home()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return ()
        base = Path(appdata)
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return tuple(base / name for name in ("Code", "Code - Insiders", "VSCodium"))


def workspace_from_extension_host(parent_pid: int) -> Path | None:
    """Déduit le workspace VS Code actif à partir des journaux de l'extension host."""
    pid_pattern = re.compile(
        rf"Extension host with pid\s+{re.escape(str(parent_pid))}\s+started",
        re.IGNORECASE,
    )
    storage_pattern = re.compile(
        r"workspaceStorage[\\/]([0-9a-f]{32})(?:[\\/.]|$)",
        re.IGNORECASE,
    )

    candidates: list[tuple[float, Path, Path]] = []
    for code_root in vscode_data_roots():
        logs_root = code_root / "logs"
        storage_root = code_root / "User" / "workspaceStorage"
        if not logs_root.is_dir() or not storage_root.is_dir():
            continue
        for log_path in logs_root.glob("*/window*/exthost/exthost.log"):
            candidates.append((log_path.stat().st_mtime, log_path, storage_root))

    for _, log_path, storage_root in sorted(candidates, reverse=True):
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not pid_pattern.search(text):
            continue
        storage_ids = storage_pattern.findall(text)
        if not storage_ids:
            return None
        metadata_path = storage_root / storage_ids[-1] / "workspace.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        folder_uri = metadata.get("folder")
        if not isinstance(folder_uri, str):
            return None
        return file_uri_to_path(folder_uri)
    return None


def identify_project() -> tuple[Path, Path] | None:
    """Retourne le projet autorisé unique correspondant au contexte d'exécution."""
    candidates: list[Path | None] = [Path.cwd(), workspace_from_extension_host(os.getppid())]
    for candidate in candidates:
        if candidate is None:
            continue
        matches = [entry for entry in PROJECTS if is_within(candidate, entry[0])]
        if len(matches) == 1:
            return matches[0]
    return None


def main() -> int:
    """Point d'entrée principal du routeur."""
    project = identify_project()
    if project is None:
        print(
            "Routeur refusé : aucun workspace autorisé unique n'a été identifié.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    root, executable = project
    if not executable.is_file():
        print(f"Exécutable introuvable : {executable}", file=sys.stderr, flush=True)
        return 3

    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONUTF8": "1",
            "CRG_REPO_ROOT": str(root),
            "CRG_DATA_DIR": str(root / ".code-review-graph"),
        }
    )
    process = subprocess.Popen(
        (str(executable), "serve", "--repo", str(root)),
        cwd=root,
        env=environment,
    )
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
