-- Penomoran CoP per VENDOR + PROYEK: 002-042-R501-2026
--
-- Susunannya: [urut 3 digit]-[id vendor 3 digit]-[kode proyek]-[tahun].
-- Berbeda dari format lama [urut]-[proyek]-[bulan Romawi]-[tahun]:
--   * bulan Romawi DIHAPUS;
--   * id vendor DITAMBAHKAN (dipad tiga digit);
--   * urutannya kini per (vendor, proyek), bukan per proyek saja.
--
-- Seluruh CoP lama dinomori ulang ke format ini.

-- 1) Kolom vendor. NULL dulu; diisi backfill di langkah berikutnya.
ALTER TABLE certificate_of_payments
  ADD COLUMN supplierID INT NULL AFTER purchaseOrderID,
  ADD CONSTRAINT fk_cop_supplier
    FOREIGN KEY (supplierID) REFERENCES suppliers(id);

-- 2) Isi vendor dari SPK-nya. `purchaseOrderID` pada CoP selalu dokumen
--    INDUK, dan induk menyimpan `supplierID` langsung.
UPDATE certificate_of_payments c
JOIN purchase_orders po ON po.id = c.purchaseOrderID
SET c.supplierID = po.supplierID;

-- 3) Lepas dulu keunikan `name`.
--
-- Penomoran ulang dikerjakan baris per baris oleh MySQL, dan sebuah nama
-- baru bisa untuk sesaat sama dengan nama LAMA baris yang belum tersentuh —
-- indeks unik akan menolaknya di tengah jalan. Nama akhirnya semuanya unik
-- (urut unik dalam tiap vendor+proyek), jadi keunikan dipasang lagi setelah
-- seluruh baris ditulis ulang.
ALTER TABLE certificate_of_payments
  DROP INDEX uq_cop_name;

-- 4) Urutkan ulang documentNumber per (vendor, proyek).
--
-- ROW_NUMBER(), bukan variabel sesi: urutan derived table tidak dijamin
-- MySQL 8, dan penomorannya bisa diam-diam acak. Diurutkan `id` karena dua
-- dokumen dapat bertanggal sama tetapi `id` tidak pernah kembar.
UPDATE certificate_of_payments c
JOIN (
  SELECT id,
         ROW_NUMBER() OVER (
           PARTITION BY supplierID, projectName ORDER BY id
         ) AS nomor
  FROM certificate_of_payments
) AS urutan ON urutan.id = c.id
SET c.documentNumber = urutan.nomor;

-- 5) Tulis ulang namanya mengikuti format baru.
--
-- Vendor dan urut sama-sama dipad tiga digit; tahun dari tanggal dokumen.
UPDATE certificate_of_payments
SET name = CONCAT(
      LPAD(documentNumber, 3, '0'), '-',
      LPAD(COALESCE(supplierID, 0), 3, '0'), '-',
      COALESCE(NULLIF(projectName, ''), '-'), '-',
      YEAR(date)
    )
WHERE documentNumber IS NOT NULL
  AND date IS NOT NULL;

-- 6) Pasang lagi keunikan nama.
ALTER TABLE certificate_of_payments
  ADD CONSTRAINT uq_cop_name UNIQUE (name);
