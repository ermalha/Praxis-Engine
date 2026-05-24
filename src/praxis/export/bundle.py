"""Evidence-bundle builder (D-068).

Walks ``.praxis/`` deterministically, hashes each file, and packages the
tree into ``zip`` / ``tar.gz`` / ``dir`` form with a ``MANIFEST.json``
at the bundle root.

The recipient can verify integrity by re-hashing each entry and
comparing against the manifest. Files are sorted alphabetically before
hashing + packaging so the manifest is reproducible — feeding the same
engagement state into ``export_evidence_bundle`` twice produces
identical hashes.
"""

from __future__ import annotations

import contextlib
import hashlib
import shutil
import tarfile
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from praxis import __version__ as _praxis_version
from praxis.config.loader import load_engagement_config


class ExportError(Exception):
    """Raised when the evidence-bundle export cannot be produced."""


class BundleFormat(StrEnum):
    """Supported archive formats for ``praxis export evidence``."""

    ZIP = "zip"
    TAR_GZ = "tar.gz"
    DIR = "dir"


class ManifestFile(BaseModel):
    """One entry in the manifest's file list."""

    path: str
    sha256: str
    size_bytes: int


class BundleManifest(BaseModel):
    """Top-level manifest written as ``MANIFEST.json`` at the bundle root."""

    schema_version: int = 1
    praxis_version: str
    engagement_name: str
    generated_at: datetime
    files: list[ManifestFile]


# Paths inside ``.praxis/`` to exclude from the bundle.
# - ``*.tmp``      : orphaned from atomic-write failures (D-060).
# - ``__pycache__``: defensive; none expected under .praxis/ but a stray
#                    bundled-skills checkout could include one.
_EXCLUDED_SUFFIXES = (".tmp",)
_EXCLUDED_NAMES = ("__pycache__",)


def _iter_engagement_files(eng_path: Path) -> Iterator[Path]:
    """Yield every file under ``eng_path/.praxis/`` in sorted order.

    Sorting is depth-first lexicographic — both files and directories are
    sorted at each level. This is what makes the manifest reproducible.
    """
    root = eng_path / ".praxis"
    if not root.is_dir():
        raise ExportError(f"Not an engagement: {eng_path} (no .praxis/ found)")

    def _walk(directory: Path) -> Iterator[Path]:
        for entry in sorted(directory.iterdir()):
            if entry.name in _EXCLUDED_NAMES:
                continue
            if entry.is_dir():
                yield from _walk(entry)
                continue
            if entry.suffix in _EXCLUDED_SUFFIXES:
                continue
            yield entry

    yield from _walk(root)


def _sha256_of(path: Path) -> str:
    """Return the hex-digest SHA-256 of *path*. Streams the file in chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(eng_path: Path, *, now: datetime | None = None) -> BundleManifest:
    """Build a content-hashed manifest of the engagement's ``.praxis/`` tree.

    *now* lets tests pin the ``generated_at`` field for deterministic
    diffing; production callers leave it ``None`` to stamp current UTC.
    """
    # Validate ``.praxis/`` exists BEFORE delegating to load_engagement_config
    # so the export-specific error surfaces — ConfigError from a deeper
    # layer would leak abstraction.
    if not (eng_path / ".praxis").is_dir():
        raise ExportError(f"Not an engagement: {eng_path} (no .praxis/ found)")

    config = load_engagement_config(eng_path)
    when = now if now is not None else datetime.now(UTC)

    files: list[ManifestFile] = []
    root = eng_path / ".praxis"
    for abs_path in _iter_engagement_files(eng_path):
        # Manifest paths are relative to the bundle root (which mirrors
        # the engagement's ``.praxis/``), so a verifier can locate each
        # file without knowing the original engagement path.
        rel = abs_path.relative_to(root).as_posix()
        files.append(
            ManifestFile(
                path=rel,
                sha256=_sha256_of(abs_path),
                size_bytes=abs_path.stat().st_size,
            )
        )

    return BundleManifest(
        praxis_version=_praxis_version,
        engagement_name=config.name,
        generated_at=when,
        files=files,
    )


def export_evidence_bundle(
    eng_path: Path,
    output_path: Path,
    *,
    bundle_format: BundleFormat = BundleFormat.ZIP,
    now: datetime | None = None,
) -> Path:
    """Write an evidence bundle for *eng_path* to *output_path*.

    Args:
        eng_path: Engagement root (must contain ``.praxis/``).
        output_path: Destination. For ``zip`` / ``tar.gz`` formats this is
            the archive filename; for ``dir`` it's the target directory.
        bundle_format: One of :class:`BundleFormat`.
        now: Optional explicit ``generated_at`` (tests use this for
            reproducibility).

    Returns:
        The resolved absolute path the bundle was written to.

    Raises:
        ExportError: if the engagement is missing or the format is unknown.
    """
    manifest = build_manifest(eng_path, now=now)
    manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
    root = eng_path / ".praxis"

    out = output_path.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    if bundle_format is BundleFormat.ZIP:
        _write_zip(out, root, manifest_bytes)
    elif bundle_format is BundleFormat.TAR_GZ:
        _write_tar_gz(out, root, manifest_bytes)
    elif bundle_format is BundleFormat.DIR:
        _write_dir(out, root, manifest_bytes)
    else:  # pragma: no cover — Enum guards exhaustiveness
        raise ExportError(f"Unknown bundle format: {bundle_format!r}")

    return out


# ---------------------------------------------------------------------------
# Format writers — each consumes the pre-built manifest bytes so the file
# is added at the same canonical position in every format.
# ---------------------------------------------------------------------------


def _write_zip(out: Path, source_root: Path, manifest_bytes: bytes) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path in _iter_sorted_files(source_root):
            arcname = abs_path.relative_to(source_root).as_posix()
            zf.write(abs_path, arcname=arcname)
        zf.writestr("MANIFEST.json", manifest_bytes)


def _write_tar_gz(out: Path, source_root: Path, manifest_bytes: bytes) -> None:
    with tarfile.open(out, "w:gz") as tf:
        for abs_path in _iter_sorted_files(source_root):
            arcname = abs_path.relative_to(source_root).as_posix()
            tf.add(abs_path, arcname=arcname)
        # Manifest as an in-memory tarball entry.
        info = tarfile.TarInfo(name="MANIFEST.json")
        info.size = len(manifest_bytes)
        import io

        tf.addfile(info, io.BytesIO(manifest_bytes))


def _write_dir(out: Path, source_root: Path, manifest_bytes: bytes) -> None:
    # ``shutil.copytree`` would refuse if the dest exists; remove first.
    if out.exists():
        if out.is_dir():
            shutil.rmtree(out)
        else:
            with contextlib.suppress(OSError):
                out.unlink()
    shutil.copytree(source_root, out)
    (out / "MANIFEST.json").write_bytes(manifest_bytes)


def _iter_sorted_files(source_root: Path) -> Iterator[Path]:
    """Sibling of ``_iter_engagement_files`` but operates on the already-
    located root directory. Kept separate so the manifest builder and the
    format writers see the same ordering."""

    def _walk(directory: Path) -> Iterator[Path]:
        for entry in sorted(directory.iterdir()):
            if entry.name in _EXCLUDED_NAMES:
                continue
            if entry.is_dir():
                yield from _walk(entry)
                continue
            if entry.suffix in _EXCLUDED_SUFFIXES:
                continue
            yield entry

    yield from _walk(source_root)
