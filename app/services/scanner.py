from pathlib import Path


def scan_directory(root: str) -> list[dict]:
    broken = []
    root_path = Path(root).resolve()
    for p in root_path.rglob("*"):
        if p.is_symlink():
            target = p.readlink()
            resolved = (p.parent / target).resolve()
            if not resolved.exists():
                broken.append(
                    {
                        "symlink": str(p),
                        "target": str(target),
                        "resolved": str(resolved),
                    }
                )
    return broken
