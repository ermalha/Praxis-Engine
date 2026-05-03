"""Browser harness install helper.

Installs/links the browser-use/browser-harness into the Praxis skills
directory so the agent can delegate browser automation to it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

from praxis.errors import IntegrationError

logger = structlog.get_logger()

BROWSER_HARNESS_REPO = "https://github.com/browser-use/browser-harness.git"
DEFAULT_INSTALL_PATH = Path.home() / ".praxis" / "browser-harness"


def install(install_path: Path | None = None) -> Path:
    """Clone the browser-harness repo and symlink skills.

    Returns the installation path.
    """
    dest = install_path or DEFAULT_INSTALL_PATH

    if dest.exists():
        logger.info("browser.already_installed", path=str(dest))
        _update(dest)
    else:
        logger.info("browser.cloning", repo=BROWSER_HARNESS_REPO, dest=str(dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", BROWSER_HARNESS_REPO, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise IntegrationError(
                f"Failed to clone browser-harness: {exc}",
                kind="browser",
            ) from exc

    _symlink_skills(dest)
    return dest


def _update(dest: Path) -> None:
    """Pull latest changes."""
    try:
        subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("browser.update_failed", path=str(dest))


def _symlink_skills(harness_path: Path) -> None:
    """Symlink SKILL.md and skill directories into ~/.praxis/skills/."""
    skills_dir = Path.home() / ".praxis" / "skills" / "browser-harness"
    skills_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        ("SKILL.md", harness_path / "SKILL.md"),
        ("interaction-skills", harness_path / "interaction-skills"),
        ("domain-skills", harness_path / "domain-skills"),
    ]

    for name, source in targets:
        link = skills_dir / name
        if link.exists() or link.is_symlink():
            link.unlink()
        if source.exists():
            link.symlink_to(source)
            logger.info("browser.symlinked", link=str(link), target=str(source))


def doctor(install_path: Path | None = None) -> dict[str, object]:
    """Verify the browser-harness installation.

    Returns a dict with diagnostic results.
    """
    dest = install_path or DEFAULT_INSTALL_PATH
    results: dict[str, object] = {
        "installed": dest.exists(),
        "path": str(dest),
        "skills_linked": False,
    }

    if not dest.exists():
        results["message"] = "Not installed. Run: praxis browser install"
        return results

    skills_dir = Path.home() / ".praxis" / "skills" / "browser-harness"
    skill_md = skills_dir / "SKILL.md"
    results["skills_linked"] = skill_md.exists() or skill_md.is_symlink()

    if results["skills_linked"]:
        results["message"] = "Browser harness installed and skills linked."
    else:
        results["message"] = "Installed but skills not linked. Re-run install."

    return results
