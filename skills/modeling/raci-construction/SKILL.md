---
name: raci-construction
category: modeling
description: Build a RACI matrix from a process or scope statement with conflict checks.
when_to_use: |
  When defining roles and responsibilities for deliverables, processes, or
  decisions. Use early in engagement to prevent accountability gaps.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# RACI Construction

## Purpose

A RACI matrix eliminates ambiguity about who does what. It maps tasks or
deliverables to roles using four assignment types, preventing the common
failure mode of "everyone assumes someone else is handling it."

## Procedure

### 1. List activities or deliverables

Start from your source material:
- Process model tasks (from BPMN)
- Scope statement work packages
- Project deliverables list
- Decision points requiring governance

Each row in the RACI should be a discrete, named activity or deliverable.

### 2. Identify roles (not people)

Columns are roles, not individuals:
- Use role titles: "Product Owner", "BA Lead", "Dev Team"
- Keep to 5-8 roles; aggregate minor roles
- Include external roles where relevant (vendor, regulator)

### 3. Assign RACI codes

For each cell (activity x role):
- **R (Responsible)** — Does the work. Can be multiple per activity.
- **A (Accountable)** — Owns the outcome and makes the final call. Exactly ONE per activity.
- **C (Consulted)** — Provides input before the activity happens. Two-way communication.
- **I (Informed)** — Notified after the activity completes. One-way communication.

### 4. Run conflict checks

Validate the matrix:
- **Single-A rule**: Every row has exactly one A. Zero A = no ownership. Multiple A = diluted ownership.
- **No orphan tasks**: Every row has at least one R. An activity with no one Responsible won't get done.
- **A without R**: If A has no R assigned, the Accountable person is also implicitly Responsible.
- **Overloaded roles**: If one role is R or A on >60% of rows, they're a bottleneck.
- **No empty columns**: A role with no assignments shouldn't be in the matrix.

### 5. Validate with stakeholders

Walk through the matrix with:
- Each Accountable person (do they accept ownership?)
- Each Responsible person (do they have capacity?)
- Sponsors (does governance align with org structure?)

## Pitfalls

1. **Multiple Accountable** — The most common error. "Co-accountable" means no one is accountable. Force a single A.
2. **Confusing R and A** — Responsible does the work; Accountable approves it. The CEO is rarely R but often A for strategic decisions.
3. **Too granular** — A 200-row RACI is unreadable. Group related tasks or use hierarchical RACIs.
4. **Static document** — A RACI written at project start and never updated becomes fiction. Review at each phase boundary.

## Verification

- [ ] Every row has exactly one A
- [ ] Every row has at least one R
- [ ] No role column is entirely empty
- [ ] No single role is A on more than 50% of rows
- [ ] Matrix has been validated with all Accountable persons

## BABOK Reference

Derived from BABOK v3 Technique 10.36 (RACI Matrix) and PMI PMBOK responsibility assignment patterns.
