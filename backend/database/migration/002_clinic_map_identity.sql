USE veterinary_dental_care;
ALTER TABLE clinics
ADD COLUMN osm_type VARCHAR(10) NULL,
    ADD COLUMN osm_id BIGINT NULL,
    ADD CONSTRAINT uq_clinic_osm_identity UNIQUE (osm_type, osm_id),
    ADD CONSTRAINT chk_clinic_osm_identity CHECK (
        (
            osm_type IS NULL
            AND osm_id IS NULL
        )
        OR (
            osm_type IS NOT NULL
            AND osm_type IN ('node', 'way', 'relation')
            AND osm_id IS NOT NULL
            AND osm_id > 0
        )
    );
SHOW COLUMNS
FROM clinics LIKE 'osm%';