-- Maintenance connections can write memberships without the application's
-- search_path. Resolve notification tables in the owning schema for all callers.
ALTER FUNCTION identity.notify_membership_change() SET search_path = identity, pg_temp;
