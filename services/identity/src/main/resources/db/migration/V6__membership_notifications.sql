CREATE TABLE membership_notifications (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id UUID NOT NULL REFERENCES users(id),
 organization_id UUID NOT NULL REFERENCES organizations(id),
 title TEXT NOT NULL, message TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 read_at TIMESTAMPTZ
);
CREATE INDEX membership_notices_user_created ON membership_notifications(user_id,created_at DESC,id DESC);
CREATE INDEX membership_notices_unread ON membership_notifications(user_id) WHERE read_at IS NULL;

-- Capture all membership writers atomically, including administrator appointment
-- and invitation acceptance. Failed transactions and unchanged roles/statuses
-- cannot leave notifications behind. Historical assignments are not backfilled.
CREATE FUNCTION notify_membership_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE org_name TEXT; role_name TEXT; old_role_name TEXT; notice TEXT;
BEGIN
 IF TG_OP = 'UPDATE' THEN
  IF NEW.role IS NOT DISTINCT FROM OLD.role AND NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NEW; END IF;
 END IF;
 SELECT name INTO org_name FROM organizations WHERE id=NEW.organization_id;
 role_name := CASE NEW.role WHEN 'ORG_ADMIN' THEN 'Organization administrator' WHEN 'ORGANIZER' THEN 'Event organizer' ELSE 'Member' END;
 IF TG_OP = 'INSERT' THEN
  notice := 'You have been assigned as ' || role_name || ' in ' || org_name || '. Membership status: ' || lower(NEW.status) || '.';
 ELSE
  old_role_name := CASE OLD.role WHEN 'ORG_ADMIN' THEN 'Organization administrator' WHEN 'ORGANIZER' THEN 'Event organizer' ELSE 'Member' END;
  notice := 'Your membership in ' || org_name || ' changed from ' || old_role_name || ' (' || lower(OLD.status) || ') to ' || role_name || ' (' || lower(NEW.status) || ').';
 END IF;
 INSERT INTO membership_notifications(user_id,organization_id,title,message)
 VALUES(NEW.user_id,NEW.organization_id,'Organization access updated: ' || org_name,notice);
 RETURN NEW;
END;
$$;
CREATE TRIGGER membership_notification AFTER INSERT OR UPDATE OF role,status ON organization_memberships FOR EACH ROW EXECUTE FUNCTION notify_membership_change();
