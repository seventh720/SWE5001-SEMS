ALTER TABLE organizations DROP CONSTRAINT organizations_status_check;
ALTER TABLE organizations ADD CONSTRAINT organizations_status_check CHECK(status IN ('ACTIVE','CLOSING','SUSPENDED','DELETED'));
CREATE TABLE organization_closures (
 organization_id UUID PRIMARY KEY REFERENCES organizations(id), operation_id UUID UNIQUE NOT NULL,
 target_status VARCHAR(20) NOT NULL CHECK(target_status IN ('SUSPENDED','DELETED')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TIMESTAMPTZ
);
