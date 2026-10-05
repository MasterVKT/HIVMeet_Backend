#!/usr/bin/env bash
# skills router gate: inject task-router instruction before each prompt (Gemini CLI hook)
# Must output ONLY JSON on stdout. Never blocks the session.
set -euo pipefail

cat > /dev/null || true

python3 -c '
import json
msg = "[ORCHESTRATOR GATE] Avant tout traitement : lire .agents/skills/task-router/SKILL.md, appliquer son arbre de decision, identifier les skills pertinentes, puis traiter la requete."
print(json.dumps({"additionalContext": msg, "suppressOutput": True}))
' 2>/dev/null || echo '{"suppressOutput": true}'
exit 0
