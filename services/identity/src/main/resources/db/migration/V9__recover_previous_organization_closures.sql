-- Recover unfinished events for organizations closed by the earlier synchronous implementation.
-- Temporary suspension has no approved CLOSE request and must remain reversible.
INSERT INTO organization_closures(organization_id,operation_id,target_status,created_at)
SELECT o.id,gen_random_uuid(),o.status,
 COALESCE((SELECT min(r.reviewed_at) FROM organization_requests r WHERE r.organization_id=o.id AND r.kind='CLOSE' AND r.status='APPROVED'),CURRENT_TIMESTAMP)
FROM organizations o
WHERE (o.status='DELETED' OR (o.status='SUSPENDED' AND EXISTS(
 SELECT 1 FROM organization_requests r WHERE r.organization_id=o.id AND r.kind='CLOSE' AND r.status='APPROVED')))
AND NOT EXISTS(SELECT 1 FROM organization_closures c WHERE c.organization_id=o.id);
UPDATE organizations o SET status='CLOSING',version=version+1
WHERE o.status IN ('SUSPENDED','DELETED') AND EXISTS(
 SELECT 1 FROM organization_closures c WHERE c.organization_id=o.id AND c.completed_at IS NULL);
