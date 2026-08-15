-- ===========================================================================
-- Penanda draft pembelian yang sudah menjadi pembelian.
--
-- Sebelum ini konversi hanya membuat pembelian baru; draftnya tetap utuh di
-- daftar tanpa tanda apa pun. Draft yang sama bisa dikonversi berkali-kali
-- dan menghasilkan pembelian ganda — kekeliruan yang baru ketahuan saat
-- rekonsiliasi, ketika satu tagihan sudah terhitung dua kali.
--
-- `purchaseID` disimpan agar jejaknya dapat ditelusuri: draft ini menjadi
-- pembelian yang mana.
-- ===========================================================================

ALTER TABLE `purchase_draft`
  ADD COLUMN `convertedAt` DATETIME NULL DEFAULT NULL AFTER `deletedBy`,
  ADD COLUMN `convertedBy` INT      NULL DEFAULT NULL AFTER `convertedAt`,
  ADD COLUMN `purchaseID`  INT      NULL DEFAULT NULL AFTER `convertedBy`;

ALTER TABLE `purchase_draft`
  ADD INDEX `ix_purchase_draft_converted` (`convertedAt`);

-- Baris lama dibiarkan NULL: sistem memang belum pernah mencatat konversi,
-- jadi tidak ada yang bisa disimpulkan tentangnya.
--
-- Draft lama yang sebenarnya SUDAH dikonversi akan tetap muncul di daftar
-- tertunda. Untuk menemukannya, cari draft yang nomor PO-nya sudah dipakai
-- sebuah pembelian:
--
--     SELECT d.id, d.purchaseOrderName, d.date, p.id AS purchaseID
--     FROM purchase_draft d
--     JOIN purchases p ON p.purchaseOrderName = d.purchaseOrderName
--                     AND p.isDelete = 0
--     WHERE d.isDelete = 0 AND d.convertedAt IS NULL;
--
-- Periksa hasilnya sebelum menandai — nomor PO yang sama bisa saja memang
-- dipakai dua tagihan berbeda. Untuk yang sudah dipastikan:
--
--     UPDATE purchase_draft SET convertedAt = NOW(), convertedBy = 1,
--            purchaseID = <id_pembelian>
--     WHERE id = <id_draft>;
