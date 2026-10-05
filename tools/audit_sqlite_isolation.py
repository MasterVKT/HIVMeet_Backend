"""Audit SQLite isolation du graphe code-review-graph."""
import os
import sqlite3
from pathlib import Path


def main() -> int:
    root = Path(r"d:\Projets\HIVMeet\env\hivmeet_backend").resolve()
    database = root / ".code-review-graph" / "graph.db"
    uri = database.as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:
        nodes = connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        sql = "SELECT DISTINCT file_path FROM nodes WHERE file_path IS NOT NULL AND file_path != ''"
        paths = [row[0] for row in connection.execute(sql)]

    outside: list[str] = []
    for value in paths:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            inside = (
                os.path.commonpath(
                    (os.path.normcase(str(candidate.resolve())), os.path.normcase(str(root)))
                )
                == os.path.normcase(str(root))
            )
        except ValueError:
            inside = False
        if not inside:
            outside.append(value)

    print(f"nodes={nodes} files={len(paths)} outside={len(outside)}")
    if outside:
        print(outside[:10])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
