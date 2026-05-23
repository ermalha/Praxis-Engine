-- D-058 — promote workitems.assignee to a real indexed column.
--
-- Before this migration, assignee lived only inside ``payload_json`` and was
-- filtered in Python *after* SQL applied LIMIT, which silently under-reported
-- results when the first N rows ORDER BY created_at DESC happened to be of
-- another assignee.
--
-- The migration is strictly additive: the new column starts NULL, gets
-- backfilled from the existing JSON, and is then used by an index. Existing
-- callers that read assignee from the dataclass / payload still work because
-- the field on the WorkItem model is unchanged.

ALTER TABLE workitems ADD COLUMN assignee TEXT;

UPDATE workitems
SET assignee = json_extract(payload_json, '$.assignee')
WHERE assignee IS NULL;

CREATE INDEX idx_workitems_assignee ON workitems(assignee, status);
