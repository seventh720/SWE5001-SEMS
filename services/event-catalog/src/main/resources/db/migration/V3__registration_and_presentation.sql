ALTER TABLE events
 ADD category VARCHAR(20) NOT NULL DEFAULT 'GENERAL' CHECK (category IN ('GENERAL','TECH','EDUCATION','MUSIC','SPORT','ART','COMMUNITY')),
 ADD card_theme VARCHAR(20) NOT NULL DEFAULT 'LILAC' CHECK (card_theme IN ('LILAC','LIME','PEACH','SKY')),
 ADD registration_requirements JSONB NOT NULL DEFAULT '{"realName":false,"email":false,"phone":false,"studentId":false,"passport":false,"customFieldLabel":null}';
CREATE INDEX idx_events_category_start ON events(category,starts_at,id) WHERE status='PUBLISHED';
