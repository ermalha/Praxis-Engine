"""D-060 — Atomic write helper for sufficiency reports + artifacts.

Closes Hermes review item #4. Previously ``sufficiency.py`` and
``artifacts/service.py`` used ``path.write_text(...)``, which leaves a
truncated file on disk if the process is killed mid-write. Those files
are the audit/evidence trail; partial writes would be especially bad.
``atomic_write_text`` writes to a sibling ``.tmp``, fsyncs, then renames.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from praxis.errors import StorageError
from praxis.storage.files import atomic_write_text


class TestAtomicWriteText:
    def test_happy_path_writes_content(self, tmp_path: Path) -> None:
        path = tmp_path / "report.json"
        atomic_write_text(path, '{"verdict": "sufficient"}')

        assert path.read_text(encoding="utf-8") == '{"verdict": "sufficient"}'
        # No leftover tmp.
        assert not path.with_suffix(".tmp").exists()

    def test_overwrites_existing_file_atomically(self, tmp_path: Path) -> None:
        """Pre-populate the destination, then overwrite. The replacement is
        all-or-nothing — readers see either the old content or the new, never
        a partial write."""
        path = tmp_path / "report.json"
        path.write_text("OLD", encoding="utf-8")

        atomic_write_text(path, "NEW")

        assert path.read_text(encoding="utf-8") == "NEW"
        assert not path.with_suffix(".tmp").exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Like the existing YAML/Markdown writers, parent dirs are created."""
        path = tmp_path / "deep" / "nested" / "report.json"
        atomic_write_text(path, "x")
        assert path.read_text() == "x"

    def test_failure_during_rename_leaves_original_intact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If ``rename`` raises, the pre-existing file at ``path`` must be
        unchanged. That's the whole point of the atomic pattern."""
        path = tmp_path / "report.json"
        path.write_text("ORIGINAL", encoding="utf-8")

        original_rename = Path.rename

        def failing_rename(self: Path, target: Path) -> Path:
            if self.suffix == ".tmp":
                raise OSError("simulated rename failure")
            return original_rename(self, target)

        monkeypatch.setattr(Path, "rename", failing_rename)

        with pytest.raises(StorageError, match="Cannot atomically write"):
            atomic_write_text(path, "NEW CONTENT THAT MUST NOT LAND")

        assert path.read_text(encoding="utf-8") == "ORIGINAL", (
            "atomic_write_text leaked the new content into the original file. "
            "The whole point of the helper is that mid-write failures preserve "
            "the previous on-disk state."
        )

    def test_new_file_failure_cleans_up_tmp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mid-write failure when the destination doesn't yet exist: no final
        file appears, and the orphaned ``.tmp`` is cleaned up."""
        path = tmp_path / "report.json"

        original_rename = Path.rename

        def failing_rename(self: Path, target: Path) -> Path:
            if self.suffix == ".tmp":
                raise OSError("simulated rename failure")
            return original_rename(self, target)

        monkeypatch.setattr(Path, "rename", failing_rename)

        with pytest.raises(StorageError, match="Cannot atomically write"):
            atomic_write_text(path, "anything")

        assert not path.exists()
        assert not path.with_suffix(".tmp").exists(), (
            "atomic_write_text left an orphaned .tmp file after failure."
        )

    def test_failure_during_fsync_does_not_corrupt_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If fsync itself raises (e.g. disk full), the rename never runs,
        so the destination is untouched."""
        path = tmp_path / "report.json"
        path.write_text("ORIGINAL", encoding="utf-8")

        with (
            patch("praxis.storage.files.os.fsync", side_effect=OSError("disk full")),
            pytest.raises(StorageError, match="Cannot atomically write"),
        ):
            atomic_write_text(path, "NEW")

        assert path.read_text(encoding="utf-8") == "ORIGINAL"


class TestIntegrationWithSufficiencyReportPath:
    def test_writing_via_real_filename_pattern(self, tmp_path: Path) -> None:
        """Sanity: the actual filename shape used by sufficiency reports
        (a 12-char hex id with a ``.json`` suffix) writes + reads correctly."""
        path = tmp_path / "568d2204082c.json"
        payload = '{"schema_version": 1, "verdict": "insufficient"}'
        atomic_write_text(path, payload)
        assert path.read_text() == payload
