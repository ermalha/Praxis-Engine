"""CLI commands: ``praxis integrations`` — manage external integrations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.config.loader import load_engagement_config

integrations_app = typer.Typer(name="integrations", help="Manage external integrations.")
err_console = Console(stderr=True)


def _resolve_eng(engagement: str | None) -> Path:
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    return eng


@integrations_app.command("status")
def integrations_status(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show health status of all enabled integrations."""
    eng = _resolve_eng(engagement)
    cfg = load_engagement_config(eng)

    # Import integration modules to trigger registration
    _ensure_registered()

    from praxis.integrations.registry import get_integration

    table = Table(title="Integration Status")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Message")

    for name, int_cfg in cfg.integrations.items():
        try:
            integration = get_integration(int_cfg.kind, int_cfg)
            result = integration.health_check()
            color = {
                "healthy": "green",
                "degraded": "yellow",
                "unhealthy": "red",
                "disabled": "dim",
            }.get(result.status.value, "white")
            table.add_row(name, f"[{color}]{result.status.value}[/{color}]", result.message)
        except Exception as exc:
            table.add_row(name, "[red]error[/red]", str(exc))

    console = Console()
    console.print(table)


@integrations_app.command("test")
def integrations_test(
    kind: str = typer.Argument(..., help="Integration kind to test."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Run a connectivity test for a specific integration."""
    eng = _resolve_eng(engagement)
    cfg = load_engagement_config(eng)

    _ensure_registered()

    from praxis.integrations.registry import get_integration

    int_cfg = cfg.integrations.get(kind)
    if int_cfg is None:
        err_console.print(f"[red]Integration '{kind}' not configured.[/red]")
        raise typer.Exit(1)

    integration = get_integration(int_cfg.kind, int_cfg)
    result = integration.health_check()
    console = Console()
    console.print(f"[bold]{kind}[/bold]: {result.status.value} — {result.message}")


@integrations_app.command("enable")
def integrations_enable(
    kind: str = typer.Argument(..., help="Integration kind to enable."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Print the configuration template for an integration."""
    _resolve_eng(engagement)
    console = Console()
    templates = {
        "jira": (
            "jira:\n  enabled: true\n  kind: jira\n  settings:\n"
            "    base_url: https://example.atlassian.net\n"
            "    email_env: JIRA_EMAIL\n    token_env: JIRA_TOKEN\n"
            "    default_project: BA"
        ),
        "confluence": (
            "confluence:\n  enabled: true\n  kind: confluence\n  settings:\n"
            "    base_url: https://example.atlassian.net\n"
            "    email_env: CONFLUENCE_EMAIL\n    token_env: CONFLUENCE_TOKEN"
        ),
        "imap": (
            "email:\n  enabled: true\n  kind: imap\n  settings:\n"
            "    host: imap.gmail.com\n    port: '993'\n    tls: 'true'\n"
            "    user_env: PRAXIS_IMAP_USER\n    password_env: PRAXIS_IMAP_PASSWORD\n"
            "    mailbox: INBOX"
        ),
        "smtp": (
            "smtp:\n  enabled: true\n  kind: smtp\n  settings:\n"
            "    host: smtp.gmail.com\n    port: '587'\n    tls: 'true'\n"
            "    user_env: PRAXIS_SMTP_USER\n    password_env: PRAXIS_SMTP_PASSWORD"
        ),
        "webhook": (
            "webhook:\n  enabled: true\n  kind: webhook\n  settings:\n"
            "    port: '8765'\n    paths: '[]'"
        ),
    }
    template = templates.get(kind)
    if template:
        console.print(f"Add to your engagement config.yaml under 'integrations:':\n\n{template}")
    else:
        console.print(f"[yellow]No template for '{kind}'.[/yellow]")


def _ensure_registered() -> None:
    """Import integration modules to trigger @register_integration decorators."""
    import praxis.integrations.confluence.integration  # noqa: F401
    import praxis.integrations.email.integration  # noqa: F401
    import praxis.integrations.jira.integration  # noqa: F401
    import praxis.integrations.webhook.integration  # noqa: F401
