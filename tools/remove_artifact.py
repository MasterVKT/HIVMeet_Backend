from pathlib import Path
import sys

def remove_artifact(path: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    artifact = '{"$mid":24,"mimeType":"cache_control","data":"ZXBoZW1lcmFs"}'
    idx = text.find(artifact)
    if idx != -1:
        text = text[:idx].rstrip() + "\n"
        p.write_text(text, encoding="utf-8")
        print(f"Removed artifact from {p}: now {len(text)} chars")
    else:
        print(f"No artifact in {p}")

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        remove_artifact(arg)
