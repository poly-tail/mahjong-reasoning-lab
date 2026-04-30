from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    removed: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if path.name == "__pycache__" and path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
        elif path.suffix == ".pyc" and path.is_file():
            path.unlink()
            removed.append(path)

    if not removed:
        print("No Python cache artifacts found.")
        return 0

    for path in removed:
        print(f"Removed {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
