USE veterinary_dental_care;
ALTER TABLE treatment_progress
ADD COLUMN start_consultation_id INT NULL,
    ADD COLUMN start_notes TEXT NULL,
    ADD CONSTRAINT fk_progress_start_consultation FOREIGN KEY (start_consultation_id) REFERENCES consultations(consultation_id);