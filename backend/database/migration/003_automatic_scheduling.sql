USE veterinary_dental_care;
CREATE TABLE automatic_schedule_rules (
    automatic_schedule_rule_id INT AUTO_INCREMENT PRIMARY KEY,
    veterinarian_id INT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    slot_minutes INT NOT NULL DEFAULT 30,
    days_ahead INT NOT NULL DEFAULT 30,
    last_run_at DATETIME NULL,
    last_error VARCHAR(1000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_automatic_schedule_vet UNIQUE (veterinarian_id),
    CONSTRAINT fk_automatic_schedule_vet FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT chk_automatic_schedule_slot_minutes CHECK (
        slot_minutes BETWEEN 5 AND 120
    ),
    CONSTRAINT chk_automatic_schedule_days CHECK (
        days_ahead BETWEEN 7 AND 30
    ),
    INDEX idx_automatic_schedule_enabled (enabled)
);