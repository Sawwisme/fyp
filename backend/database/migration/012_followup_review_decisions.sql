USE veterinary_dental_care;
CREATE TABLE followup_review_decisions (
    decision_id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    veterinarian_id INT NOT NULL,
    outcome VARCHAR(30) NOT NULL,
    veterinarian_comment TEXT NOT NULL,
    decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    previous_review_status VARCHAR(30) NOT NULL,
    previous_comment TEXT NULL,
    previous_reviewed_at DATETIME NULL,
    previous_reviewer_id INT NULL,
    CONSTRAINT fk_followup_decision_submission FOREIGN KEY (submission_id) REFERENCES followup_submissions(submission_id),
    CONSTRAINT fk_followup_decision_vet FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT fk_followup_decision_previous_vet FOREIGN KEY (previous_reviewer_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT chk_followup_decision_outcome CHECK (
        outcome IN (
            'complete',
            'request_update',
            'in_clinic'
        )
    ),
    INDEX ix_followup_decision_submission (submission_id, decision_id)
);