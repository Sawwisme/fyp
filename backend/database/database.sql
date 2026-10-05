-- Veterinary Dental Care System
CREATE DATABASE IF NOT EXISTS veterinary_dental_care CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE veterinary_dental_care;
-- ============================================================
-- 1. USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NULL,
    role VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB;
-- ============================================================
-- 2. PET OWNER
-- ============================================================
CREATE TABLE IF NOT EXISTS pet_owners (
    pet_owner_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    default_address VARCHAR(255) NULL,
    CONSTRAINT fk_pet_owner_user FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE = InnoDB;
-- ============================================================
-- 3. CLINIC ADMINISTRATOR
-- ============================================================
CREATE TABLE IF NOT EXISTS clinic_administrators (
    clinic_administrator_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    clinic_name VARCHAR(150) NOT NULL,
    CONSTRAINT fk_clinic_admin_user FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE = InnoDB;
-- ============================================================
-- 4. VETERINARIAN
-- Approved correction: qualification + years_experience
-- ============================================================
CREATE TABLE IF NOT EXISTS veterinarians (
    veterinarian_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    registration_number VARCHAR(50) NOT NULL UNIQUE,
    qualification VARCHAR(150) NULL,
    specialization VARCHAR(100) NULL,
    years_experience INT NULL,
    approval_status VARCHAR(20) NOT NULL,
    clinic_name VARCHAR(150) NULL,
    CONSTRAINT fk_veterinarian_user FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE = InnoDB;
-- ============================================================
-- 5. PET
-- Approved correction: colour + existing_dental_condition
-- ============================================================
CREATE TABLE IF NOT EXISTS pets (
    pet_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_owner_id INT NOT NULL,
    pet_name VARCHAR(100) NOT NULL,
    species VARCHAR(30) NOT NULL,
    breed VARCHAR(100) NULL,
    gender VARCHAR(20) NULL,
    date_of_birth DATE NULL,
    weight DECIMAL(5, 2) NULL,
    colour VARCHAR(50) NULL,
    existing_dental_condition TEXT NULL,
    notes TEXT NULL,
    CONSTRAINT fk_pet_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id)
) ENGINE = InnoDB;
-- ============================================================
-- 6. SCHEDULE
-- ============================================================
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id INT AUTO_INCREMENT PRIMARY KEY,
    veterinarian_id INT NOT NULL,
    schedule_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_schedule_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id)
) ENGINE = InnoDB;
-- ============================================================
-- 7. TIME SLOT
-- ============================================================
CREATE TABLE IF NOT EXISTS time_slots (
    time_slot_id INT AUTO_INCREMENT PRIMARY KEY,
    schedule_id INT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_time_slot_schedule FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id)
) ENGINE = InnoDB;
-- ============================================================
-- 8. APPOINTMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_owner_id INT NOT NULL,
    pet_id INT NOT NULL,
    veterinarian_id INT NULL,
    time_slot_id INT NOT NULL,
    appointment_type VARCHAR(30) NOT NULL,
    appointment_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appointment_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id),
    CONSTRAINT fk_appointment_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    CONSTRAINT fk_appointment_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT fk_appointment_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slots(time_slot_id)
) ENGINE = InnoDB;
-- ============================================================
-- 9. EMERGENCY APPOINTMENT
-- Approved correction: no duplicated ID/FK rows
-- ============================================================
CREATE TABLE IF NOT EXISTS emergency_appointments (
    emergency_appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NOT NULL UNIQUE,
    urgency_level VARCHAR(20) NOT NULL,
    emergency_reason TEXT NOT NULL,
    approval_status VARCHAR(20) NOT NULL,
    assigned_veterinarian_id INT NULL,
    approved_by INT NULL,
    CONSTRAINT fk_emergency_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    CONSTRAINT fk_emergency_veterinarian FOREIGN KEY (assigned_veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT fk_emergency_approved_by FOREIGN KEY (approved_by) REFERENCES clinic_administrators(clinic_administrator_id)
) ENGINE = InnoDB;
-- ============================================================
-- 10. CONSULTATION
-- ============================================================
CREATE TABLE IF NOT EXISTS consultations (
    consultation_id INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NOT NULL UNIQUE,
    pet_id INT NOT NULL,
    veterinarian_id INT NOT NULL,
    consultation_date DATETIME NOT NULL,
    consultation_information TEXT NULL,
    diagnosis TEXT NULL,
    notes TEXT NULL,
    CONSTRAINT fk_consultation_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    CONSTRAINT fk_consultation_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    CONSTRAINT fk_consultation_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id)
) ENGINE = InnoDB;
-- ============================================================
-- 11. DENTAL RECORD
-- ============================================================
CREATE TABLE IF NOT EXISTS dental_records (
    dental_record_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    veterinarian_id INT NULL,
    consultation_id INT NULL,
    record_date DATE NOT NULL,
    dental_condition TEXT NULL,
    notes TEXT NULL,
    CONSTRAINT fk_dental_record_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    CONSTRAINT fk_dental_record_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id),
    CONSTRAINT fk_dental_record_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id)
) ENGINE = InnoDB;
-- ============================================================
-- 12. PRESCRIPTION
-- Current report design: one row represents one medication.
-- ============================================================
CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id INT AUTO_INCREMENT PRIMARY KEY,
    consultation_id INT NOT NULL,
    veterinarian_id INT NOT NULL,
    medication_name VARCHAR(150) NOT NULL,
    dosage VARCHAR(100) NOT NULL,
    frequency VARCHAR(100) NULL,
    duration VARCHAR(100) NULL,
    instructions TEXT NULL,
    prescription_date DATE NOT NULL,
    CONSTRAINT fk_prescription_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id),
    CONSTRAINT fk_prescription_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id)
) ENGINE = InnoDB;
-- ============================================================
-- 13. FOLLOW-UP CARE
-- ============================================================
CREATE TABLE IF NOT EXISTS followup_care (
    followup_care_id INT AUTO_INCREMENT PRIMARY KEY,
    consultation_id INT NOT NULL,
    pet_id INT NOT NULL,
    veterinarian_id INT NOT NULL,
    followup_date DATETIME NOT NULL,
    assessment_information TEXT NULL,
    status VARCHAR(20) NOT NULL,
    notes TEXT NULL,
    CONSTRAINT fk_followup_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id),
    CONSTRAINT fk_followup_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    CONSTRAINT fk_followup_veterinarian FOREIGN KEY (veterinarian_id) REFERENCES veterinarians(veterinarian_id)
) ENGINE = InnoDB;
-- ============================================================
-- 14. FOLLOW-UP IMAGE
-- ============================================================
CREATE TABLE IF NOT EXISTS followup_images (
    followup_care_image_id INT AUTO_INCREMENT PRIMARY KEY,
    followup_care_id INT NOT NULL,
    image_url VARCHAR(255) NOT NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_followup_image_care FOREIGN KEY (followup_care_id) REFERENCES followup_care(followup_care_id)
) ENGINE = InnoDB;
-- ============================================================
-- 15. TREATMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS treatments (
    treatment_id INT AUTO_INCREMENT PRIMARY KEY,
    consultation_id INT NOT NULL,
    treatment_name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    treatment_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_treatment_consultation FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id)
) ENGINE = InnoDB;
-- ============================================================
-- 16. DENTAL IMAGE
-- ============================================================
CREATE TABLE IF NOT EXISTS dental_images (
    dental_image_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    uploaded_by INT NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dental_image_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id),
    CONSTRAINT fk_dental_image_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(user_id)
) ENGINE = InnoDB;
-- ============================================================
-- 17. AI ANALYSIS RESULT
-- Approved redesign for current multi-label model.
-- No single severity_level is used here.
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_analysis_results (
    analysis_id INT AUTO_INCREMENT PRIMARY KEY,
    dental_image_id INT NOT NULL,
    heatmap_url VARCHAR(500) NULL,
    segmentation_url VARCHAR(500) NULL,
    analysis_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(100) NULL,
    veterinarian_override VARCHAR(30) NULL,
    override_notes TEXT NULL,
    CONSTRAINT fk_ai_analysis_dental_image FOREIGN KEY (dental_image_id) REFERENCES dental_images(dental_image_id)
) ENGINE = InnoDB;
-- ============================================================
-- 18. AI ANALYSIS PREDICTION
-- New table for multi-label condition predictions.
-- Example rows: plaque, gingivitis, calculus, healthy
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_analysis_predictions (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id INT NOT NULL,
    condition_name VARCHAR(50) NOT NULL,
    confidence_score DECIMAL(6, 5) NOT NULL,
    predicted_positive BOOLEAN NOT NULL,
    supported BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_analysis_condition UNIQUE (analysis_id, condition_name),
    CONSTRAINT fk_prediction_analysis FOREIGN KEY (analysis_id) REFERENCES ai_analysis_results(analysis_id)
) ENGINE = InnoDB;
-- ============================================================
-- 19. CHATBOT CONVERSATION
-- ============================================================
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    conversation_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    pet_id INT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT fk_chat_conversation_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_chat_conversation_pet FOREIGN KEY (pet_id) REFERENCES pets(pet_id)
) ENGINE = InnoDB;
-- ============================================================
-- 20. CHATBOT MESSAGE
-- ============================================================
CREATE TABLE IF NOT EXISTS chatbot_messages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    sender_type VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_message_conversation FOREIGN KEY (conversation_id) REFERENCES chatbot_conversations(conversation_id)
) ENGINE = InnoDB;
-- ============================================================
-- 21. PRODUCT CATEGORY
-- ============================================================
CREATE TABLE IF NOT EXISTS product_categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB;
-- ============================================================
-- 22. PRODUCT
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    product_name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INT NOT NULL,
    image_url VARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_category FOREIGN KEY (category_id) REFERENCES product_categories(category_id)
) ENGINE = InnoDB;
-- ============================================================
-- 23. CART
-- ============================================================
CREATE TABLE IF NOT EXISTS carts (
    cart_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_owner_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cart_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id)
) ENGINE = InnoDB;
-- ============================================================
-- 24. CART ITEM
-- ============================================================
CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INT AUTO_INCREMENT PRIMARY KEY,
    cart_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    CONSTRAINT uq_cart_product UNIQUE (cart_id, product_id),
    CONSTRAINT fk_cart_item_cart FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
    CONSTRAINT fk_cart_item_product FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE = InnoDB;
