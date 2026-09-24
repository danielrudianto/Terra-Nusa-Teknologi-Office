-- =====================================================================
-- JENIS PENGADAAN PEMBELIAN vs PURCHASE ORDER-nya
--
-- `purchases.purchaseType` menentukan KATEGORI biaya pada laporan proyek.
-- Sampai sekarang, membetulkan nomor PO sebuah pembelian memindahkan
-- proyeknya tetapi TIDAK jenisnya — sehingga biayanya tetap terhitung di
-- kategori dokumen yang lama. Tidak ada galat; angkanya hanya duduk di
-- baris yang salah.
--
-- Perbaikan kodenya sudah dipasang: sejak sekarang jenisnya ikut berpindah
-- bersama nomor PO. Berkas ini membereskan yang sudah terlanjur.
-- =====================================================================

-- ---------------------------------------------------------------------
-- LANGKAH 1 — LIHAT. Pembelian yang jenisnya berbeda dari PO-nya.
-- ---------------------------------------------------------------------
SELECT p.id,
       p.invoiceName,
       p.date,
       p.projectName        AS proyek_pembelian,
       po.projectName       AS proyek_po,
       p.purchaseOrderName,
       p.purchaseType       AS jenis_pembelian,
       po.purchaseType      AS jenis_po,
       p.dpp
FROM purchases p
JOIN purchase_orders po
       ON po.name = p.purchaseOrderName
      AND po.isDelete = 0
WHERE p.isDelete = 0
  AND p.purchaseType <> po.purchaseType
ORDER BY p.date DESC, p.id;

-- ---------------------------------------------------------------------
-- LANGKAH 2 — CADANGKAN, lalu selaraskan.
-- Jalankan HANYA bila daftar di atas sudah dibaca.
--
-- PO-nya yang menjadi acuan: jenis pengadaan adalah sifat DOKUMENNYA,
-- dan pembelian hanya menagihkan dokumen itu.
-- ---------------------------------------------------------------------

-- CREATE TABLE purchases_tipe_backup_20260924 AS
--   SELECT id, purchaseType, projectName, purchaseOrderName
--   FROM purchases WHERE isDelete = 0;

-- UPDATE purchases p
-- JOIN purchase_orders po
--        ON po.name = p.purchaseOrderName
--       AND po.isDelete = 0
-- SET p.purchaseType = po.purchaseType,
--     p.updatedAt = NOW()
-- WHERE p.isDelete = 0
--   AND p.purchaseType <> po.purchaseType;

-- ---------------------------------------------------------------------
-- LANGKAH 3 — PERIKSA. Jalankan ulang LANGKAH 1; harus 0 baris.
-- ---------------------------------------------------------------------
