"""D-068 — Evidence-bundle export.

Closes Hermes review item #13 — "audit-ready BA work product." Tests
cover the three output formats (zip / tar.gz / dir), the manifest's
content-hash reproducibility, the CLI invocation, and the missing-
engagement error path.
"""

from __future__ import annotations

import json
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.engagement import StakeholderRepo
from praxis.export import (
    BundleFormat,
    ExportError,
    build_manifest,
    export_evidence_bundle,
)

runner = CliRunner()


@pytest.fixture()
def populated_engagement(tmp_engagement: Path, tmp_home: Path) -> Path:
    """A minimal engagement with one stakeholder + one work item, enough to
    exercise the engagement/, state/, and audit JSONL paths."""
    init_engagement(tmp_engagement, "Acme Bundle Test")
    StakeholderRepo(tmp_engagement).add(name="Alice", role="VP")
    return tmp_engagement


class TestManifestReproducibility:
    def test_same_engagement_yields_identical_hashes(self, populated_engagement: Path) -> None:
        """The whole point of the manifest is integrity verification. Two
        builds against the same on-disk state MUST produce identical
        per-file hashes — otherwise the audit recipient can't verify."""
        fixed_now = datetime(2026, 1, 1, tzinfo=UTC)

        m1 = build_manifest(populated_engagement, now=fixed_now)
        m2 = build_manifest(populated_engagement, now=fixed_now)

        assert len(m1.files) == len(m2.files), "file lists differ in length"
        for f1, f2 in zip(m1.files, m2.files, strict=True):
            assert f1.path == f2.path, "file ordering not deterministic"
            assert f1.sha256 == f2.sha256, f"hash differs for {f1.path}"
            assert f1.size_bytes == f2.size_bytes

    def test_manifest_lists_known_engagement_files(self, populated_engagement: Path) -> None:
        """The manifest must include the seed entities we put there."""
        m = build_manifest(populated_engagement)
        paths = {f.path for f in m.files}

        assert "config.yaml" in paths
        assert "engagement/stakeholders.yaml" in paths


class TestZipFormat:
    def test_zip_roundtrip_preserves_files_and_manifest(
        self, populated_engagement: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "evidence.zip"
        written = export_evidence_bundle(populated_engagement, out, bundle_format=BundleFormat.ZIP)

        assert written.exists()
        assert written.suffix == ".zip"

        with zipfile.ZipFile(written) as zf:
            names = set(zf.namelist())
            assert "MANIFEST.json" in names
            assert "config.yaml" in names
            assert "engagement/stakeholders.yaml" in names

            manifest_data = json.loads(zf.read("MANIFEST.json"))
            assert manifest_data["schema_version"] == 1
            assert manifest_data["engagement_name"] == "Acme Bundle Test"
            assert manifest_data["files"], "manifest has no files entry"


class TestTarGzFormat:
    def test_tar_gz_contains_manifest_and_files(
        self, populated_engagement: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "evidence.tar.gz"
        export_evidence_bundle(populated_engagement, out, bundle_format=BundleFormat.TAR_GZ)

        with tarfile.open(out, "r:gz") as tf:
            names = set(tf.getnames())
            assert "MANIFEST.json" in names
            assert "config.yaml" in names

            manifest_member = tf.extractfile("MANIFEST.json")
            assert manifest_member is not None
            data = json.loads(manifest_member.read())
            assert data["engagement_name"] == "Acme Bundle Test"


class TestDirFormat:
    def test_dir_format_is_a_plain_tree(self, populated_engagement: Path, tmp_path: Path) -> None:
        out = tmp_path / "evidence-dir"
        export_evidence_bundle(populated_engagement, out, bundle_format=BundleFormat.DIR)

        assert out.is_dir()
        assert (out / "MANIFEST.json").exists()
        assert (out / "config.yaml").exists()
        assert (out / "engagement" / "stakeholders.yaml").exists()

    def test_dir_format_overwrites_existing_destination(
        self, populated_engagement: Path, tmp_path: Path
    ) -> None:
        """If the dest already exists (re-export), the bundler clears it
        rather than failing — otherwise users can't iteratively refine."""
        out = tmp_path / "evidence-dir"
        out.mkdir()
        (out / "stale.txt").write_text("should be wiped")

        export_evidence_bundle(populated_engagement, out, bundle_format=BundleFormat.DIR)

        assert not (out / "stale.txt").exists()
        assert (out / "MANIFEST.json").exists()


class TestErrorPaths:
    def test_missing_engagement_raises_export_error(self, tmp_path: Path) -> None:
        with pytest.raises(ExportError, match="Not an engagement"):
            build_manifest(tmp_path / "no-such-engagement")


class TestExclusions:
    def test_tmp_files_are_excluded_from_bundle(
        self, populated_engagement: Path, tmp_path: Path
    ) -> None:
        """Orphaned ``.tmp`` files from atomic-write failures (D-060) must
        not leak into the audit bundle — they're internal cleanup state."""
        praxis_dir = populated_engagement / ".praxis"
        (praxis_dir / "state" / "junk.tmp").parent.mkdir(parents=True, exist_ok=True)
        (praxis_dir / "state" / "junk.tmp").write_text("orphaned tmp")

        out = tmp_path / "evidence.zip"
        export_evidence_bundle(populated_engagement, out, bundle_format=BundleFormat.ZIP)

        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert not any(n.endswith(".tmp") for n in names), (
            f".tmp files leaked into bundle: {[n for n in names if n.endswith('.tmp')]}"
        )


class TestCLI:
    def test_export_evidence_via_cli(self, populated_engagement: Path, tmp_path: Path) -> None:
        out = tmp_path / "evidence.zip"
        result = runner.invoke(
            app,
            [
                "export",
                "evidence",
                "-e",
                str(populated_engagement),
                "--format",
                "zip",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        assert "Wrote evidence bundle" in result.output

    def test_unknown_format_exits_clean(self, populated_engagement: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "export",
                "evidence",
                "-e",
                str(populated_engagement),
                "--format",
                "rar",  # nope
                "--output",
                str(tmp_path / "out"),
            ],
        )
        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "rar" in combined.lower()
        # The error message names the valid formats.
        assert "zip" in combined.lower()
