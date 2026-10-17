-- Trigger correctness must not depend on the caller's search_path (including recovery tools).
ALTER FUNCTION guard_closed_organization() SET search_path = catalog, pg_temp;
