USE veterinary_dental_care;
-- Clinic identity and location.
CREATE TABLE clinics (
    clinic_id INT AUTO_INCREMENT PRIMARY KEY,
    clinic_code VARCHAR(50) NOT NULL UNIQUE,
    clinic_name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NULL,
    phone_number VARCHAR(20) NULL,
    email VARCHAR(255) NULL,
    latitude DECIMAL(9, 6) NULL,
    longitude DECIMAL(9, 6) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_clinic_latitude CHECK (
        latitude IS NULL
        OR latitude BETWEEN -90 AND 90
    ),
    CONSTRAINT chk_clinic_longitude CHECK (
        longitude IS NULL
        OR longitude BETWEEN -180 AND 180
    ),
    CONSTRAINT chk_clinic_coordinates CHECK (
        (
            latitude IS NULL
            AND longitude IS NULL
        )
        OR (
            latitude IS NOT NULL
            AND longitude IS NOT NULL
        )
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
-- Weekly opening periods.
-- weekday: 0 = Monday, 1 = Tuesday, ... 6 = Sunday.
-- Multiple periods allow a lunch break, e.g. 09:00–12:00 and 14:00–17:00.
CREATE TABLE clinic_working_hours (
    clinic_working_hour_id INT AUTO_INCREMENT PRIMARY KEY,
    clinic_id INT NOT NULL,
    weekday TINYINT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    CONSTRAINT fk_working_hours_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    CONSTRAINT uq_clinic_weekday_start UNIQUE (clinic_id, weekday, start_time),
    CONSTRAINT chk_clinic_weekday CHECK (
        weekday BETWEEN 0 AND 6
    ),
    CONSTRAINT chk_clinic_working_period CHECK (
        start_time >= '00:00:00'
        AND end_time < '24:00:00'
        AND end_time > start_time
    )
) ENGINE = InnoDB;
-- Keep the existing clinic_name columns during the transition.
ALTER TABLE clinic_administrators
ADD COLUMN clinic_id INT NULL,
    ADD COLUMN membership_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ADD CONSTRAINT fk_admin_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id);
ALTER TABLE veterinarians
ADD COLUMN clinic_id INT NULL,
    ADD CONSTRAINT fk_veterinarian_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id);
-- Create the existing clinic. Location and hours will be entered later.
INSERT INTO clinics (
        clinic_code,
        clinic_name,
        status
    )
VALUES (
        'CLINIC-A',
        'ClinicA',
        'active'
    );
-- Link the existing administrator confirmed in your query results.
UPDATE clinic_administrators AS administrator
    JOIN clinics AS clinic ON clinic.clinic_code = 'CLINIC-A'
SET administrator.clinic_id = clinic.clinic_id,
    administrator.membership_status = 'approved'
WHERE administrator.clinic_administrator_id = 1
    AND administrator.clinic_name = 'ClinicA';
-- Link the existing veterinarian confirmed in your query results.
UPDATE veterinarians AS veterinarian
    JOIN clinics AS clinic ON clinic.clinic_code = 'CLINIC-A'
SET veterinarian.clinic_id = clinic.clinic_id
WHERE veterinarian.veterinarian_id = 1
    AND veterinarian.clinic_name = 'ClinicA';
-- Verification.
SELECT clinic_id,
    clinic_code,
    clinic_name
FROM clinics;
SELECT clinic_administrator_id,
    clinic_id,
    membership_status
FROM clinic_administrators;
SELECT veterinarian_id,
    clinic_id
FROM veterinarians;
SELECT 'unlinked_administrators' AS record_type,
    COUNT(*) AS total
FROM clinic_administrators
WHERE clinic_id IS NULL
UNION ALL
SELECT 'unlinked_veterinarians',
    COUNT(*)
FROM veterinarians
WHERE clinic_id IS NULL;