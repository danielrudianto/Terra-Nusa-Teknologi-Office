-- Penomoran Certificate of Payment: 001-R501-VIII-2026
--
-- Angka pertama adalah urutan DOKUMEN dalam satu proyek. Ia berjalan terus
-- dan tidak pernah kembali ke 1; bulan romawi dan tahun hanya menerangkan
-- kapan berkasnya terbit.
--
-- Kolom ini SENGAJA terpisah dari `number`, yang tetap berarti "pembayaran
-- ke berapa atas SPK ini" — angka itulah yang tercetak pada lembar CoP dan
-- yang menyusun daftar akumulasi pembayaran. Menukar keduanya membuat
-- cetakan ulang dokumen lama menyatakan angka yang berbeda.

ALTER TABLE certificate_of_payments
  ADD COLUMN documentNumber INT NULL AFTER number;

-- Dokumen yang sudah ada diberi nomor menurut URUTAN TERBITNYA per proyek.
--
-- ROW_NUMBER(), bukan variabel sesi (@urut := ...). Urutan baris pada
-- derived table tidak dijamin MySQL 8 — ORDER BY di dalamnya boleh
-- diabaikan pengoptimal, dan penomorannya diam-diam menjadi acak tanpa
-- satu pun galat.
--
-- Diurutkan dengan `id`, bukan `date`: dua dokumen dapat bertanggal sama,
-- dan `id` tidak pernah kembar.
UPDATE certificate_of_payments c
JOIN (
  SELECT id,
         ROW_NUMBER() OVER (PARTITION BY projectName ORDER BY id) AS nomor
  FROM certificate_of_payments
) AS urutan ON urutan.id = c.id
SET c.documentNumber = urutan.nomor;

-- Nama dokumen disusun ulang mengikuti format baru.
--
-- ELT dipakai sebagai ganti dua belas cabang CASE: bulannya tetap dan tidak
-- akan bertambah.
UPDATE certificate_of_payments
SET name = CONCAT(
      LPAD(documentNumber, 3, '0'), '-',
      COALESCE(NULLIF(projectName, ''), '-'), '-',
      ELT(MONTH(date), 'I','II','III','IV','V','VI',
                       'VII','VIII','IX','X','XI','XII'), '-',
      YEAR(date)
    )
WHERE documentNumber IS NOT NULL
  AND date IS NOT NULL;
