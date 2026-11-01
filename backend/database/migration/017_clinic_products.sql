USE veterinary_dental_care;
ALTER TABLE products
ADD COLUMN clinic_id INT NULL
AFTER product_id,
    ADD CONSTRAINT fk_product_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id),
    ADD INDEX ix_product_clinic_status (
        clinic_id,
        status,
        product_id
    );