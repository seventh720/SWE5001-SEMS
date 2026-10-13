CREATE TABLE pre_registrations (
 user_id UUID NOT NULL, event_id UUID NOT NULL REFERENCES sales(event_id), ticket_type_id UUID NOT NULL REFERENCES ticket_types(id),
 quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 10), attendee_info JSONB NOT NULL,
 event_title VARCHAR(200) NOT NULL, event_location VARCHAR(500) NOT NULL, custom_field_label VARCHAR(100),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,event_id)
);
CREATE INDEX idx_pre_registrations_user ON pre_registrations(user_id,updated_at DESC);
