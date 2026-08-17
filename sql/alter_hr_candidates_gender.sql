-- Pelamar didaftarkan hanya dengan nama dan jenis kelamin.
--
-- Sisanya — panggilan, tanggal lahir, alamat, kontak — diisi pelamar sendiri
-- lewat tautan. Mengumpulkannya lebih dulu justru pekerjaan yang hendak
-- dihilangkan.

ALTER TABLE hr_candidates
  -- L / P.
  --
  -- Ditanyakan di muka bersama namanya: yang menyusun jadwal wawancara
  -- memerlukannya sebelum pelamarnya sempat membuka tautan, dan sebagian
  -- tidak pernah membukanya sama sekali.
  ADD COLUMN `gender` varchar(1) DEFAULT NULL AFTER `name`,

  -- Surel BOLEH kosong.
  --
  -- Mewajibkannya berarti yang mendaftarkan harus mengumpulkan surel seluruh
  -- pelamar lebih dulu — dan pada tahap ini sebagian memang belum diketahui.
  MODIFY COLUMN `email` varchar(150) DEFAULT NULL;

-- Pastikan hasilnya.
SHOW COLUMNS FROM hr_candidates WHERE Field IN ('gender', 'email');
