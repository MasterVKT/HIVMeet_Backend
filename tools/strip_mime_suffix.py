from pathlib import Path
import sys


def strip_mime_suffix(path: str) -> None:
    p = Path(path)
    b = p.read_bytes()
    marker = b'{"$mid"'
    idx = b.find(marker)
    if idx == -1:
        print("No MIME artifact found", file=sys.stderr)
        return
    nl = b.rfind(b'\n', 0, idx)
    cut_at = nl + 1 if nl != -1 else idx
    p.write_bytes(b[:cut_at])
    print(f"Stripped {len(b) - cut_at} bytes from {p}")


if __name__ == "__main__":
    strip_mime_suffix(sys.argv[1])
