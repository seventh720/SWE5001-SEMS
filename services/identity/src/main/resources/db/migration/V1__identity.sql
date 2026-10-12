CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_users_username UNIQUE (username),
    CONSTRAINT uk_users_email UNIQUE (email),
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE', 'LOCKED', 'DISABLED'))
);

CREATE TABLE roles (
    code VARCHAR(30) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL,
    role_code VARCHAR(30) NOT NULL,
    PRIMARY KEY (user_id, role_code),
    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_code) REFERENCES roles(code)
);

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_user_roles_role_code ON user_roles(role_code);

INSERT INTO roles (code, display_name) VALUES
    ('ATTENDEE', 'Attendee'),
    ('ORGANIZER', 'Event Organizer'),
    ('STAFF', 'Event Staff'),
    ('ADMIN', 'System Administrator');
