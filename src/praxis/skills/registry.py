"""Skill registry — caches loaded skills with mtime-based reload."""

from __future__ import annotations

from pathlib import Path

from .loader import load_skills
from .models import Skill


class SkillRegistry:
    """Cache and serve skills, reloading when filesystem changes are detected.

    The registry tracks the maximum mtime across all skill directories.
    On each ``list_skills()`` call it checks whether any directory has been
    modified and reloads if so.
    """

    def __init__(
        self,
        engagement_path: Path | None = None,
        *,
        user_home: Path | None = None,
        enabled_toolsets: set[str] | None = None,
        populated_engagement_fields: set[str] | None = None,
    ) -> None:
        self._engagement_path = engagement_path
        self._user_home = user_home
        self._enabled_toolsets = enabled_toolsets or set()
        self._populated_fields = populated_engagement_fields or set()
        self._skills: list[Skill] = []
        self._last_mtime: float = 0.0
        self._loaded = False

    def _check_reload(self) -> None:
        """Reload skills if filesystem has changed or not yet loaded."""
        current_mtime = self._scan_mtime()
        if not self._loaded or current_mtime > self._last_mtime:
            self._skills = load_skills(
                engagement_path=self._engagement_path,
                user_home=self._user_home,
            )
            self._last_mtime = current_mtime
            self._loaded = True

    def _scan_mtime(self) -> float:
        """Return the maximum mtime across all skill source directories."""
        mtimes: list[float] = []
        for root in self._skill_roots():
            if root.is_dir():
                mtimes.append(root.stat().st_mtime)
                for path in root.rglob("SKILL.md"):
                    mtimes.append(path.stat().st_mtime)
        return max(mtimes) if mtimes else 0.0

    def _skill_roots(self) -> list[Path]:
        """Return the list of skill root directories to watch."""
        from .loader import _bundled_skills_root

        roots: list[Path] = [_bundled_skills_root()]

        user_home = self._user_home or (Path.home() / ".praxis")
        roots.append(user_home / "skills")

        if self._engagement_path is not None:
            roots.append(self._engagement_path / ".praxis" / "skills")

        return roots

    def _is_active(self, skill: Skill) -> bool:
        """Check whether a skill meets activation criteria."""
        fm = skill.frontmatter

        # Must be published
        if fm.status != "published":
            return False

        # requires_toolsets must all be enabled
        if fm.requires_toolsets and not set(fm.requires_toolsets).issubset(self._enabled_toolsets):
            return False

        # fallback_for_toolsets — skill only active if NONE of these are enabled
        if fm.fallback_for_toolsets and set(fm.fallback_for_toolsets) & self._enabled_toolsets:
            return False

        # required_engagement_fields must all be populated
        return not (
            fm.required_engagement_fields
            and not set(fm.required_engagement_fields).issubset(self._populated_fields)
        )

    def list_skills(self, *, only_active: bool = True) -> list[Skill]:
        """Return loaded skills, optionally filtered by activation criteria.

        Args:
            only_active: If True, filter by toolset requirements, fallback
                rules, required engagement fields, and published status.
        """
        self._check_reload()
        if only_active:
            return [s for s in self._skills if self._is_active(s)]
        return list(self._skills)

    def get(self, name: str) -> Skill | None:
        """Get a skill by name (searches all skills, including drafts)."""
        self._check_reload()
        for skill in self._skills:
            if skill.frontmatter.name == name:
                return skill
        return None

    def get_file(self, name: str, file: str) -> str:
        """Read a reference/template/example file from a skill.

        Args:
            name: Skill name.
            file: Relative filename within references/, templates/, or examples/.

        Returns:
            File contents as a string.

        Raises:
            KeyError: If the skill or file is not found.
        """
        skill = self.get(name)
        if skill is None:
            msg = f"Unknown skill: {name!r}"
            raise KeyError(msg)

        # Search across references, templates, examples
        for subdir in ("references", "templates", "examples"):
            candidate = skill.path / subdir / file
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")

        msg = f"File {file!r} not found in skill {name!r}"
        raise KeyError(msg)
