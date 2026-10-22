USE veterinary_dental_care;
ALTER TABLE pet_owners
MODIFY COLUMN user_id INT NULL,
    ADD COLUMN contact_name VARCHAR(150) NULL,
    ADD COLUMN contact_phone VARCHAR(20) NULL,
    ADD COLUMN contact_email VARCHAR(255) NULL,
    ADD CONSTRAINT chk_pet_owner_identity CHECK (
        user_id IS NOT NULL
        OR (
            contact_name IS NOT NULL
            AND contact_phone IS NOT NULL
        )
    );
CREATE TABLE clinic_owner_links (
    clinic_id INT NOT NULL,
    pet_owner_id INT NOT NULL,
    created_by_user_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (clinic_id, pet_owner_id),
    CONSTRAINT fk_clinic_owner_link_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    CONSTRAINT fk_clinic_owner_link_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id),
    CONSTRAINT fk_clinic_owner_link_creator FOREIGN KEY (created_by_user_id) REFERENCES users(user_id)
);