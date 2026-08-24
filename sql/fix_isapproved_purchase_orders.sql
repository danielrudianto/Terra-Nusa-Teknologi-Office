-- Selaraskan `isApproved` dengan `status` pada purchase order yang sudah ada.
--
-- Persetujuan hanya menulis kolom `status`; `isApproved`, `approvedBy`, dan
-- `approvedAt` tidak pernah tersentuh. Akibatnya dokumen yang sudah disetujui
-- di layar tetap tercatat belum disetujui, dan blok tanda tangannya tercetak
-- TANPA nama penyetuju — tanpa galat apa pun.
--
-- Kode sudah diperbaiki; berkas ini memperbaiki yang terlanjur.

-- 1. Lihat dulu apa yang akan berubah.
SELECT
  COUNT(*) AS akan_diperbaiki,
  MIN(date) AS dokumen_terlama,
  MAX(date) AS dokumen_terbaru
FROM purchase_orders
WHERE status = 'approved'
  AND isDelete = 0
  AND (isApproved = 0 OR isApproved IS NULL);

-- 2. Siapa yang akan tercatat sebagai penyetuju.
--
-- Diambil dari JEJAK AUDIT, bukan ditebak: `update_status` mencatat siapa
-- yang menekannya, dan itu satu-satunya keterangan yang benar tentang siapa
-- sebenarnya menyetujui dokumen tersebut.
SELECT
  po.id,
  po.number,
  po.date,
  (SELECT a.userID
     FROM audit_logs a
    WHERE a.entity = 'purchase_orders'
      AND a.entityID = po.id
      AND a.action = 'update_status'
    ORDER BY a.id DESC
    LIMIT 1) AS penyetuju_dari_audit
FROM purchase_orders po
WHERE po.status = 'approved'
  AND po.isDelete = 0
  AND (po.isApproved = 0 OR po.isApproved IS NULL)
ORDER BY po.id;

-- 3. Terapkan.
--
-- `approvedAt` diambil dari waktu jejak auditnya, bukan NOW(): dokumen yang
-- disetujui minggu lalu tidak boleh tercatat disetujui hari ini.
UPDATE purchase_orders po
SET
  po.isApproved = 1,
  po.approvedBy = COALESCE(
    (SELECT a.userID
       FROM audit_logs a
      WHERE a.entity = 'purchase_orders'
        AND a.entityID = po.id
        AND a.action = 'update_status'
      ORDER BY a.id DESC
      LIMIT 1),
    po.createdBy
  ),
  po.approvedAt = COALESCE(
    (SELECT a.createdAt
       FROM audit_logs a
      WHERE a.entity = 'purchase_orders'
        AND a.entityID = po.id
        AND a.action = 'update_status'
      ORDER BY a.id DESC
      LIMIT 1),
    po.createdAt
  )
WHERE po.status = 'approved'
  AND po.isDelete = 0
  AND (po.isApproved = 0 OR po.isApproved IS NULL);

-- 4. Pastikan hasilnya; harus 0 baris.
SELECT COUNT(*) AS masih_tidak_selaras
FROM purchase_orders
WHERE status = 'approved'
  AND isDelete = 0
  AND (isApproved = 0 OR isApproved IS NULL);
