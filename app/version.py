import os
import subprocess
from pathlib import Path

_APP_VERSION: str | None = None
_GIT_COMMIT: str | None = None
_GIT_TAG: str | None = None


def _read_pyproject_version() -> str | None:
    try:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if not pyproject.exists():
            return None
        text = pyproject.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("version ="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _git_describe() -> tuple[str | None, str | None, str | None]:
    try:
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=root,
        )
        if result.returncode == 0:
            desc = result.stdout.strip()
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=root,
            ).stdout.strip()
            sha = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=root,
            ).stdout.strip()
            return desc, branch, sha
    except Exception:
        pass
    return None, None, None


def get_version() -> str:
    global _APP_VERSION, _GIT_COMMIT, _GIT_TAG
    if _APP_VERSION is not None:
        return _APP_VERSION

    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        _APP_VERSION = version_file.read_text().strip()
        return _APP_VERSION

    desc, branch, sha = _git_describe()
    if desc:
        parts = [desc]
        if branch and branch != "HEAD":
            parts.append(branch)
        _APP_VERSION = " / ".join(parts)
        _GIT_COMMIT = sha
        _GIT_TAG = desc.split("-")[0] if "-" in desc else desc
        return _APP_VERSION

    ver = _read_pyproject_version()
    _APP_VERSION = ver or "dev"
    return _APP_VERSION


def get_version_info() -> dict:
    docker_hash = None
    hash_file = Path(__file__).resolve().parent.parent / "DOCKER_HASH"
    if hash_file.exists():
        docker_hash = hash_file.read_text().strip() or None
    if not docker_hash:
        docker_hash = os.environ.get("DOCKER_HASH")
    return {
        "version": get_version(),
        "commit": _GIT_COMMIT,
        "tag": _GIT_TAG,
        "docker_hash": docker_hash,
    }
