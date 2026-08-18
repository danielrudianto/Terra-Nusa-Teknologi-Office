-- Tender pengadaan.
--
-- Empat tabel; pemisahan `tender_quote_items` dari `tender_items` disengaja:
-- TIDAK setiap pemasok menawar seluruh baris, dan menyimpan harganya pada
-- baris permintaan memaksa satu harga per baris — justru yang hendak
-- dibandingkan.
--
-- Jalankan berurutan; tabel bawah merujuk yang di atasnya.

CREATE TABLE IF NOT EXISTS tenders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    number          INT NULL,
    name            VARCHAR(255) NOT NULL,
    date            DATE NOT NULL,
    -- 'barang' | 'jasa'
    tenderType      VARCHAR(20) NOT NULL,
    projectName     VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    -- Syarat yang DIMINTA AKN, bukan yang ditawarkan pemasok.
    paymentTerm     VARCHAR(20) NULL,
    creditTerm      INT NULL,
    -- Garansi, masa berlaku penawaran, syarat pengiriman.
    requirements    TEXT NULL,
    dueDate         DATE NULL,
    -- 'draft' | 'berjalan' | 'selesai' | 'batal'
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    winnerQuoteID   INT NULL,
    winnerReason    TEXT NULL,
    decidedAt       DATETIME NULL,
    decidedBy       INT NULL,
    createdAt       DATETIME NOT NULL,
    createdBy       INT NOT NULL,
    updatedAt       DATETIME NULL,
    updatedBy       INT NULL,
    isDelete        TINYINT(1) NOT NULL DEFAULT 0,
    deletedAt       DATETIME NULL,
    deletedBy       INT NULL,
    INDEX idx_tenders_number (number),
    INDEX idx_tenders_status (status),
    INDEX idx_tenders_project (projectName),
    CONSTRAINT fk_tenders_created  FOREIGN KEY (createdBy)  REFERENCES users(id),
    CONSTRAINT fk_tenders_updated  FOREIGN KEY (updatedBy)  REFERENCES users(id),
    CONSTRAINT fk_tenders_deleted  FOREIGN KEY (deletedBy)  REFERENCES users(id),
    CONSTRAINT fk_tenders_decided  FOREIGN KEY (decidedBy)  REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tender_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tenderID        INT NOT NULL,
    -- Barang dari katalog; kosong pada tender jasa.
    itemID          INT NULL,
    -- Nama DISALIN, tidak hanya dirujuk lewat itemID: permintaan penawaran
    -- sudah disebar, dan namanya harus tetap seperti saat disebarkan.
    name            VARCHAR(255) NOT NULL,
    specification   TEXT NULL,
    quantity        DECIMAL(15,2) NULL,
    unit            VARCHAR(50) NULL,
    sortOrder       INT NOT NULL DEFAULT 0,
    INDEX idx_tender_items_tender (tenderID),
    CONSTRAINT fk_tender_items_tender FOREIGN KEY (tenderID) REFERENCES tenders(id),
    CONSTRAINT fk_tender_items_item   FOREIGN KEY (itemID)   REFERENCES master_item(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tender_quotes (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tenderID        INT NOT NULL,
    supplierID      INT NOT NULL,
    -- Syarat yang DITAWARKAN pemasok; kerap berbeda dari yang diminta.
    paymentTerm     VARCHAR(20) NULL,
    creditTerm      INT NULL,
    -- Garansi, waktu kirim, ketentuan lain dari pemasok.
    notes           TEXT NULL,
    -- Dicatat manual: balasannya datang lewat WhatsApp.
    quotedAt        DATE NULL,
    createdAt       DATETIME NOT NULL,
    createdBy       INT NOT NULL,
    updatedAt       DATETIME NULL,
    updatedBy       INT NULL,
    isDelete        TINYINT(1) NOT NULL DEFAULT 0,
    deletedAt       DATETIME NULL,
    deletedBy       INT NULL,
    INDEX idx_tender_quotes_tender (tenderID),
    INDEX idx_tender_quotes_supplier (supplierID),
    CONSTRAINT fk_tender_quotes_tender   FOREIGN KEY (tenderID)   REFERENCES tenders(id),
    CONSTRAINT fk_tender_quotes_supplier FOREIGN KEY (supplierID) REFERENCES suppliers(id),
    CONSTRAINT fk_tender_quotes_created  FOREIGN KEY (createdBy)  REFERENCES users(id),
    CONSTRAINT fk_tender_quotes_updated  FOREIGN KEY (updatedBy)  REFERENCES users(id),
    CONSTRAINT fk_tender_quotes_deleted  FOREIGN KEY (deletedBy)  REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tender_quote_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    quoteID         INT NOT NULL,
    tenderItemID    INT NOT NULL,
    -- Baris yang TIDAK ditawar sama sekali tidak disimpan, sehingga kolom ini
    -- praktis selalu terisi. Dibiarkan NULL-able supaya baris lama yang
    -- terlanjur tersimpan tanpa harga tidak menggagalkan pembacaan.
    price           DECIMAL(15,2) NULL,
    notes           TEXT NULL,
    INDEX idx_tqi_quote (quoteID),
    INDEX idx_tqi_item (tenderItemID),
    CONSTRAINT fk_tqi_quote FOREIGN KEY (quoteID)      REFERENCES tender_quotes(id),
    CONSTRAINT fk_tqi_item  FOREIGN KEY (tenderItemID) REFERENCES tender_items(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
