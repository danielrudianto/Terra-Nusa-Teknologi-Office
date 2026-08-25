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

-- Dokumen yang sudah ada diberi nomor menurut URUTAN TERBITNYA per proyek:
-- yang lebih dulu dibuat mendapat nomor lebih kecil. Diurutkan dengan `id`,
-- bukan `date` — dua dokumen dapat bertanggal sama, dan `id` tidak pernah
-- kembar.
SET @proyek := '';
SET @urut := 0;

UPDATE certificate_of_payments c
JOIN (
  SELECT id,
         @urut := IF(@proyek = projectName, @urut + 1, 1) AS nomor,
         @proyek := projectName AS p
  FROM certificate_of_payments
  ORDER BY projectName, id
) AS urutan ON urutan.id = c.id
SET c.documentNumber = urutan.nomor;

-- Nama dokumen disusun ulang mengikuti format baru.
--
-- ELT dipakai sebagai ganti daftar CASE: bulannya hanya dua belas dan
-- tetap, dan CASE dua belas cabang di sini lebih panjang daripada yang
-- diterangkannya.
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
