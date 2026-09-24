-- =====================================================================
-- AKUN PEMERIKSA — hanya baca
--
-- Satu kolom pada `users`. Ditegakkan di `utils/permission.py::is_allowed`,
-- DI ATAS izin khusus per pengguna: tanda ini menyatakan sifat akunnya,
-- bukan kewenangan atas satu modul.
--
-- Kenapa perlu: laba rugi dan jejak aktivitas dijaga level 5, dan level 5
-- sekaligus memberi hak MENULIS atas rekening bank, pinjaman, dan pengguna.
-- Tanpa kolom ini, memberi konsultan akses baca berarti memberi mereka hak
-- ubah atas data induk keuangan.
-- =====================================================================

ALTER TABLE users
  ADD COLUMN isReadOnly TINYINT(1) NOT NULL DEFAULT 0
  AFTER authenticationLevel;

-- ---------------------------------------------------------------------
-- Contoh pemakaian — JANGAN dijalankan sebelum akunnya dibuat.
-- Ganti alamat surelnya, lalu periksa hasilnya di bawah.
-- ---------------------------------------------------------------------

-- UPDATE users SET isReadOnly = 1 WHERE email = 'konsultan.pajak@contoh.co.id';
-- UPDATE users SET isReadOnly = 1 WHERE email = 'konsultan.akuntansi@contoh.co.id';

-- ---------------------------------------------------------------------
-- PERIKSA — siapa saja yang sekarang hanya dapat membaca.
-- ---------------------------------------------------------------------
SELECT id, name, email, authenticationLevel, isReadOnly, isActive
FROM users
WHERE isReadOnly = 1
ORDER BY id;
