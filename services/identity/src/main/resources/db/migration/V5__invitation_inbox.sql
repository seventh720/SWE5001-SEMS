ALTER TABLE organization_invitations DROP CONSTRAINT organization_invitations_status_check;
ALTER TABLE organization_invitations ADD CONSTRAINT organization_invitations_status_check CHECK(status IN ('PENDING','ACCEPTED','REVOKED','DECLINED'));
