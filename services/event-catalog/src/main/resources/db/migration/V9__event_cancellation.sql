ALTER TABLE events DROP CONSTRAINT events_status_check;
ALTER TABLE events ADD CONSTRAINT events_status_check CHECK(status IN ('DRAFT','PUBLISHING','PUBLISHED','UPDATING','PAUSED','CANCELLING','CANCELLED'));
ALTER TABLE events ADD COLUMN cancellation_reason VARCHAR(500);
CREATE TABLE event_cancellations (
 event_id UUID PRIMARY KEY REFERENCES events(id), operation_id UUID UNIQUE NOT NULL,
 requested_version BIGINT NOT NULL, reason VARCHAR(500) NOT NULL,
 completed_at TIMESTAMPTZ, last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
