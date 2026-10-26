USE veterinary_dental_care;
ALTER TABLE appointments
ADD COLUMN planned_treatment_id INT NULL,
    ADD COLUMN followup_care_id INT NULL,
    ADD CONSTRAINT fk_appointment_treatment_plan FOREIGN KEY (planned_treatment_id) REFERENCES treatment_progress(treatment_id),
    ADD CONSTRAINT fk_appointment_followup FOREIGN KEY (followup_care_id) REFERENCES followup_care(followup_care_id),
    ADD CONSTRAINT chk_appointment_return_visit CHECK (
        planned_treatment_id IS NULL
        OR followup_care_id IS NULL
    ),
    ADD INDEX ix_appointment_treatment_status (planned_treatment_id, status),
    ADD INDEX ix_appointment_followup_status (followup_care_id, status);