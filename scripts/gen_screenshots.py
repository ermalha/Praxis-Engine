"""Generate SVG screenshots of every Praxis TUI screen.

Drives ``PraxisApp`` via Textual's ``Pilot`` test driver against a seeded
demo engagement, captures one SVG per screen, writes to
``docs/screenshots/``. Reproducible: same seed input → same SVGs.

Usage:
    uv run python scripts/gen_screenshots.py [output_dir]

Default output_dir is ``docs/screenshots/``.

The seeding logic is shared with the TUI pilot tests
(``tests/integration/_tui_seed.py``) so screenshots and tested behaviour
can never drift.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# D-062 — share the demo-engagement seeder with the pilot tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "tests" / "integration"))
from _tui_seed import seed_demo_engagement, seed_demo_profile  # noqa: E402

from praxis.tui.app import PraxisApp  # noqa: E402

# Screens to capture: (binding key, app screen name, output filename)
_SCREENS: list[tuple[str, str, str]] = [
    ("1", "queue", "01-queue.svg"),
    ("2", "conversation", "02-chat.svg"),
    ("3", "engagement", "03-engagement.svg"),
    ("4", "audit", "04-audit.svg"),
    ("5", "backlog", "05-backlog.svg"),
    ("6", "config", "06-config.svg"),
    ("7", "setup", "07-setup.svg"),
    ("8", "priorities", "08-priorities.svg"),
    ("9", "artifact_viewer", "09-artifact-viewer.svg"),
]


async def _capture(eng_path: Path, output_dir: Path) -> None:
    """Pilot the TUI through every screen, save SVGs."""
    app = PraxisApp(engagement_path=eng_path, initial_screen="queue")
    async with app.run_test(size=(132, 40)) as pilot:
        await pilot.pause(0.6)  # let on_mount + first _load_* settle
        for key, screen_name, filename in _SCREENS:
            await pilot.press(key)
            # Give the screen a moment to render + first refresh cycle to populate
            await pilot.pause(0.6)
            out_path = output_dir / filename
            app.save_screenshot(path=str(out_path.parent), filename=out_path.name)
            print(f"  wrote {out_path.name} ({screen_name})")


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = Path(argv[1]) if len(argv) > 1 else repo_root / "docs" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="praxis-screenshot-") as tmp:
        tmp_path = Path(tmp)
        praxis_home = tmp_path / ".praxis"
        praxis_home.mkdir()
        # Isolate this run from the user's real ~/.praxis
        os.environ["PRAXIS_HOME"] = str(praxis_home)
        os.environ.setdefault("OPENAI_API_KEY", "stub-for-screenshots")

        eng_path = tmp_path / "demo-engagement"
        eng_path.mkdir()

        seed_demo_profile(praxis_home)
        seed_demo_engagement(eng_path)

        print(f"Generating screenshots into {output_dir}/")
        asyncio.run(_capture(eng_path, output_dir))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
