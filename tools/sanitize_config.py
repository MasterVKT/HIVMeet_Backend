"""Sanitize MCP/JSON/TOML config files by stripping MIME/cache_control artifacts."""
from pathlib import Path
import sys


def sanitize(path: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    # Known artifact patterns produced by some VS Code file operations.
    artifact = '{"$mid":24,"mimeType":"cache_control","data":"ZXBoZW1lcmFs"}'
    if artifact in text:
        text = text.split(artifact)[0]
    # Also strip any line starting with a JSON/MIME artifact in TOML files.
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith('{"$mid"') or "cache_control" in line or 'mimeType' in line:
            continue
        lines.append(line)
    # Trim trailing whitespace/newlines then add single newline.
    while lines and lines[-1].strip() == "":
        lines.pop()
    final = "\n".join(lines) + "\n"
    p.write_text(final, encoding="utf-8")
    print(f"Sanitized {p}: {len(final)} chars")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        sanitize(arg)
