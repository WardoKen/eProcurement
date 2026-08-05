--
-- Create model Role
--
CREATE TABLE `api_role` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(50) NOT NULL UNIQUE, `description` varchar(255) NOT NULL, `created_at` datetime(6) NOT NULL);
--
-- Create model Supplier
--
CREATE TABLE `api_supplier` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `company_name` varchar(255) NOT NULL, `business_type` varchar(50) NOT NULL, `business_address` longtext NOT NULL, `tin` varchar(100) NOT NULL, `contact_person` varchar(255) NOT NULL, `contact_phone` varchar(50) NOT NULL, `nature_of_business` varchar(255) NOT NULL, `goods_services` longtext NOT NULL, `years_in_business` integer NULL, `email` varchar(255) NOT NULL, `status` varchar(50) NOT NULL, `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL);
--
-- Create model SupplierDocument
--
CREATE TABLE `api_supplierdocument` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `doc_type` varchar(100) NOT NULL, `filename` varchar(512) NOT NULL, `original_name` varchar(512) NOT NULL, `uploaded_at` datetime(6) NOT NULL, `supplier_id` bigint NOT NULL);
--
-- Create model User
--
CREATE TABLE `api_user` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `username` varchar(255) NOT NULL UNIQUE, `password_hash` varchar(255) NOT NULL, `full_name` varchar(255) NOT NULL, `is_active` bool NOT NULL, `last_login` datetime(6) NULL, `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `role_id` bigint NOT NULL);
ALTER TABLE `api_supplierdocument` ADD CONSTRAINT `api_supplierdocument_supplier_id_13074665_fk_api_supplier_id` FOREIGN KEY (`supplier_id`) REFERENCES `api_supplier` (`id`);
ALTER TABLE `api_user` ADD CONSTRAINT `api_user_role_id_0b60389b_fk_api_role_id` FOREIGN KEY (`role_id`) REFERENCES `api_role` (`id`);
--
-- Create model PurchaseRequest
--
CREATE TABLE `api_purchaserequest` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `entity_name` varchar(255) NOT NULL, `fund_cluster` varchar(100) NULL, `office_section` varchar(255) NULL, `pr_no` varchar(50) NULL, `responsibility_center_code` varchar(100) NULL, `date` date NULL, `purpose` longtext NULL, `requested_by` varchar(255) NULL, `funds_available_by` varchar(255) NULL, `approved_by` varchar(255) NULL, `twg_verified_by` varchar(255) NULL, `grand_total` numeric(14, 2) NOT NULL, `created_at` datetime(6) NOT NULL);
--
-- Create model PurchaseRequestItem
--
CREATE TABLE `api_purchaserequestitem` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `stock_property_no` varchar(100) NULL, `unit` varchar(50) NULL, `item_description` longtext NOT NULL, `quantity` numeric(12, 2) NOT NULL, `unit_cost` numeric(14, 2) NOT NULL, `total_cost` numeric(14, 2) NOT NULL, `purchase_request_id` bigint NOT NULL);
ALTER TABLE `api_purchaserequestitem` ADD CONSTRAINT `api_purchaserequesti_purchase_request_id_0dcf8da5_fk_api_purch` FOREIGN KEY (`purchase_request_id`) REFERENCES `api_purchaserequest` (`id`);
--
-- Add field status to purchaserequest
--
ALTER TABLE `api_purchaserequest` ADD COLUMN `status` varchar(32) DEFAULT 'uploaded' NOT NULL;
ALTER TABLE `api_purchaserequest` ALTER COLUMN `status` DROP DEFAULT;
--
-- Add field category to purchaserequest
--
ALTER TABLE `api_purchaserequest` ADD COLUMN `category` varchar(255) NULL;
--
-- Add field category to purchaserequestitem
--
ALTER TABLE `api_purchaserequestitem` ADD COLUMN `category` varchar(255) NULL;
--
-- Create model Quotation
--
CREATE TABLE `api_quotation` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `quoted_amount` numeric(14, 2) NOT NULL, `estimated_delivery_days` integer NULL, `warranty_months` integer NULL, `remarks` longtext NOT NULL, `attachment_filename` varchar(512) NOT NULL, `status` varchar(32) NOT NULL, `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `purchase_request_id` bigint NOT NULL, `supplier_id` bigint NOT NULL);
--
-- Create model Notification
--
CREATE TABLE `api_notification` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `notification_type` varchar(50) NOT NULL, `title` varchar(255) NOT NULL, `message` longtext NOT NULL, `is_read` bool NOT NULL, `related_pr_id` integer NULL, `related_quotation_id` integer NULL, `created_at` datetime(6) NOT NULL, `supplier_id` bigint NOT NULL);
--
-- Create constraint unique_supplier_pr_quotation on model quotation
--
ALTER TABLE `api_quotation` ADD CONSTRAINT `unique_supplier_pr_quotation` UNIQUE (`supplier_id`, `purchase_request_id`);
ALTER TABLE `api_quotation` ADD CONSTRAINT `api_quotation_purchase_request_id_c022eb0e_fk_api_purch` FOREIGN KEY (`purchase_request_id`) REFERENCES `api_purchaserequest` (`id`);
ALTER TABLE `api_quotation` ADD CONSTRAINT `api_quotation_supplier_id_238f1891_fk_api_supplier_id` FOREIGN KEY (`supplier_id`) REFERENCES `api_supplier` (`id`);
ALTER TABLE `api_notification` ADD CONSTRAINT `api_notification_supplier_id_be3b45f6_fk_api_supplier_id` FOREIGN KEY (`supplier_id`) REFERENCES `api_supplier` (`id`);
--
-- Create model Category
--
CREATE TABLE `api_category` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(255) NOT NULL UNIQUE, `description` varchar(500) NOT NULL, `is_active` bool NOT NULL, `created_at` datetime(6) NOT NULL);
--
-- Create model SupplierCategory
--
CREATE TABLE `api_suppliercategory` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `created_at` datetime(6) NOT NULL);
--
-- Remove constraint unique_supplier_pr_quotation from model quotation
--
ALTER TABLE `api_quotation` DROP INDEX `unique_supplier_pr_quotation`;
--
-- Add field products_services to supplier
--
ALTER TABLE `api_supplier` ADD COLUMN `products_services` longtext NOT NULL;
--
-- Alter field status on supplier
--
-- (no-op)
--
-- Alter unique_together for quotation (1 constraint(s))
--
ALTER TABLE `api_quotation` ADD CONSTRAINT `api_quotation_supplier_id_purchase_request_id_7aa99ebe_uniq` UNIQUE (`supplier_id`, `purchase_request_id`);
--
-- Add field category to suppliercategory
--
ALTER TABLE `api_suppliercategory` ADD COLUMN `category_id` bigint NOT NULL , ADD CONSTRAINT `api_suppliercategory_category_id_3e57dfb4_fk_api_category_id` FOREIGN KEY (`category_id`) REFERENCES `api_category`(`id`);
--
-- Add field supplier to suppliercategory
--
ALTER TABLE `api_suppliercategory` ADD COLUMN `supplier_id` bigint NOT NULL , ADD CONSTRAINT `api_suppliercategory_supplier_id_ce31cda6_fk_api_supplier_id` FOREIGN KEY (`supplier_id`) REFERENCES `api_supplier`(`id`);
--
-- Alter unique_together for suppliercategory (1 constraint(s))
--
ALTER TABLE `api_suppliercategory` ADD CONSTRAINT `api_suppliercategory_supplier_id_category_id_ef44eade_uniq` UNIQUE (`supplier_id`, `category_id`);
--
-- Add field review_remarks to supplier
--
ALTER TABLE `api_supplier` ADD COLUMN `review_remarks` longtext NOT NULL;
--
-- Add field verification_status to supplierdocument
--
ALTER TABLE `api_supplierdocument` ADD COLUMN `verification_status` varchar(32) DEFAULT 'Pending' NOT NULL;
ALTER TABLE `api_supplierdocument` ALTER COLUMN `verification_status` DROP DEFAULT;
