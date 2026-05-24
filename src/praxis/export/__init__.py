"""Evidence-bundle export — package engagement state for audit hand-off.

Hermes review item #13: "Given the product is audit/BA-focused, this
would be a strong differentiator." Turns Praxis from agent tool into
audit-ready BA work product by bundling the entire ``.praxis/`` tree
plus a content-hashed ``MANIFEST.json`` into a single archive.
"""

from .bundle import (
    BundleFormat,
    BundleManifest,
    ExportError,
    ManifestFile,
    build_manifest,
    export_evidence_bundle,
)

__all__ = [
    "BundleFormat",
    "BundleManifest",
    "ExportError",
    "ManifestFile",
    "build_manifest",
    "export_evidence_bundle",
]
