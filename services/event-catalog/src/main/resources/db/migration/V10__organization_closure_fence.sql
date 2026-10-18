CREATE TABLE organization_closures (
 organization_id UUID PRIMARY KEY, operation_id UUID UNIQUE NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Fence new work locally even if a request passed Identity authorization before closure.
-- Pending publication/revision may finish; the closure worker cancels their resulting events.
CREATE FUNCTION guard_closed_organization() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('organization:'||NEW.organization_id::text,0));
 IF EXISTS(SELECT 1 FROM organization_closures WHERE organization_id=NEW.organization_id) THEN
  IF TG_OP='INSERT' THEN
   RAISE EXCEPTION 'Organization is closing or closed' USING ERRCODE='23514', CONSTRAINT='organization_closure_fence';
  END IF;
  IF OLD.status NOT IN ('PUBLISHING','UPDATING','CANCELLING') AND NOT (OLD.status IN ('PUBLISHED','PAUSED') AND NEW.status='CANCELLING') THEN
   RAISE EXCEPTION 'Organization is closing or closed' USING ERRCODE='23514', CONSTRAINT='organization_closure_fence';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_closed_organization BEFORE INSERT OR UPDATE ON events FOR EACH ROW EXECUTE FUNCTION guard_closed_organization();
