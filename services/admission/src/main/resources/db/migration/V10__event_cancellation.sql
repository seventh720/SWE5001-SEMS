ALTER TABLE sales DROP CONSTRAINT sales_state_check;
ALTER TABLE sales ADD CONSTRAINT sales_state_check CHECK(state IN ('DRAFT','ACTIVE','PAUSED','CANCELLED'));
CREATE TABLE event_cancellation_receipts (
 event_id UUID PRIMARY KEY REFERENCES sales(event_id), operation_id UUID UNIQUE NOT NULL,
 reason VARCHAR(500) NOT NULL, completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE bookings ADD COLUMN event_cancellation_reason VARCHAR(500);