-- ============================================================
-- 25. ORDER
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    pet_owner_id INT NOT NULL,
    order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipping_address VARCHAR(255) NOT NULL,
    shipping_method VARCHAR(50) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    shipping_fee DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    CONSTRAINT fk_order_owner FOREIGN KEY (pet_owner_id) REFERENCES pet_owners(pet_owner_id)
) ENGINE = InnoDB;
-- ============================================================
-- 26. ORDER ITEM
-- ============================================================
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_order_item_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_order_item_product FOREIGN KEY (product_id) REFERENCES products(product_id)
) ENGINE = InnoDB;
-- ============================================================
-- 27. PAYMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NULL,
    appointment_id INT NULL,
    payment_method VARCHAR(30) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_date DATETIME NULL,
    gateway_reference VARCHAR(100) NULL UNIQUE,
    receipt_number VARCHAR(50) NULL UNIQUE,
    CONSTRAINT fk_payment_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_payment_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
) ENGINE = InnoDB;
-- ============================================================
-- 28. TRANSACTION
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    order_id INT NULL,
    payment_id INT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_status VARCHAR(20) NOT NULL,
    transaction_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transaction_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_transaction_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_transaction_payment FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
) ENGINE = InnoDB;
-- ============================================================
-- 29. REFUND
-- ============================================================
CREATE TABLE IF NOT EXISTS refunds (
    refund_id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT NOT NULL,
    requested_by INT NOT NULL,
    approved_by INT NULL,
    refund_amount DECIMAL(10, 2) NOT NULL,
    reason TEXT NULL,
    status VARCHAR(20) NOT NULL,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME NULL,
    CONSTRAINT fk_refund_transaction FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    CONSTRAINT fk_refund_requested_by FOREIGN KEY (requested_by) REFERENCES users(user_id),
    CONSTRAINT fk_refund_approved_by FOREIGN KEY (approved_by) REFERENCES clinic_administrators(clinic_administrator_id)
) ENGINE = InnoDB;
-- ============================================================
-- 30. REPORT
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    generated_by INT NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    report_data TEXT NULL,
    file_url VARCHAR(500) NULL,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_report_generated_by FOREIGN KEY (generated_by) REFERENCES users(user_id)
) ENGINE = InnoDB;
-- ============================================================
-- USEFUL INDEXES
-- ============================================================
CREATE INDEX idx_pet_owner_id ON pets(pet_owner_id);
CREATE INDEX idx_appointment_date ON appointments(appointment_date);
CREATE INDEX idx_appointment_veterinarian ON appointments(veterinarian_id);
CREATE INDEX idx_consultation_pet ON consultations(pet_id);
CREATE INDEX idx_dental_record_pet ON dental_records(pet_id);
CREATE INDEX idx_dental_image_pet ON dental_images(pet_id);
CREATE INDEX idx_ai_analysis_image ON ai_analysis_results(dental_image_id);
CREATE INDEX idx_chat_conversation_user ON chatbot_conversations(user_id);
CREATE INDEX idx_order_owner ON orders(pet_owner_id);
CREATE INDEX idx_transaction_user ON transactions(user_id);