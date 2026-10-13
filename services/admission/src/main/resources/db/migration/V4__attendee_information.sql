ALTER TABLE bookings ADD attendee_info JSONB NOT NULL DEFAULT '{}', ADD custom_field_label VARCHAR(100);
