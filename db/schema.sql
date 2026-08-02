-- SQL schema for eProcure application
-- Creates the database and tables required for authentication and suppliers

-- NOTE: Removed CREATE DATABASE/USE to make this file safe to run from
-- an already-open connection in MySQL Workbench. Create the
-- `eprocure` database separately or select it in Workbench before
-- executing this script.

CREATE TABLE IF NOT EXISTS `roles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL UNIQUE,
  `description` VARCHAR(255),
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `roles` (`name`, `description`)
SELECT 'admin', 'Administrator'
WHERE NOT EXISTS (SELECT 1 FROM `roles` WHERE `name` = 'admin');

INSERT INTO `roles` (`name`, `description`)
SELECT 'buyer', 'Buyer user'
WHERE NOT EXISTS (SELECT 1 FROM `roles` WHERE `name` = 'buyer');

INSERT INTO `roles` (`name`, `description`)
SELECT 'supplier', 'Supplier user'
WHERE NOT EXISTS (SELECT 1 FROM `roles` WHERE `name` = 'supplier');

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(255),
  `role_id` INT NOT NULL,
  `is_active` TINYINT NOT NULL DEFAULT 1,
  `last_login` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_users_username` (`username`),
  CONSTRAINT `fk_users_role`
    FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `suppliers` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `company_name` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255),
  `contact_phone` VARCHAR(50),
  `status` VARCHAR(50) NOT NULL DEFAULT 'Pending',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `api_purchaserequest` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `entity_name` VARCHAR(255) NOT NULL,
  `fund_cluster` VARCHAR(100) NULL,
  `office_section` VARCHAR(255) NULL,
  `pr_no` VARCHAR(50) NULL,
  `responsibility_center_code` VARCHAR(100) NULL,
  `date` DATE NULL,
  `purpose` TEXT NULL,
  `requested_by` VARCHAR(255) NULL,
  `funds_available_by` VARCHAR(255) NULL,
  `approved_by` VARCHAR(255) NULL,
  `twg_verified_by` VARCHAR(255) NULL,
  `grand_total` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_api_purchaserequest_pr_no` (`pr_no`),
  INDEX `idx_api_purchaserequest_entity` (`entity_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `api_purchaserequestitem` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `purchase_request_id` BIGINT NOT NULL,
  `stock_property_no` VARCHAR(100) NULL,
  `unit` VARCHAR(50) NULL,
  `item_description` TEXT NULL,
  `quantity` DECIMAL(12,2) NOT NULL DEFAULT 0,
  `unit_cost` DECIMAL(14,2) NOT NULL DEFAULT 0,
  `total_cost` DECIMAL(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  INDEX `idx_api_purchaserequestitem_request_id` (`purchase_request_id`),
  CONSTRAINT `fk_api_purchaserequestitem_pr`
    FOREIGN KEY (`purchase_request_id`) REFERENCES `api_purchaserequest` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
