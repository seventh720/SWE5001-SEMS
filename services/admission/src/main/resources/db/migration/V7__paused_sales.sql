ALTER TABLE sales DROP CONSTRAINT sales_state_check;
ALTER TABLE sales ADD CONSTRAINT sales_state_check CHECK(state IN ('DRAFT','ACTIVE','PAUSED'));
ALTER TABLE ticket_types DROP CONSTRAINT ticket_types_event_id_name_key;
ALTER TABLE ticket_types ADD CONSTRAINT ticket_types_event_id_name_key UNIQUE(event_id,name) DEFERRABLE INITIALLY DEFERRED;
