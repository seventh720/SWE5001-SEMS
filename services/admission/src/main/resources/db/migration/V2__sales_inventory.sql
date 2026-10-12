CREATE TABLE sales (
 event_id UUID PRIMARY KEY, organizer_id UUID NOT NULL,
 capacity INTEGER NOT NULL CHECK (capacity > 0), starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
 state VARCHAR(20) NOT NULL CHECK (state IN ('DRAFT','ACTIVE')),
 version BIGINT NOT NULL, activation_id UUID UNIQUE,
 CHECK (ends_at > starts_at)
);
CREATE TABLE ticket_types (
 id UUID PRIMARY KEY, event_id UUID NOT NULL REFERENCES sales(event_id),
 name VARCHAR(100) NOT NULL CHECK (length(trim(name)) > 0), quota INTEGER NOT NULL CHECK (quota > 0),
 reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0 AND reserved <= quota),
 opens_at TIMESTAMPTZ NOT NULL, closes_at TIMESTAMPTZ NOT NULL,
 UNIQUE (event_id, name), CHECK (closes_at > opens_at)
);
CREATE INDEX idx_ticket_types_event ON ticket_types(event_id);
