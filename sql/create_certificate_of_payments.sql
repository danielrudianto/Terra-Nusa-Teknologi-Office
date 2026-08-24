CREATE TABLE IF NOT EXISTS certificate_of_payments (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(255) NOT NULL, 
	number INTEGER NOT NULL, 
	`purchaseOrderID` INTEGER NOT NULL, 
	`projectName` VARCHAR(255) NOT NULL, 
	date DATE NOT NULL, 
	`periodStart` DATE, 
	`periodEnd` DATE, 
	note TEXT, 
	status ENUM('draft','approved','cancelled') NOT NULL DEFAULT 'draft', 
	`grossAmount` DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	`deductionTotal` DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	`additionTotal` DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	`netAmount` DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	`createdBy` INTEGER NOT NULL, 
	`createdAt` DATETIME NOT NULL DEFAULT now(), 
	`isChecked` BOOL NOT NULL DEFAULT 0, 
	`checkedBy` INTEGER, 
	`checkedAt` DATETIME, 
	`isApproved` BOOL NOT NULL DEFAULT 0, 
	`approvedBy` INTEGER, 
	`approvedAt` DATETIME, 
	`isDelete` BOOL NOT NULL DEFAULT 0, 
	`deletedBy` INTEGER, 
	`deletedAt` DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cop_name UNIQUE (name), 
	FOREIGN KEY(`purchaseOrderID`) REFERENCES purchase_orders (id), 
	FOREIGN KEY(`createdBy`) REFERENCES users (id), 
	FOREIGN KEY(`checkedBy`) REFERENCES users (id), 
	FOREIGN KEY(`approvedBy`) REFERENCES users (id), 
	FOREIGN KEY(`deletedBy`) REFERENCES users (id)
);

CREATE INDEX ix_cop_po ON certificate_of_payments (`purchaseOrderID`);

CREATE INDEX ix_cop_status ON certificate_of_payments (status, `isDelete`);

CREATE TABLE IF NOT EXISTS certificate_of_payment_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	`certificateOfPaymentID` INTEGER NOT NULL, 
	`purchaseOrderItemID` INTEGER NOT NULL, 
	quantity DECIMAL(12, 2) NOT NULL DEFAULT '0.00', 
	price DECIMAL(14, 4) NOT NULL DEFAULT '0.0000', 
	amount DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(`certificateOfPaymentID`) REFERENCES certificate_of_payments (id), 
	FOREIGN KEY(`purchaseOrderItemID`) REFERENCES purchase_order_items (id)
);

CREATE INDEX ix_cop_item_cop ON certificate_of_payment_items (`certificateOfPaymentID`);

CREATE INDEX ix_cop_item_po_item ON certificate_of_payment_items (`purchaseOrderItemID`);

CREATE TABLE IF NOT EXISTS certificate_of_payment_adjustments (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	`certificateOfPaymentID` INTEGER NOT NULL, 
	kind ENUM('deduction','addition') NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	label VARCHAR(255), 
	amount DECIMAL(17, 4) NOT NULL DEFAULT '0.0000', 
	note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(`certificateOfPaymentID`) REFERENCES certificate_of_payments (id)
);

CREATE INDEX ix_cop_adj_cop ON certificate_of_payment_adjustments (`certificateOfPaymentID`);

CREATE INDEX ix_cop_adj_kategori ON certificate_of_payment_adjustments (kind, category);
