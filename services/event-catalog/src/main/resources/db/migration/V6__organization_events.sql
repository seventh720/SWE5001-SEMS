ALTER TABLE events ADD COLUMN organization_id UUID;
ALTER TABLE events ADD COLUMN visibility VARCHAR(30) NOT NULL DEFAULT 'PUBLIC' CHECK(visibility IN ('PUBLIC','ORGANIZATION_ONLY'));
CREATE INDEX idx_events_org ON events(organization_id,created_at DESC,id);
-- Existing events remain inaccessible to management until the explicit owner mapping migration runs.
