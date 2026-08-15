-- ===========================================================================
-- Buang kolom `description` dari tabel `projects`.
--
-- Alasannya: `name` dan `description` menanyakan hal yang nyaris sama, dan
-- yang mengisi tidak pernah yakin mana untuk apa — hasilnya salah satunya
-- selalu kosong atau keduanya berisi teks yang mirip.
--
-- Kolom `description` pada `project_contracts` TIDAK ikut dibuang. Yang itu
-- catatan per dokumen SPK/adendum ("penambahan lingkup pekerjaan galian"),
-- bukan pengulangan nama proyek.
-- ===========================================================================

-- Periksa dulu: adakah isi yang akan hilang?
--
--     SELECT id, code, name, description
--     FROM projects
--     WHERE description IS NOT NULL AND TRIM(description) <> '';
--
-- Bila ada baris yang keterangannya ternyata lebih lengkap daripada namanya,
-- pindahkan dulu sebelum kolomnya dibuang:
--
--     UPDATE projects
--     SET name = description, updatedAt = NOW()
--     WHERE id IN (...);

ALTER TABLE `projects` DROP COLUMN `description`;
