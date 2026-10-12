ALTER TABLE events DROP CONSTRAINT events_status_check;
ALTER TABLE events ADD CONSTRAINT events_status_check CHECK (status IN ('DRAFT','PUBLISHING','PUBLISHED'));
ALTER TABLE events ADD COLUMN sales_configured BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE events ADD COLUMN publication_id UUID;
ALTER TABLE events ADD COLUMN publication_version BIGINT;
ALTER TABLE events ADD COLUMN ticket_version BIGINT;
ALTER TABLE events ADD COLUMN publication_error VARCHAR(500);
CREATE INDEX idx_events_publication ON events(status);
