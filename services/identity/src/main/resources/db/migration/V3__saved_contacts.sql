ALTER TABLE booking_profiles ADD COLUMN id UUID;
UPDATE booking_profiles SET id=user_id;
ALTER TABLE booking_profiles ALTER COLUMN id SET NOT NULL;
ALTER TABLE booking_profiles DROP CONSTRAINT booking_profiles_pkey;
ALTER TABLE booking_profiles ADD PRIMARY KEY(id);
ALTER TABLE booking_profiles ADD COLUMN label VARCHAR(60) NOT NULL DEFAULT 'My details';
ALTER TABLE booking_profiles ADD COLUMN version BIGINT NOT NULL DEFAULT 0;
ALTER TABLE booking_profiles DROP COLUMN student_id;
CREATE INDEX booking_profiles_owner ON booking_profiles(user_id);
