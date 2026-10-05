#!/usr/bin/env bash
# double-check completion gate: verify response completeness before stop (Gemini CLI hook)
# Must output ONLY JSON on stdout. Never blocks the session.
set -euo pipefail

cat > /dev/null || true

python3 -c '
import json
msg = "[DOUBLE CHECK GATE] OBLIGATOIRE avant envoi : 1- Relire la requete originale mot pour mot. 2- Verifier chaque exigence contre ce qui a ete fait. 3- Corriger tout ecart silencieusement. 4- Envoyer seulement apres verification complete."
print(json.dumps({"systemMessage": msg, "suppressOutput": True}))
' 2>/dev/null || echo '{"suppressOutput": true}'
exit 0
