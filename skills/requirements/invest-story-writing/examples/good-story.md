# Good Story Example

## Story

As a **hiring manager**,
I want to **receive an email notification when a candidate completes their assessment**,
so that **I can review results promptly and reduce time-to-hire**.

## Why it's good

- **Independent** — No dependency on other stories; notification system exists
- **Negotiable** — Could discuss: email vs. in-app notification, immediate vs. batched
- **Valuable** — Clear business value (reduce time-to-hire)
- **Estimable** — Team can size this (event trigger + email template)
- **Small** — Single notification, one trigger, one recipient type
- **Testable** — Clear acceptance criteria possible

## Acceptance Criteria

1. Given a candidate completes all assessment sections, when the assessment is submitted, then the hiring manager receives an email within 5 minutes
2. Given the notification is sent, when the manager opens the email, then it contains the candidate name, role, and a link to view results
3. Given the manager has notification preferences set to "off," when an assessment completes, then no email is sent
