ALTER TABLE organizations DROP CONSTRAINT organizations_status_check;
ALTER TABLE organizations ADD CONSTRAINT organizations_status_check CHECK(status IN ('ACTIVE','SUSPENDED','DELETED'));
ALTER TABLE organizations ADD COLUMN version BIGINT NOT NULL DEFAULT 0;
CREATE TABLE organization_requests (
 id UUID PRIMARY KEY, organization_id UUID NOT NULL REFERENCES organizations(id),
 requester_id UUID NOT NULL REFERENCES users(id),
 kind VARCHAR(20) NOT NULL CHECK(kind IN ('UPDATE','CLOSE')),
 name VARCHAR(160), slug VARCHAR(100), reason VARCHAR(2000) NOT NULL,
 base_version BIGINT NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
 reviewer_id UUID REFERENCES users(id), review_note VARCHAR(2000),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX one_pending_organization_request ON organization_requests(organization_id) WHERE status='PENDING';
ALTER TABLE membership_notifications ADD COLUMN link TEXT;
ALTER TABLE membership_notifications ADD COLUMN kind VARCHAR(40) NOT NULL DEFAULT 'ORGANIZATION_MEMBERSHIP';
