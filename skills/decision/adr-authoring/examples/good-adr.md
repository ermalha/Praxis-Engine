# ADR-003: Use PostgreSQL for Event Storage

**Status:** Accepted
**Date:** 2024-03-15
**Deciders:** Tech Lead, Platform Architect

## Context

Our event-sourced order system generates ~50K events/day and requires:
- ACID guarantees for event ordering
- Efficient range queries by timestamp and aggregate ID
- Integration with existing monitoring stack (Grafana/Prometheus)
- Team familiarity for on-call support

We currently use PostgreSQL 15 for our main database and have operational expertise.

## Decision

We will use PostgreSQL with a dedicated `events` table and BRIN indexes for event storage.

## Consequences

### Positive
- Zero new infrastructure to operate
- Team already knows PostgreSQL operationally
- ACID guarantees built-in
- Can join events with other domain tables when needed

### Negative
- Single-node write throughput ceiling (~100K events/day before needing partitioning)
- No built-in pub/sub for real-time consumers (need polling or NOTIFY)

### Risks
- If event volume grows 10x, we'll need table partitioning or a migration

## Alternatives Considered

### Alternative 1: Apache Kafka
- Good for high-throughput streaming
- Rejected because: Operational complexity for our team size (3 engineers), overkill at 50K events/day

### Alternative 2: EventStoreDB
- Purpose-built for event sourcing
- Rejected because: No team expertise, adds a new system to operate, small community
