CREATE TABLE notifications (
 id UUID PRIMARY KEY,
 user_id UUID NOT NULL,
 dedup_key TEXT NOT NULL,
 kind VARCHAR(40) NOT NULL,
 title VARCHAR(250) NOT NULL,
 message TEXT NOT NULL,
 link TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 read_at TIMESTAMPTZ,
 UNIQUE(user_id,dedup_key)
);
CREATE INDEX idx_notifications_user_created ON notifications(user_id,created_at DESC,id);
CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE read_at IS NULL;
