USE veterinary_dental_care;
-- Requirements saved while drafting the consultation.
ALTER TABLE consultations
ADD COLUMN followup_photos_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN followup_photo_instructions TEXT NULL,
    ADD COLUMN followup_visit_required BOOLEAN NOT NULL DEFAULT FALSE;
-- Requirements copied into the finalized follow-up task.
ALTER TABLE followup_care
ADD COLUMN photos_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN photo_instructions TEXT NULL,
    ADD COLUMN visit_required BOOLEAN NOT NULL DEFAULT FALSE;
-- One owner update, optionally containing several images.
CREATE TABLE followup_submissions (
    submission_id INT AUTO_INCREMENT PRIMARY KEY,
    followup_care_id INT NOT NULL,
    pet_owner_id INT NOT NULL,
    owner_comment TEXT NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_status VARCHAR(30) NOT NULL DEFAULT 'submitted',
    veterinarian_comment TEXT NULL,
    reviewed_by_veterinarian_id INT NULL,
    reviewed_at DATETIME NULL,
    CONSTRAINT fk_submission_followup FOREIGN KEY (followup_care_id) REFERENCES followup_care(followup_care_id),
    CONSTRAINT fk_submission_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id),
    CONSTRAINT fk_submission_reviewer FOREIGN KEY (reviewed_by_veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT chk_submission_review_status CHECK (
        review_status IN (
            'submitted',
            'reviewed',
            'more_requested'
        )
    ),
    INDEX ix_submission_followup_date (followup_care_id, submitted_at),
    INDEX ix_submission_owner_date (pet_owner_id, submitted_at)
);
-- Preserve existing images; new images belong to a submission.
ALTER TABLE followup_images
ADD COLUMN submission_id INT NULL,
    ADD CONSTRAINT fk_followup_image_submission FOREIGN KEY (submission_id) REFERENCES followup_submissions(submission_id);