CREATE TABLE organizations (
 id UUID PRIMARY KEY, name VARCHAR(160) NOT NULL, slug VARCHAR(100) NOT NULL UNIQUE,
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUSPENDED')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE organization_memberships (
 organization_id UUID NOT NULL REFERENCES organizations(id), user_id UUID NOT NULL REFERENCES users(id),
 role VARCHAR(20) NOT NULL CHECK(role IN ('ORG_ADMIN','ORGANIZER','MEMBER')),
 status VARCHAR(20) NOT NULL CHECK(status IN ('ACTIVE','SUSPENDED','REMOVED')),
 version BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(organization_id,user_id)
);
CREATE INDEX idx_membership_user ON organization_memberships(user_id,status);
CREATE TABLE organization_invitations (
 id UUID PRIMARY KEY, organization_id UUID NOT NULL REFERENCES organizations(id), user_id UUID NOT NULL REFERENCES users(id),
 role VARCHAR(20) NOT NULL CHECK(role IN ('ORG_ADMIN','ORGANIZER','MEMBER')),
 token_hash VARCHAR(64) NOT NULL UNIQUE, status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED','REVOKED')),
 expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
