-- Alur CoP dua persetujuan: BAP lalu CoP.
--
-- Empat tahap menggantikan tiga:
--   dibuat        (createdBy)      level 1  — isi VOLUME
--   BAP disetujui (bapApprovedBy)  level 4+ — progres lapangan disahkan
--   CoP dibuat    (copCreatedBy)   level 2+ — harga & potongan diisi
--   CoP disetujui (approvedBy)     level 4+ — boleh ditagih
--
-- Kolom `checked*` LAMA berganti nama menjadi `copCreated*`: perannya kini
-- MEMBUAT CoP (mengisi harga), bukan "memeriksa". Tahap persetujuan BAP di
-- depannya adalah kolom yang benar-benar baru.
--
-- Seluruh CoP lama DINOMORI ULANG alurnya: stempelnya direset ke tahap awal
-- supaya menempuh persetujuan BAP lalu CoP sekali lagi. Nilai harga &
-- potongan yang sudah terisi TIDAK dihapus — hanya penanda tahapnya yang
-- dikembalikan ke nol.
--
-- Jalankan SETELAH deploy kode baru. Idempoten sederhana tidak dijamin;
-- jalankan sekali.

-- 1) Kolom persetujuan BAP — gerbang pertama. Baru, NULL/0 di awal.
ALTER TABLE certificate_of_payments
  ADD COLUMN isBapApproved TINYINT(1) NOT NULL DEFAULT 0 AFTER createdAt,
  ADD COLUMN bapApprovedBy INT NULL AFTER isBapApproved,
  ADD COLUMN bapApprovedAt DATETIME NULL AFTER bapApprovedBy,
  ADD CONSTRAINT fk_cop_bap_approver
    FOREIGN KEY (bapApprovedBy) REFERENCES users(id);

-- 2) Ganti nama kolom pemeriksaan LAMA menjadi pembuatan CoP.
--
-- CHANGE COLUMN, bukan DROP+ADD: isinya (siapa mengisi harga, kapan) tetap
-- bermakna pada alur baru sebagai "CoP dibuat oleh". FK-nya ikut mengikuti
-- kolom pada MySQL 8 tanpa perlu dilepas.
ALTER TABLE certificate_of_payments
  CHANGE COLUMN isChecked isCopCreated TINYINT(1) NOT NULL DEFAULT 0,
  CHANGE COLUMN checkedBy copCreatedBy INT NULL,
  CHANGE COLUMN checkedAt copCreatedAt DATETIME NULL;

-- 3) Reset alur seluruh CoP lama ke tahap awal — approve ulang.
--
-- Hanya penanda tahap yang dinolkan; baris harga, potongan, dan volumenya
-- utuh. Yang sudah dihapus (isDelete=1) dibiarkan apa adanya.
UPDATE certificate_of_payments
SET isBapApproved = 0, bapApprovedBy = NULL, bapApprovedAt = NULL,
    isCopCreated  = 0, copCreatedBy  = NULL, copCreatedAt  = NULL,
    isApproved    = 0, approvedBy    = NULL, approvedAt    = NULL,
    status = 'draft'
WHERE isDelete = 0;

-- Catatan: CoP yang TERLANJUR ditagihkan (sudah ada purchase yang merujuknya)
-- ikut kembali ke 'draft'. Itu tidak menagihkannya dua kali — penjagaan
-- penagihan menolak CoP yang belum disetujui — tetapi bila ada yang sedang
-- berjalan, setujui ulang BAP lalu CoP-nya agar keadaannya kembali konsisten.
