-- ===========================================================================
-- Tabel induk proyek dan nilai kontraknya
-- ===========================================================================
--
-- Sebelum ini, "proyek" hanya berupa teks bebas `projectName` di lima tabel.
-- Akibatnya nilai kontrak tidak tersimpan di mana pun, dan salah ketik
-- menciptakan proyek baru tanpa ada yang tahu.
--
-- Jalankan berurutan. Bagian 3 hanya MENYEMAI kode yang sudah dipakai; nama,
-- klien, dan nilai kontraknya diisi belakangan lewat aplikasi.
--
-- SENGAJA TIDAK ADA FOREIGN KEY dari purchases/sales_invoices/dst ke
-- projects. Data lama memuat kode yang belum tentu seragam; memasang foreign
-- key sekarang akan menggagalkan migrasi pada baris yang kodenya menyimpang.
-- Penyambungan dilakukan lewat `code`. Setelah datanya bersih dan masukannya
-- diganti menjadi pemilih, tautannya baru dieratkan.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. Induk proyek
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `projects` (
  `id`          INT           NOT NULL AUTO_INCREMENT,
  `code`        VARCHAR(20)   NOT NULL,
  `name`        VARCHAR(255)  NOT NULL,
  `clientID`    INT           NULL,
  `startDate`   DATE          NULL,
  `endDate`     DATE          NULL,
  -- Tiga keadaan proyek dinyatakan oleh dua penanda:
  --
  --     isActive=1, isCancelled=0  -> berjalan
  --     isActive=0, isCancelled=0  -> selesai
  --     isActive=0, isCancelled=1  -> batal
  --
  -- Boolean, bukan enum teks: tidak ada nilai tak sah yang bisa masuk, dan
  -- di layar cukup diterjemahkan sebagai label. Kombinasi aktif+batal dijaga
  -- di controller, bukan di sini.
  --
  -- Proyek batal SENGAJA tidak memakai `isDelete`: biaya yang terlanjur
  -- dikeluarkan atasnya tetap tercatat, dan induknya harus tetap ada agar
  -- biaya itu tidak menjadi yatim di laporan.
  `isActive`    TINYINT(1)    NOT NULL DEFAULT 1,
  `isCancelled` TINYINT(1)    NOT NULL DEFAULT 0,
  `createdAt`   DATETIME      NOT NULL,
  `createdBy`   INT           NOT NULL,
  `updatedAt`   DATETIME      NULL DEFAULT NULL,
  `updatedBy`   INT           NULL DEFAULT NULL,
  `isDelete`    TINYINT(1)    NOT NULL DEFAULT 0,
  `deletedAt`   DATETIME      NULL DEFAULT NULL,
  `deletedBy`   INT           NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  -- Kode wajib unik: dua baris berkode sama membuat penyambungan dokumen
  -- menjadi ambigu dan angka laporannya berlipat.
  UNIQUE KEY `uq_projects_code` (`code`),
  KEY `ix_projects_active` (`isActive`, `isCancelled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- 2. Nilai kontrak, satu baris per dokumen
-- ---------------------------------------------------------------------------
--
-- Nilai kontrak tidak disimpan sebagai satu kolom di `projects`. Adendum
-- adalah hal biasa, dan satu kolom yang ditimpa akan menghapus riwayatnya.
-- Nilai kontrak berjalan = SUM(value) dari baris yang belum dihapus.
--
-- `value` boleh negatif: adendum pengurangan lingkup kerja memang mengurangi
-- nilai kontrak, dan mencatatnya sebagai baris negatif membuat jejaknya utuh.
CREATE TABLE IF NOT EXISTS `project_contracts` (
  `id`             INT            NOT NULL AUTO_INCREMENT,
  `projectID`      INT            NOT NULL,
  `documentNumber` VARCHAR(100)   NOT NULL,
  `documentType`   VARCHAR(20)    NOT NULL DEFAULT 'spk',
  -- Nilai dipecah seperti dokumen aslinya. Yang dipakai menghitung margin
  -- adalah `dpp`: PPN titipan negara, bukan pendapatan.
  `dpp`            DECIMAL(20,2)  NOT NULL,
  `ppn`            DECIMAL(6,2)   NOT NULL DEFAULT 0,
  `pphCode`        VARCHAR(20)    NULL,
  `pphTaxObject`   VARCHAR(255)   NULL,
  `pphPercentage`  DECIMAL(6,2)   NULL,
  --
  -- TIDAK ada kolom `value`. Nominal dokumen selalu sama dengan
  -- `dpp + dpp * ppn / 100`, dan tarifnya sudah tersimpan di baris ini.
  -- Menyimpannya berarti dua tempat harus selalu sepakat.
  --
  `date`           DATE           NOT NULL,
  `description`    VARCHAR(500)   NULL,
  `createdAt`      DATETIME       NOT NULL,
  `createdBy`      INT            NOT NULL,
  `updatedAt`      DATETIME       NULL DEFAULT NULL,
  `updatedBy`      INT            NULL DEFAULT NULL,
  `isDelete`       TINYINT(1)     NOT NULL DEFAULT 0,
  `deletedAt`      DATETIME       NULL DEFAULT NULL,
  `deletedBy`      INT            NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_project_contracts_project` (`projectID`, `isDelete`),
  CONSTRAINT `fk_project_contracts_project`
    FOREIGN KEY (`projectID`) REFERENCES `projects` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- 3. Semai kode proyek dari dokumen yang sudah ada
-- ---------------------------------------------------------------------------
--
-- `name` diisi sama dengan kodenya sebagai penanda sementara — nama
-- sebenarnya diisi lewat aplikasi. `createdBy` = 1 mewakili migrasi; ganti
-- bila id pengguna sistem Anda berbeda.
--
-- Baris kosong dan spasi tepi dibuang, dan kodenya diseragamkan huruf besar.
INSERT INTO `projects` (`code`, `name`, `isActive`, `isCancelled`, `createdAt`, `createdBy`, `isDelete`)
SELECT k.code, k.code, 1, 0, NOW(), 1, 0
FROM (
  SELECT DISTINCT UPPER(TRIM(`projectName`)) AS code FROM `purchases`
    WHERE `projectName` IS NOT NULL AND TRIM(`projectName`) <> ''
  UNION
  SELECT DISTINCT UPPER(TRIM(`projectName`)) FROM `purchase_drafts`
    WHERE `projectName` IS NOT NULL AND TRIM(`projectName`) <> ''
  UNION
  SELECT DISTINCT UPPER(TRIM(`projectName`)) FROM `purchase_orders`
    WHERE `projectName` IS NOT NULL AND TRIM(`projectName`) <> ''
  UNION
  SELECT DISTINCT UPPER(TRIM(`projectName`)) FROM `reimbursements`
    WHERE `projectName` IS NOT NULL AND TRIM(`projectName`) <> ''
  UNION
  SELECT DISTINCT UPPER(TRIM(`projectName`)) FROM `sales_invoices`
    WHERE `projectName` IS NOT NULL AND TRIM(`projectName`) <> ''
) AS k
ON DUPLICATE KEY UPDATE `projects`.`code` = `projects`.`code`;


-- ---------------------------------------------------------------------------
-- 4. Isi klien dari faktur penjualan
-- ---------------------------------------------------------------------------
--
-- Klien tidak perlu diketik ulang: `sales_invoices` sudah memuat pasangan
-- projectName -> clientID.
--
-- Dipilih klien yang PALING SERING muncul pada proyek tersebut, bukan yang
-- terbaru. Satu faktur yang klienya salah pilih tidak boleh menentukan klien
-- seluruh proyek; kalau terjadi seri, yang tanggalnya paling akhir yang
-- dipakai.
--
-- Faktur terhapus diabaikan.
UPDATE `projects` p
SET p.`clientID` = (
  SELECT si.`clientID`
  FROM `sales_invoices` si
  WHERE UPPER(TRIM(si.`projectName`)) = p.`code`
    AND si.`clientID` IS NOT NULL
    AND si.`isDelete` = 0
  GROUP BY si.`clientID`
  ORDER BY COUNT(*) DESC, MAX(si.`date`) DESC
  LIMIT 1
)
-- `p.id > 0` tidak menyaring apa pun; ia ada agar kueri ini tetap berjalan
-- di bawah safe update mode MySQL Workbench, yang menolak UPDATE tanpa
-- syarat pada kolom kunci (error 1175). Menyisipkan syarat kunci lebih baik
-- daripada mematikan pengamannya.
WHERE p.`id` > 0
  AND p.`clientID` IS NULL
  AND p.`isDelete` = 0;


-- ---------------------------------------------------------------------------
-- 5. PEMERIKSAAN — jalankan dan BACA hasilnya sebelum melangkah
-- ---------------------------------------------------------------------------
--
-- Kueri ini tidak mengubah apa pun. Tujuannya menemukan kode yang
-- kemungkinan besar salah ketik: kode yang hanya dipakai satu-dua dokumen,
-- di sebelah kode lain yang mirip. Gabungkan secara manual sebelum
-- masukannya diganti menjadi pemilih — sesudah itu kode menyimpang tidak
-- bisa lagi dibuat, tetapi yang terlanjur ada akan menetap.
--
-- SELECT p.code,
--        p.name,
--        (SELECT COUNT(*) FROM purchases       x WHERE UPPER(TRIM(x.projectName)) = p.code) AS pembelian,
--        (SELECT COUNT(*) FROM purchase_orders x WHERE UPPER(TRIM(x.projectName)) = p.code) AS po,
--        (SELECT COUNT(*) FROM reimbursements  x WHERE UPPER(TRIM(x.projectName)) = p.code) AS reimbursement,
--        (SELECT COUNT(*) FROM sales_invoices  x WHERE UPPER(TRIM(x.projectName)) = p.code) AS faktur
-- FROM projects p
-- WHERE p.isDelete = 0
-- ORDER BY (pembelian + po + reimbursement + faktur) ASC, p.code;
--
-- Kode dengan jumlah dokumen 0 hampir pasti sisa salah ketik yang dokumennya
-- sudah dihapus, dan aman dibuang.
--
--
-- Kedua: proyek yang fakturnya memuat LEBIH DARI SATU klien. Bagian 4 memilih
-- yang paling sering, tetapi kalau muncul di sini berarti ada faktur yang
-- klienya keliru — atau memang satu kode proyek dipakai untuk dua pekerjaan
-- berbeda, dan itu harus dipisah sebelum laporannya dipercaya.
--
-- SELECT UPPER(TRIM(si.projectName)) AS code,
--        COUNT(DISTINCT si.clientID)  AS jumlah_klien,
--        GROUP_CONCAT(DISTINCT si.clientID) AS daftar_klien
-- FROM sales_invoices si
-- WHERE si.isDelete = 0 AND si.clientID IS NOT NULL
--   AND si.projectName IS NOT NULL AND TRIM(si.projectName) <> ''
-- GROUP BY UPPER(TRIM(si.projectName))
-- HAVING COUNT(DISTINCT si.clientID) > 1;
--
--
-- Ketiga: proyek yang klienya tetap kosong setelah bagian 4 — biasanya proyek
-- yang belum pernah ditagihkan sama sekali. Isi manual lewat aplikasi.
--
-- SELECT code, name FROM projects WHERE clientID IS NULL AND isDelete = 0;
