CREATE TABLE events (
 id UUID PRIMARY KEY,
 organizer_id UUID NOT NULL,
 title VARCHAR(200) NOT NULL,
 description VARCHAR(10000) NOT NULL,
 location VARCHAR(500) NOT NULL,
 starts_at TIMESTAMPTZ NOT NULL,
 ends_at TIMESTAMPTZ NOT NULL,
 capacity INTEGER NOT NULL CHECK (capacity > 0),
 status VARCHAR(20) NOT NULL CHECK (status IN ('DRAFT')),
 version BIGINT NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 CHECK (ends_at > starts_at)
);
CREATE INDEX idx_events_owner_created ON events (organizer_id, created_at DESC, id DESC);
