"""Tests for file-based storage helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from praxis.errors import StorageError
from praxis.storage.files import (
    read_markdown_with_frontmatter,
    read_yaml_typed,
    write_markdown_with_frontmatter,
    write_yaml_typed,
)


class SampleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    count: int = 0


class TestYamlRoundTrip:
    def test_write_and_read(self, tmp_path: Path) -> None:
        path = tmp_path / "test.yaml"
        obj = SampleModel(name="hello", count=42)
        write_yaml_typed(path, obj)
        loaded = read_yaml_typed(path, SampleModel)
        assert loaded.name == "hello"
        assert loaded.count == 42

    def test_atomic_write_creates_parent(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "test.yaml"
        write_yaml_typed(path, SampleModel(name="deep"))
        assert path.exists()

    def test_read_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(StorageError, match="not found"):
            read_yaml_typed(tmp_path / "missing.yaml", SampleModel)

    def test_read_malformed_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(": bad: yaml: {{")
        with pytest.raises(StorageError, match="Malformed"):
            read_yaml_typed(path, SampleModel)

    def test_read_validation_error(self, tmp_path: Path) -> None:
        path = tmp_path / "invalid.yaml"
        path.write_text("unknown_field: true\n")
        with pytest.raises(StorageError, match="Validation failed"):
            read_yaml_typed(path, SampleModel)


class FrontmatterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    version: int = 1


class TestMarkdownFrontmatter:
    def test_write_and_read(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        fm = FrontmatterModel(title="Test Doc", version=2)
        body = "# Hello\n\nThis is content.\n"
        write_markdown_with_frontmatter(path, fm, body)
        loaded_fm, loaded_body = read_markdown_with_frontmatter(path, FrontmatterModel)
        assert loaded_fm.title == "Test Doc"
        assert loaded_fm.version == 2
        assert "Hello" in loaded_body

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(StorageError, match="not found"):
            read_markdown_with_frontmatter(tmp_path / "nope.md", FrontmatterModel)

    def test_no_frontmatter_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "plain.md"
        path.write_text("# No frontmatter\n")
        with pytest.raises(StorageError, match="No YAML frontmatter"):
            read_markdown_with_frontmatter(path, FrontmatterModel)
