CREATE TABLE event_notification_outbox (
 id UUID PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 delivered_at TIMESTAMPTZ
);
CREATE INDEX idx_event_notification_pending ON event_notification_outbox(created_at) WHERE delivered_at IS NULL;
CREATE FUNCTION queue_event_notification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status IN ('PUBLISHED','PAUSED') AND OLD.status IN ('PUBLISHED','PAUSED')
 AND (NEW.title,NEW.description,NEW.location,NEW.starts_at,NEW.ends_at,NEW.capacity,NEW.visibility,NEW.status,NEW.category,NEW.card_theme)
 IS DISTINCT FROM (OLD.title,OLD.description,OLD.location,OLD.starts_at,OLD.ends_at,OLD.capacity,OLD.visibility,OLD.status,OLD.category,OLD.card_theme) THEN
 INSERT INTO event_notification_outbox(id,payload) VALUES(gen_random_uuid(),jsonb_build_object(
 'eventId',NEW.id,'title',NEW.title,'location',NEW.location,'startsAt',NEW.starts_at,
 'endsAt',NEW.ends_at,'status',NEW.status,'visibility',NEW.visibility));
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER event_notification_after_update AFTER UPDATE ON events FOR EACH ROW EXECUTE FUNCTION queue_event_notification();
