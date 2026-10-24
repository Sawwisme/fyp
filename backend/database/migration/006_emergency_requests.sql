USE veterinary_dental_care;
ALTER TABLE emergency_appointments
MODIFY COLUMN appointment_id INT NULL,
    ADD COLUMN clinic_id INT NULL,
    ADD COLUMN pet_owner_id INT NULL,
    ADD COLUMN pet_id INT NULL,
    ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN reviewed_at DATETIME NULL,
    ADD COLUMN rejection_reason TEXT NULL;
-- Preserve clinic and ownership information for existing records.
UPDATE emergency_appointments AS emergency
    JOIN appointments AS appointment ON appointment.appointment_id = emergency.appointment_id
    JOIN time_slots AS slot ON slot.time_slot_id = appointment.time_slot_id
    JOIN schedules AS schedule ON schedule.schedule_id = slot.schedule_id
    JOIN veterinarians AS vet ON vet.veterinarian_id = schedule.veterinarian_id
SET emergency.clinic_id = vet.clinic_id,
    emergency.pet_owner_id = appointment.pet_owner_id,
    emergency.pet_id = appointment.pet_id,
    emergency.created_at = appointment.created_at;
ALTER TABLE emergency_appointments
MODIFY COLUMN clinic_id INT NOT NULL,
    MODIFY COLUMN pet_owner_id INT NOT NULL,
    MODIFY COLUMN pet_id INT NOT NULL,
    ADD CONSTRAINT fk_emergency_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    ADD CONSTRAINT fk_emergency_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id),
    ADD CONSTRAINT fk_emergency_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    ADD INDEX ix_emergency_clinic_status_created (clinic_id, approval_status, created_at),
    ADD INDEX ix_emergency_owner_created (pet_owner_id, created_at);