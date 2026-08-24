-- ===========================================================================
-- Migrasi kolom keadaan proyek.
--
-- Keadaan akhir yang dituju:
--
--     isActive=1, isCancelled=0  -> berjalan
--     isActive=0, isCancelled=0  -> selesai
--     isActive=0, isCancelled=1  -> batal
--
-- Pilih SATU bagian sesuai keadaan basis data Anda. Jalankan kueri ini dulu
-- untuk mengetahui yang mana:
--
--     SHOW COLUMNS FROM `projects`;
--
--   * Tabel `projects` belum ada          -> LEWATI berkas ini,
--                                            jalankan create_projects.sql
--   * Ada kolom `status`                  -> jalankan BAGIAN A
--   * Ada `isActive` tanpa `isCancelled`  -> jalankan BAGIAN B
--   * Sudah ada keduanya                  -> tidak perlu apa-apa
--
-- CATATAN safe update mode: seluruh UPDATE di berkas ini sudah memakai
-- syarat pada kolom kunci, sehingga tidak perlu mematikan pengaman apa pun.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- BAGIAN A — dari kolom `status` bertipe teks
-- ---------------------------------------------------------------------------

ALTER TABLE `projects`
  ADD COLUMN `isActive`    TINYINT(1) NOT NULL DEFAULT 1 AFTER `endDate`,
  ADD COLUMN `isCancelled` TINYINT(1) NOT NULL DEFAULT 0 AFTER `isActive`;

-- `WHERE id > 0` tidak menyaring apa pun; ia ada agar kueri ini tetap
-- berjalan di bawah safe update mode MySQL Workbench, yang menolak UPDATE
-- tanpa syarat pada kolom kunci (error 1175).
UPDATE `projects`
SET `isActive`    = IF(LOWER(TRIM(`status`)) = 'aktif', 1, 0),
    `isCancelled` = IF(LOWER(TRIM(`status`)) = 'batal', 1, 0)
WHERE `id` > 0;

ALTER TABLE `projects` DROP INDEX `ix_projects_status`;
ALTER TABLE `projects` ADD INDEX `ix_projects_active` (`isActive`, `isCancelled`);
ALTER TABLE `projects` DROP COLUMN `status`;


-- ---------------------------------------------------------------------------
-- BAGIAN B — sudah ada `isActive`, tinggal menambah `isCancelled`
-- ---------------------------------------------------------------------------
--
-- Baris yang sudah nonaktif akan terbaca sebagai SELESAI, karena keterangan
-- batalnya memang tidak pernah tersimpan. Bila ada proyek yang sebenarnya
-- batal, tandai manual sesudahnya:
--
--     UPDATE projects SET isCancelled = 1, isActive = 0 WHERE code IN ('...');

-- ALTER TABLE `projects`
--   ADD COLUMN `isCancelled` TINYINT(1) NOT NULL DEFAULT 0 AFTER `isActive`;
--
-- ALTER TABLE `projects` DROP INDEX `ix_projects_active`;
-- ALTER TABLE `projects` ADD INDEX `ix_projects_active` (`isActive`, `isCancelled`);


-- ---------------------------------------------------------------------------
-- PEMERIKSAAN — tidak boleh ada baris yang aktif sekaligus batal
-- ---------------------------------------------------------------------------
--
-- SELECT id, code, isActive, isCancelled
-- FROM projects
-- WHERE isActive = 1 AND isCancelled = 1;
--
-- Hasil harus kosong. Bila ada isinya, itu data yang masuk sebelum penjagaan
-- di controller berlaku — perbaiki dengan:
--
--     UPDATE projects SET isActive = 0
--     WHERE id > 0 AND isActive = 1 AND isCancelled = 1;
