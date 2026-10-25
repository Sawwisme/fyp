USE veterinary_dental_care;
ALTER TABLE consultations
ADD COLUMN clinic_id INT NULL,
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'draft',
    ADD COLUMN examination_findings TEXT NULL,
    ADD COLUMN completed_at DATETIME NULL,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ADD COLUMN version INT NOT NULL DEFAULT 1;
-- Populate the clinic for existing consultation records.
UPDATE consultations AS consultation
    JOIN veterinarians AS vet ON vet.veterinarian_id = consultation.veterinarian_id
SET consultation.clinic_id = vet.clinic_id;
-- Preserve completed appointments as completed consultations.
UPDATE consultations AS consultation
    JOIN appointments AS appointment ON appointment.appointment_id = consultation.appointment_id
SET consultation.status = 'completed'
WHERE appointment.status = 'completed';
ALTER TABLE consultations
MODIFY COLUMN clinic_id INT NOT NULL,
    ADD CONSTRAINT fk_consultation_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    ADD INDEX ix_consultation_clinic_status (clinic_id, status),
    ADD INDEX ix_consultation_vet_date (veterinarian_id, consultation_date);
ALTER TABLE prescriptions
ADD COLUMN administration_route VARCHAR(50) NULL;