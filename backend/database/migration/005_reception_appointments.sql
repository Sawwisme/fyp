USE veterinary_dental_care;
ALTER TABLE appointments
ADD COLUMN appointment_source VARCHAR(20) NULL,
    ADD COLUMN created_by_user_id INT NULL,
    ADD CONSTRAINT fk_appointment_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(user_id);