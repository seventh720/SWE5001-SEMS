CREATE TABLE bookings (
 id UUID PRIMARY KEY, user_id UUID NOT NULL, request_key UUID NOT NULL,
 event_id UUID NOT NULL REFERENCES sales(event_id), ticket_type_id UUID NOT NULL REFERENCES ticket_types(id),
 quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 10),
 status VARCHAR(20) NOT NULL CHECK (status IN ('CONFIRMED','CANCELLED')),
 event_title VARCHAR(200) NOT NULL, event_location VARCHAR(500) NOT NULL,
 starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL, ticket_name VARCHAR(100) NOT NULL,
 amount INTEGER NOT NULL DEFAULT 0 CHECK (amount = 0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, cancelled_at TIMESTAMPTZ,
 UNIQUE(user_id, request_key), CHECK ((status='CANCELLED') = (cancelled_at IS NOT NULL))
);
CREATE INDEX idx_bookings_user ON bookings(user_id, created_at DESC, id DESC);
CREATE TABLE tickets (
 id UUID PRIMARY KEY, booking_id UUID NOT NULL REFERENCES bookings(id),
 credential VARCHAR(64) NOT NULL UNIQUE,
 state VARCHAR(20) NOT NULL CHECK (state IN ('VALID','CHECKED_IN','CANCELLED'))
);
CREATE INDEX idx_tickets_booking ON tickets(booking_id);
