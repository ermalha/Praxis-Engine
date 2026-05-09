"""``praxis profile`` commands — manage profiles."""

from __future__ import annotations

import json

import typer

from praxis.config import (
    GlobalConfig,
    ModelConfig,
    Provider,
    create_profile,
    delete_profile,
    get_active_profile_name,
    list_profiles,
    load_global_config,
    save_global_config,
    save_profile,
)
from praxis.errors import ConfigError

profile_app = typer.Typer(name="profile", help="Manage Praxis profiles.")


@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name ([a-z0-9_-]+)."),  # noqa: B008
    provider: str | None = typer.Option(  # noqa: B008
        None,
        help="LLM provider (anthropic, openai, openrouter, openai_compat).",
    ),
    model: str | None = typer.Option(None, help="Model name (e.g. claude-sonnet-4-20250514)."),  # noqa: B008
    api_key_env: str | None = typer.Option(  # noqa: B008
        None,
        help="Environment variable holding the API key (e.g. ANTHROPIC_API_KEY).",
    ),
    set_default: bool = typer.Option(False, "--set-default", help="Set as default profile."),  # noqa: B008
) -> None:
    """Create a new profile."""
    try:
        profile = create_profile(name)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # If all three model options are provided, configure the default model alias.
    if provider and model and api_key_env:
        model_config = ModelConfig(
            provider=Provider(provider),
            model=model,
            api_key_env=api_key_env,
        )
        profile.model_aliases["default"] = model_config
        profile.default_model_alias = "default"
        save_profile(profile)

    # Auto-default: if this is the only profile, set as default automatically.
    existing = list_profiles()
    is_only_profile = len(existing) == 1 and existing[0] == name

    if set_default or is_only_profile:
        try:
            global_cfg = load_global_config()
        except ConfigError:
            global_cfg = GlobalConfig()
        global_cfg.default_profile = name
        save_global_config(global_cfg)

    typer.echo(f"Profile '{profile.name}' created.")

    if is_only_profile and not set_default:
        typer.echo("  Auto-set as default profile (only profile).")

    if not profile.model_aliases:
        typer.echo(
            "  Next: configure a model with --provider, --model, and --api-key-env,\n"
            "  or edit ~/.praxis/profiles/{name}/profile.yaml directly."
        )


@profile_app.command("list")
def profile_list(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
) -> None:
    """List all profiles."""
    profiles = list_profiles()
    active = get_active_profile_name()
    if as_json:
        typer.echo(json.dumps({"profiles": profiles, "active": active}))
    else:
        if not profiles:
            typer.echo("No profiles found.")
            return
        for p in profiles:
            marker = " (active)" if p == active else ""
            typer.echo(f"  {p}{marker}")


@profile_app.command("use")
def profile_use(
    name: str = typer.Argument(..., help="Profile name to activate."),  # noqa: B008
) -> None:
    """Set the active profile (via PRAXIS_PROFILE env var hint)."""
    profiles = list_profiles()
    if name not in profiles:
        typer.echo(f"Error: Profile '{name}' does not exist.", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"To activate profile '{name}', set: export PRAXIS_PROFILE={name}\n"
        f"Or update default_profile in ~/.praxis/config.yaml."
    )


@profile_app.command("delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile name to delete."),  # noqa: B008
    force: bool = typer.Option(False, "--force", help="Delete even if active."),  # noqa: B008
) -> None:
    """Delete a profile."""
    try:
        delete_profile(name, force=force)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Profile '{name}' deleted.")
