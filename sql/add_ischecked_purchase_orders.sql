-- Tahap pemeriksaan pada purchase order.
--
-- Dokumen melewati DUA tangan: diperiksa dulu, baru disetujui. Pemeriksa
-- membaca isinya — harga, volume, spesifikasi; penyetuju memutuskan dokumen
-- itu boleh terbit.
--
-- Dipisah karena keduanya menjawab pertanyaan yang berbeda, dan yang
-- menggabungkannya berarti satu orang menjawab keduanya sendirian.

ALTER TABLE purchase_orders
  ADD COLUMN `isChecked` tinyint(1) NOT NULL DEFAULT '0' AFTER approvedAt,
  ADD COLUMN `checkedBy` int DEFAULT NULL AFTER isChecked,
  ADD COLUMN `checkedAt` datetime DEFAULT NULL AFTER checkedBy,
  ADD KEY `idx_po_checked_by` (`checkedBy`),
  ADD CONSTRAINT `fk_po_checked_by` FOREIGN KEY (`checkedBy`)
    REFERENCES `users` (`id`);

-- Dokumen yang SUDAH DISETUJUI dianggap sudah diperiksa.
--
-- Tanpa ini, seluruh dokumen lama mendadak tidak dapat disetujui ulang —
-- dan yang mencetaknya kembali menemukan lembar yang tadinya sah kini
-- tertahan pada tahap yang belum pernah ada saat ia terbit.
--
-- Pemeriksanya disamakan dengan penyetujunya: itu memang orang yang
-- sebenarnya membaca dokumen tersebut sebelum menerbitkannya.
UPDATE purchase_orders
SET isChecked = 1,
    checkedBy = approvedBy,
    checkedAt = approvedAt
WHERE isApproved = 1
  AND isDelete = 0;

-- Pastikan hasilnya; harus 0 baris.
SELECT COUNT(*) AS disetujui_tanpa_diperiksa
FROM purchase_orders
WHERE isApproved = 1
  AND isDelete = 0
  AND (isChecked = 0 OR isChecked IS NULL);
