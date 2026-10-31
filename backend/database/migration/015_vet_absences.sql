USE veterinary_dental_care;
CREATE TABLE veterinarian_absences (
    absence_id INT AUTO_INCREMENT PRIMARY KEY,
    clinic_id INT NOT NULL,
    veterinarian_id INT NOT NULL,
    absence_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by_user_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at DATETIME NULL,
    CONSTRAINT fk_absence_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    CONSTRAINT fk_absence_vet FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT fk_absence_creator FOREIGN KEY (created_by_user_id) REFERENCES users(user_id),
    CONSTRAINT chk_absence_times CHECK (end_time > start_time),
    CONSTRAINT chk_absence_status CHECK (status IN ('active', 'cancelled')),
    INDEX ix_absence_vet_date (veterinarian_id, absence_date, status)
);
CREATE TABLE absence_affected_appointments (
    affected_id INT AUTO_INCREMENT PRIMARY KEY,
    absence_id INT NOT NULL,
    appointment_id INT NOT NULL,
    original_time_slot_id INT NOT NULL,
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolution_note TEXT NULL,
    owner_agreement_note TEXT NULL,
    resolved_by_user_id INT NULL,
    resolved_at DATETIME NULL,
    CONSTRAINT fk_affected_absence FOREIGN KEY (absence_id) REFERENCES veterinarian_absences(absence_id),
    CONSTRAINT fk_affected_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    CONSTRAINT fk_affected_original_slot FOREIGN KEY (original_time_slot_id) REFERENCES time_slots(time_slot_id),
    CONSTRAINT fk_affected_resolver FOREIGN KEY (resolved_by_user_id) REFERENCES users(user_id),
    CONSTRAINT uq_absence_appointment UNIQUE (absence_id, appointment_id),
    CONSTRAINT chk_absence_resolution CHECK (
        resolution_status IN (
            'pending',
            'rescheduled',
            'reassigned',
            'cancelled',
            'no_change'
        )
    ),
    INDEX ix_affected_resolution (absence_id, resolution_status)
);