-- Tenor dan jadwal angsuran pinjaman — OPSIONAL.
--
-- Diisi untuk pinjaman berjadwal (leasing seperti ORIX, kredit bank);
-- dibiarkan kosong untuk pinjaman tanpa jadwal (pinjaman pribadi).
--
-- Dengan tenor, Status Keuangan dapat memisahkan porsi pinjaman yang jatuh
-- tempo dalam 12 bulan dan memasukkannya ke kewajiban lancar. Tanpa tenor
-- pinjamannya tetap di luar quick ratio seperti sebelumnya.
--
-- Kolom NULL, jadi seluruh pinjaman lama tetap sah tanpa diubah.

ALTER TABLE loans
  ADD COLUMN tenorMonths INT NULL AFTER debt,
  ADD COLUMN firstInstallmentDate DATE NULL AFTER tenorMonths;
