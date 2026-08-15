-- ===========================================================================
-- Pecah nilai kontrak menjadi DPP, PPN, dan PPh.
--
-- HANYA untuk basis data yang sudah menjalankan create_projects.sql versi
-- sebelumnya (project_contracts hanya punya kolom `value`).
--
-- Yang dipakai menghitung margin adalah `dpp`. PPN titipan negara dan bukan
-- pendapatan; memakai nominal kotor membuat margin setiap proyek tampak
-- lebih besar daripada kenyataannya.
-- ===========================================================================

ALTER TABLE `project_contracts`
  ADD COLUMN `dpp`           DECIMAL(20,2) NOT NULL DEFAULT 0 AFTER `documentType`,
  ADD COLUMN `ppn`           DECIMAL(6,2)  NOT NULL DEFAULT 0 AFTER `dpp`,
  ADD COLUMN `pphCode`       VARCHAR(20)   NULL AFTER `ppn`,
  ADD COLUMN `pphTaxObject`  VARCHAR(255)  NULL AFTER `pphCode`,
  ADD COLUMN `pphPercentage` DECIMAL(6,2)  NULL AFTER `pphTaxObject`;

-- Baris lama hanya punya nominal. Yang bisa dipastikan hanyalah bahwa
-- nominal itu ada; komposisinya tidak tersimpan di mana pun.
--
-- DPP diisi sama dengan nominal dan PPN nol. Itu ASUMSI, bukan fakta: bila
-- dokumen aslinya memuat PPN, angka DPP-nya kini kelebihan sebesar PPN itu.
-- Periksa dokumen yang sudah masuk dan perbaiki manual sesudahnya.
UPDATE `project_contracts`
SET `dpp` = `value`, `ppn` = 0
WHERE `id` > 0 AND `dpp` = 0;

-- Daftar baris yang perlu diperiksa:
--
--     SELECT c.id, p.code, c.documentNumber, c.value, c.dpp, c.ppn
--     FROM project_contracts c JOIN projects p ON p.id = c.projectID
--     WHERE c.isDelete = 0
--     ORDER BY p.code, c.date;
--
-- Untuk dokumen yang nominalnya sudah termasuk PPN 11%, hitung mundur:
--
--     UPDATE project_contracts
--     SET dpp = ROUND(value / 1.11, 2), ppn = 11
--     WHERE id IN (...);
