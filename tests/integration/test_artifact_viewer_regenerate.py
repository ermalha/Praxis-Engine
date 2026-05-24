"""D-067 — Artifact Viewer ``R`` keybind triggers a regenerate.

Pilot test that drives the TUI through ``app.run_test()``, stubs
``generate_artifact`` to avoid a real LLM round-trip, presses ``R`` on
the selected row, and verifies the stub was invoked + a new row landed
in the DataTable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from praxis.tui.app import PraxisApp

from ._tui_seed import seed_demo_engagement, seed_demo_profile

_INITIAL_SETTLE = 0.5
_SWITCH_SETTLE = 0.3
_WORKER_SETTLE = 0.8  # generate_artifact stub + UI refresh need a beat


@pytest.fixture()
def seeded_engagement(tmp_engagement: Path, tmp_home: Path) -> Path:
    seed_demo_profile()
    seed_demo_engagement(tmp_engagement)
    return tmp_engagement


@pytest.fixture()
def fake_generate_artifact(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub ``praxis.artifacts.service.generate_artifact``.

    Writes a real file to the artifacts directory so the screen's
    auto-refresh picks it up. Records the call args in the returned
    dict so the test can assert what the screen passed.
    """
    captured: dict[str, Any] = {"calls": []}

    def fake(
        *,
        engagement_path: Path,
        profile: Any,
        model: str,
        transport: Any,
        artifact_kind: str,
        prompt: str,
        output_dir: str = "reports",
    ) -> Any:
        captured["calls"].append(
            {
                "engagement_path": engagement_path,
                "profile": profile,
                "model": model,
                "artifact_kind": artifact_kind,
                "prompt": prompt,
                "output_dir": output_dir,
            }
        )
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = engagement_path / ".praxis" / "artifacts" / output_dir / f"{artifact_kind}-{ts}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Regenerated {artifact_kind}\n\nStub content.", encoding="utf-8")
        return SimpleNamespace(
            path=path,
            content=path.read_text(),
            artifact_kind=artifact_kind,
            sufficiency_verdict=None,
            sufficiency_report_path=None,
            created_at=datetime.now(UTC),
        )

    # Patch where the screen imports from. Lazy-import inside the screen
    # means we only need to patch the module-level symbol.
    monkeypatch.setattr("praxis.artifacts.service.generate_artifact", fake)
    return captured


@pytest.fixture()
def fake_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``make_transport`` so the screen's plumbing doesn't try a
    real OpenAI client init. The stub is never actually exercised by
    ``generate_artifact`` (also stubbed) — this fixture just lets the
    ``make_transport()`` call inside the worker succeed."""

    def fake_make(_cfg: object) -> object:
        return SimpleNamespace(name="fake")

    monkeypatch.setattr("praxis.transport.make_transport", fake_make)


async def test_r_keybind_regenerates_selected_artifact(
    seeded_engagement: Path,
    fake_generate_artifact: dict[str, Any],
    fake_transport: None,
) -> None:
    """Press R on Artifact Viewer → stub is called with the row's kind →
    a new row appears in the DataTable."""
    app = PraxisApp(
        engagement_path=seeded_engagement,
        profile_name="demo",
        initial_screen="queue",
    )

    async with app.run_test(size=(132, 40)) as pilot:
        await pilot.pause(_INITIAL_SETTLE)
        # Switch to Artifact Viewer (key 9).
        await pilot.press("9")
        await pilot.pause(_SWITCH_SETTLE)

        from textual.widgets import DataTable

        table = app.screen.query_one("#artifact-list", DataTable)
        starting_rows = table.row_count
        assert starting_rows == 1, f"Seed has exactly one artifact; got {starting_rows} rows"

        # Press R — triggers the regenerate worker.
        await pilot.press("R")
        await pilot.pause(_WORKER_SETTLE)

        assert len(fake_generate_artifact["calls"]) == 1, (
            f"generate_artifact stub was not invoked exactly once; "
            f"calls={fake_generate_artifact['calls']!r}"
        )

        call = fake_generate_artifact["calls"][0]
        # The seeded artifact is ``scope-brief-demo.md``; the kind-recovery
        # helper drops only the ``.md`` since no timestamp suffix is present.
        assert call["artifact_kind"] == "scope-brief-demo", (
            f"Expected kind 'scope-brief-demo'; got {call['artifact_kind']!r}"
        )
        assert "regenerate" in call["prompt"].lower()

        # The screen's auto-refresh interval is 3s — settle a bit more
        # then trigger a manual refresh to be deterministic.
        await pilot.press("r")
        await pilot.pause(_SWITCH_SETTLE)

        # Re-query the table; row count should now be 2.
        table = app.screen.query_one("#artifact-list", DataTable)
        assert table.row_count == 2, (
            f"After regenerate + refresh, expected 2 rows; got {table.row_count}"
        )


async def test_r_without_profile_shows_error_notification(
    seeded_engagement: Path,
    fake_generate_artifact: dict[str, Any],
) -> None:
    """If the TUI was launched without a profile, R must NOT attempt the LLM
    call — it should surface a clear error notification instead."""
    app = PraxisApp(
        engagement_path=seeded_engagement,
        profile_name=None,  # explicitly omitted
        initial_screen="queue",
    )

    async with app.run_test(size=(132, 40)) as pilot:
        await pilot.pause(_INITIAL_SETTLE)
        await pilot.press("9")
        await pilot.pause(_SWITCH_SETTLE)

        await pilot.press("R")
        await pilot.pause(_WORKER_SETTLE)

        # The stub must NOT have been called.
        assert fake_generate_artifact["calls"] == [], (
            "Regenerate proceeded without a profile — should have been blocked"
        )
