"""Email tools — send email (dangerous) and poll inbox."""

from __future__ import annotations

from praxis.tools import ToolContext, ToolResult, tool


@tool(
    name="email_send",
    description="Send an email via SMTP.",
    toolset="email",
    dangerous=True,
)
def email_send(
    ctx: ToolContext,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    in_reply_to: str | None = None,
) -> ToolResult:
    """Send an email. Requires human approval."""
    from praxis.integrations.email.smtp_sender import SmtpSender

    settings = _smtp_settings(ctx)
    sender = SmtpSender(settings)
    sender.send(to=to, subject=subject, body=body, cc=cc, in_reply_to=in_reply_to)
    return ToolResult(content=f"Email sent to {to}: {subject}")


def _smtp_settings(ctx: ToolContext) -> dict[str, str]:
    """Extract SMTP settings from the engagement config."""
    if ctx.engagement is None:
        return {}
    cfg = ctx.engagement.integrations.get("smtp")
    if cfg is None:
        return {}
    return cfg.settings
