ALTER TABLE sales ADD COLUMN organization_id UUID;
CREATE TABLE event_staff_assignments (
 event_id UUID NOT NULL REFERENCES sales(event_id), user_id UUID NOT NULL, assigned_by UUID NOT NULL,
 active BOOLEAN NOT NULL DEFAULT true, assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(event_id,user_id)
);
CREATE INDEX idx_staff_user ON event_staff_assignments(user_id,active);
ALTER TABLE tickets ADD COLUMN checked_in_at TIMESTAMPTZ;
ALTER TABLE tickets ADD COLUMN checked_in_by UUID;
