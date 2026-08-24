-- ===========================================================================
-- Buang kolom `value` dari `project_contracts`.
--
-- Nominal dokumen selalu sama dengan `dpp + dpp * ppn / 100`, dan tarif PPN
-- sudah tersimpan di baris yang sama — jadi angkanya tidak pernah bisa
-- berubah arti. Menyimpannya berarti dua tempat harus selalu sepakat, dan
-- cepat atau lambat salah satunya diperbarui tanpa yang lain.
--
-- Nilainya tetap keluar di respons API, dihitung saat dibaca.
--
-- JALANKAN SESUDAH alter_project_contracts_tax.sql, karena `dpp` diisi dari
-- `value`. Kalau urutannya terbalik, nilai kontraknya hilang.
-- ===========================================================================

-- Periksa dulu: `dpp` sudah terisi untuk semua baris?
--
--     SELECT COUNT(*) AS belum_terisi
--     FROM project_contracts
--     WHERE isDelete = 0 AND (dpp IS NULL OR dpp = 0);
--
-- Harus 0. Bila masih ada isinya, JANGAN lanjut — jalankan dulu
-- alter_project_contracts_tax.sql.

ALTER TABLE `project_contracts` DROP COLUMN `value`;
