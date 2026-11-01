USE veterinary_dental_care;
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_key VARCHAR(190) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME NULL,
    CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT uq_notification_user_event UNIQUE (user_id, event_key),
    INDEX ix_notification_user_created (
        user_id,
        created_at,
        notification_id
    ),
    INDEX ix_notification_user_read (user_id, read_at)
);