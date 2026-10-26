USE veterinary_dental_care;
CREATE TABLE treatment_progress (
    treatment_id INT PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'planned',
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    completion_consultation_id INT NULL,
    cancellation_reason TEXT NULL,
    updated_by_user_id INT NULL,
    updated_at DATETIME NULL,
    version INT NOT NULL DEFAULT 1,
    CONSTRAINT fk_progress_treatment FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id),
    CONSTRAINT fk_progress_completion_consultation FOREIGN KEY (completion_consultation_id) REFERENCES consultations(consultation_id),
    CONSTRAINT fk_progress_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES users(user_id),
    CONSTRAINT chk_treatment_progress_status CHECK (
        status IN (
            'planned',
            'in_progress',
            'completed',
            'cancelled'
        )
    )
);
-- Initialize tracking for existing finalized treatment plans.
INSERT INTO treatment_progress (treatment_id, status)
SELECT treatment.treatment_id,
    'planned'
FROM treatments AS treatment
    JOIN consultations AS consultation ON consultation.consultation_id = treatment.consultation_id
WHERE treatment.status = 'planned'
    AND consultation.status = 'completed';