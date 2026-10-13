CREATE TABLE booking_profiles (
 user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 real_name VARCHAR(100), email VARCHAR(254), phone VARCHAR(40), student_id VARCHAR(100), passport_number VARCHAR(100)
);
