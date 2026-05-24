"""File-based storage helpers for YAML and Markdown with frontmatter.

All writes are atomic: write to ``<path>.tmp``, fsync, rename.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from praxis.errors import StorageError

T = TypeVar("T", bound=BaseModel)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def read_yaml_typed(path: Path, model: type[T]) -> T:
    """Read a YAML file and validate against a Pydantic model.

    Args:
        path: Path to the YAML file.
        model: Pydantic model class to validate against.

    Raises:
        StorageError: If the file doesn't exist, is malformed, or fails validation.
    """
    if not path.exists():
        raise StorageError(f"File not found: {path}", path=str(path))
    if not path.is_file():
        raise StorageError(f"Not a file: {path}", path=str(path))
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise StorageError(f"Malformed YAML in {path}: {exc}", path=str(path)) from exc
    except OSError as exc:
        raise StorageError(f"Cannot read {path}: {exc}", path=str(path)) from exc

    if data is None:
        data = {}

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StorageError(
            f"Validation failed for {path}: {exc}",
            path=str(path),
            errors=exc.errors(),
        ) from exc


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write *content* to *path*.

    Writes to a sibling ``<stem>.tmp`` first, fsync's the data to disk, then
    atomically renames into place. A process killed between the write and
    the rename leaves the *original* file (if any) intact and an orphaned
    ``.tmp`` sibling that the next successful write will overwrite.

    Used for the audit/evidence trail — sufficiency reports + generated
    artifacts (D-060). ``rename`` is atomic on POSIX; on Windows it's
    near-atomic (atomic when the destination already exists, replacement
    otherwise). The risk on Windows is small enough that we don't add a
    transactional shim today; document it loudly here if it ever bites.

    Args:
        path: Destination path. Parent directories are created if missing.
        content: Text to write.
        encoding: Text encoding (default utf-8).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(path)
    except OSError as exc:
        # Best-effort cleanup; don't mask the original error.
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise StorageError(f"Cannot atomically write {path}: {exc}", path=str(path)) from exc


def write_yaml_typed(path: Path, obj: BaseModel) -> None:
    """Atomically write a Pydantic model as YAML.

    Args:
        path: Destination path.
        obj: Pydantic model instance to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    data = obj.model_dump(mode="json")
    try:
        with open(tmp, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(path)
    except OSError as exc:
        raise StorageError(f"Cannot write {path}: {exc}", path=str(path)) from exc


def read_markdown_with_frontmatter(path: Path, frontmatter_model: type[T]) -> tuple[T, str]:
    """Read a Markdown file with YAML frontmatter.

    Args:
        path: Path to the Markdown file.
        frontmatter_model: Pydantic model for the frontmatter.

    Returns:
        Tuple of (parsed frontmatter, body text).

    Raises:
        StorageError: If the file doesn't exist, has no frontmatter, or fails validation.
    """
    if not path.exists():
        raise StorageError(f"File not found: {path}", path=str(path))

    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise StorageError(f"No YAML frontmatter found in {path}", path=str(path))

    raw_fm, body = match.group(1), match.group(2)

    try:
        fm_data = yaml.safe_load(raw_fm)
    except yaml.YAMLError as exc:
        raise StorageError(f"Malformed frontmatter in {path}: {exc}", path=str(path)) from exc

    if fm_data is None:
        fm_data = {}

    try:
        frontmatter = frontmatter_model.model_validate(fm_data)
    except ValidationError as exc:
        raise StorageError(
            f"Frontmatter validation failed for {path}: {exc}",
            path=str(path),
            errors=exc.errors(),
        ) from exc

    return frontmatter, body


def write_markdown_with_frontmatter(path: Path, frontmatter: BaseModel, body: str) -> None:
    """Atomically write a Markdown file with YAML frontmatter.

    Args:
        path: Destination path.
        frontmatter: Pydantic model instance for the frontmatter.
        body: Markdown body text.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fm_data = frontmatter.model_dump(mode="json")
    fm_yaml = yaml.safe_dump(fm_data, default_flow_style=False, sort_keys=False)

    with open(tmp, "w") as f:
        f.write("---\n")
        f.write(fm_yaml)
        f.write("---\n")
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(path)
