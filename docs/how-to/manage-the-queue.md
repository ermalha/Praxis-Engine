# Managing the Work Queue

## Viewing your queue

```bash
praxis queue
```

Shows a prioritized table of human work-items. Critical items appear first,
followed by items with approaching deadlines.

To see all items (including agent tasks and completed):

```bash
praxis queue --all
```

## Working through items

### 1. Start an item

```bash
praxis queue start wi-abc123
```

### 2. Complete an item

```bash
praxis queue done wi-abc123 --note "Sent the email to Maria"
```

Or use `commit` for a one-step start-and-done:

```bash
praxis queue commit wi-abc123 --note "Maria replied: threshold is 10k"
```

### 3. Provide structured return data

When completing items linked to questions, you can include the answer:

```bash
praxis queue commit wi-abc123 \
  --note "Maria confirmed the threshold" \
  --result '{"answer": "The AP threshold is $10,000"}'
```

This automatically updates the linked OpenQuestion to `answered`.

## Rejecting items

If an item is unnecessary or wrong:

```bash
praxis queue reject wi-abc123 --note "Wrong stakeholder, Maria doesn't handle this"
```

## Deferring items

To push an item back for later:

```bash
praxis queue defer wi-abc123
```

The item moves to `deferred` status. Re-queue it later when ready.

## JSON output

For scripting or integration:

```bash
praxis queue --json
```
