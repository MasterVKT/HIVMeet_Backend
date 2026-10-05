#!/usr/bin/env bash
# skills router gate: inject task-router instruction before each prompt (Cursor hook)
# Runs from project root. Output is surfaced to the agent as context.
set -euo pipefail

echo "[ORCHESTRATOR GATE] Avant tout traitement : lire .agents/skills/task-router/SKILL.md, appliquer son arbre de decision, identifier les skills pertinentes, puis traiter la requete."
exit 0
