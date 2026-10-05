"""Audit MCP/JSON/TOML config files for MIME/cache_control artifacts."""
from pathlib import Path

CONFIGS = [
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.codex\\config.toml"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.vscode\\mcp.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.cursor\\mcp.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.gemini\\settings.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.kiro\\settings\\mcp.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.qoder\\mcp.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.kilo\\kilo.json"),
    Path(r"D:\\Projets\\HIVMeet\\env\\hivmeet_backend\\.mcp.json"),
    Path(r"C:\\Users\\vekou\\.cline\\mcp.json"),
    Path(r"C:\\Users\\vekou\\.codex\\config.toml"),
]

ARTIFACT = '{"$mid":24,"mimeType":"cache_control","data":"ZXBoZW1lcmFs"}'


def main() -> int:
    clean = True
    for p in CONFIGS:
        if not p.exists():
            print(f"MISSING {p}")
            clean = False
            continue
        text = p.read_text(encoding="utf-8")
        has_artifact = ARTIFACT in text or "cache_control" in text or "mimeType" in text
        if has_artifact:
            print(f"ARTIFACT {p}")
            clean = False
        else:
            print(f"CLEAN {p.name}")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
