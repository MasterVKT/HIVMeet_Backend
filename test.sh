set -euo pipefail; msg="$(nonexistent_command 2>&1 | head -n 1 || true)"; echo $msg
