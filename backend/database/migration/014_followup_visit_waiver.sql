USE veterinary_dental_care;
ALTER TABLE followup_review_decisions
ADD COLUMN previous_visit_required BOOLEAN NULL,
    ADD COLUMN visit_waiver_reason TEXT NULL;