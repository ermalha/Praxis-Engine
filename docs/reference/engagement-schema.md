# Engagement Schema Reference

All models are defined in `src/praxis/engagement/models.py` using Pydantic v2
with `extra="forbid"`. Container models carry `schema_version: Literal[1] = 1`.

## GlossaryTerm

| Field        | Type            | Default | Notes                       |
| ------------ | --------------- | ------- | --------------------------- |
| `term`       | `str`           | —       | The canonical term          |
| `definition` | `str`           | —       | Plain-text definition       |
| `synonyms`   | `list[str]`     | `[]`    | Alternative names           |
| `notes`      | `str \| None`   | `None`  | Free-form Markdown          |
| `sources`    | `list[str]`     | `[]`    | Where the term was sourced  |
| `created_at` | `datetime`      | —       | UTC-aware                   |
| `updated_at` | `datetime`      | —       | UTC-aware                   |

## Stakeholder

| Field                | Type                                    | Default             |
| -------------------- | --------------------------------------- | ------------------- |
| `id`                 | `str`                                   | —                   |
| `name`               | `str`                                   | —                   |
| `role`               | `str`                                   | —                   |
| `organization`       | `str \| None`                           | `None`              |
| `expertise`          | `list[str]`                             | `[]`                |
| `decision_authority` | `list[str]`                             | `[]`                |
| `consult_on`         | `list[str]`                             | `[]`                |
| `contact_preference` | `ContactChannel`                        | `ContactChannel.EMAIL` |
| `contact_handle`     | `str \| None`                           | `None`              |
| `notes`              | `str \| None`                           | `None`              |
| `influence`          | `Literal["low","medium","high"]`        | `"medium"`          |
| `interest`           | `Literal["low","medium","high"]`        | `"medium"`          |
| `created_at`         | `datetime`                              | —                   |
| `updated_at`         | `datetime`                              | —                   |

## Decision (ADR)

| Field            | Type                                                        | Default      |
| ---------------- | ----------------------------------------------------------- | ------------ |
| `id`             | `str`                                                       | —            |
| `title`          | `str`                                                       | —            |
| `status`         | `Literal["proposed","accepted","deprecated","superseded"]`  | `"proposed"` |
| `context`        | `str`                                                       | —            |
| `decision`       | `str`                                                       | —            |
| `consequences`   | `str`                                                       | —            |
| `alternatives`   | `list[str]`                                                 | `[]`         |
| `superseded_by`  | `str \| None`                                               | `None`       |
| `decided_by`     | `list[str]`                                                 | `[]`         |
| `created_at`     | `datetime`                                                  | —            |
| `updated_at`     | `datetime`                                                  | —            |

## OpenQuestion

| Field                  | Type                                                  | Default      |
| ---------------------- | ----------------------------------------------------- | ------------ |
| `id`                   | `str`                                                 | —            |
| `question`             | `str`                                                 | —            |
| `why_it_matters`       | `str`                                                 | —            |
| `candidate_answerers`  | `list[str]`                                           | `[]`         |
| `status`               | `Literal["open","asked","answered","withdrawn"]`      | `"open"`     |
| `answer`               | `str \| None`                                         | `None`       |
| `blocks`               | `list[str]`                                           | `[]`         |
| `priority`             | `Literal["low","medium","high","critical"]`           | `"medium"`   |
| `asked_at`             | `datetime \| None`                                    | `None`       |
| `answered_at`          | `datetime \| None`                                    | `None`       |
| `created_at`           | `datetime`                                            | —            |
| `updated_at`           | `datetime`                                            | —            |

## System

| Field                | Type                                                    | Default    |
| -------------------- | ------------------------------------------------------- | ---------- |
| `id`                 | `str`                                                   | —          |
| `name`               | `str`                                                   | —          |
| `kind`               | `str`                                                   | —          |
| `owner`              | `str \| None`                                           | `None`     |
| `status`             | `Literal["live","planned","deprecated","retired"]`      | `"live"`   |
| `description`        | `str \| None`                                           | `None`     |
| `tech_stack`         | `list[str]`                                             | `[]`       |
| `integrations_with`  | `list[str]`                                             | `[]`       |
| `notes`              | `str \| None`                                           | `None`     |
| `created_at`         | `datetime`                                              | —          |
| `updated_at`         | `datetime`                                              | —          |

## Risk

| Field        | Type                                                                       | Default    |
| ------------ | -------------------------------------------------------------------------- | ---------- |
| `id`         | `str`                                                                      | —          |
| `title`      | `str`                                                                      | —          |
| `description`| `str`                                                                      | —          |
| `likelihood` | `Literal["low","medium","high"]`                                           | —          |
| `impact`     | `Literal["low","medium","high"]`                                           | —          |
| `mitigation` | `str \| None`                                                              | `None`     |
| `owner`      | `str \| None`                                                              | `None`     |
| `status`     | `Literal["open","mitigated","accepted","transferred","closed"]`            | `"open"`   |
| `created_at` | `datetime`                                                                 | —          |
| `updated_at` | `datetime`                                                                 | —          |

## Assumption

| Field               | Type              | Default  |
| ------------------- | ----------------- | -------- |
| `id`                | `str`             | —        |
| `statement`         | `str`             | —        |
| `rationale`         | `str \| None`     | `None`   |
| `validated`         | `bool`            | `False`  |
| `validation_method` | `str \| None`     | `None`   |
| `invalidated_at`    | `datetime \| None`| `None`   |
| `created_at`        | `datetime`        | —        |

## Constraint

| Field             | Type                                                                         | Default |
| ----------------- | ---------------------------------------------------------------------------- | ------- |
| `id`              | `str`                                                                        | —       |
| `statement`       | `str`                                                                        | —       |
| `source`          | `str \| None`                                                                | `None`  |
| `constraint_type` | `Literal["technical","regulatory","business","schedule","budget","other"]`    | —       |
| `created_at`      | `datetime`                                                                   | —       |

## Milestone

| Field         | Type                                                                    | Default    |
| ------------- | ----------------------------------------------------------------------- | ---------- |
| `id`          | `str`                                                                   | —          |
| `title`       | `str`                                                                   | —          |
| `target_date` | `date`                                                                  | —          |
| `status`      | `Literal["future","in_progress","achieved","missed","cancelled"]`       | `"future"` |
| `notes`       | `str \| None`                                                           | `None`     |

## ContactChannel (enum)

`email`, `teams`, `slack`, `phone`, `in_person`, `other`
