from pathlib import Path
import sys

def fix(path: str) -> None:
    p = Path(path)
    b = p.read_bytes()
    marker = b'{"$mid"'
    idx = b.find(marker)
    if idx != -1:
        # remove from previous newline to end
        nl = b.rfind(b'\n', 0, idx)
        cut = nl + 1 if nl != -1 else idx
        b = b[:cut]
    # trim trailing newlines then add one
    while b.endswith(b'\n') or b.endswith(b'\r'):
        b = b[:-1]
    b += b'\n'
    p.write_bytes(b)
    print(f"{path}: {len(b)} bytes, mid_artifact={idx != -1}")

if __name__ == "__main__":
    fix(sys.argv[1])
