ALTER TABLE events DROP CONSTRAINT events_status_check;
ALTER TABLE events ADD CONSTRAINT events_status_check CHECK(status IN ('DRAFT','PUBLISHING','PUBLISHED','UPDATING'));
CREATE TABLE event_revisions(id UUID PRIMARY KEY,event_id UUID NOT NULL REFERENCES events(id),payload JSONB NOT NULL,status VARCHAR(20) NOT NULL CHECK(status IN ('PENDING','APPLIED','REJECTED')),error VARCHAR(500),created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE UNIQUE INDEX idx_event_revision_pending ON event_revisions(event_id) WHERE status='PENDING';
