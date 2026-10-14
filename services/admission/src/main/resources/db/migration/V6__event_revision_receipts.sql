CREATE TABLE event_revision_receipts(id UUID PRIMARY KEY,event_id UUID NOT NULL REFERENCES sales(event_id),payload JSONB NOT NULL);
