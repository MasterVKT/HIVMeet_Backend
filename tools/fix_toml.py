from pathlib import Path
import sys


def normalize_file(path: str) -> None:
    p = Path(path)
    b = p.read_bytes()
    # Strip any JSON/MIME artifact starting with {"$mid"
    marker = b'{"$mid"'
    idx = b.find(marker)
    if idx != -1:
        nl = b.rfind(b'\n', 0, idx)
        b = b[: nl + 1 if nl != -1 else idx]
    # Trim trailing newlines then add exactly one
    while b and b[-1:] in (b'\n', b'\r'):
        b = b[:-1]
    b += b'\n'
    p.write_bytes(b)
    print(f"Wrote {len(b)} bytes to {p}")


if __name__ == "__main__":
    normalize_file(sys.argv[1])
