USE veterinary_dental_care;
-- Recommendation saved with the consultation, including drafts.
ALTER TABLE consultations
ADD COLUMN followup_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN followup_recommended_date DATE NULL,
    ADD COLUMN followup_reason TEXT NULL,
    ADD COLUMN followup_instructions TEXT NULL;
-- Follow-up task created when the consultation is finalized.
-- A recommended date does not represent a booked appointment.
ALTER TABLE followup_care
MODIFY COLUMN followup_date DATETIME NULL,
    ADD COLUMN recommended_date DATE NULL,
    ADD COLUMN reason TEXT NULL,
    ADD COLUMN care_instructions TEXT NULL;