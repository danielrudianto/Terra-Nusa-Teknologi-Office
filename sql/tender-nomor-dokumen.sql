-- =====================================================================
-- Nomor dokumen tender: T-AKN-001-IX-2026
-- =====================================================================
--
-- SEBELUM: `tenders.number` sebuah INT yang naik terus (1, 2, 3, ...), dan
-- itulah yang tampil di layar. Nomor dokumen yang cuma "3" tidak dapat
-- dirujuk di luar sistem — di percakapan WhatsApp, di berkas cetak, di surat
-- ke pemasok, "tender 3" tidak menyebut tahun, tidak menyebut perusahaan, dan
-- tahun depan akan ada "tender 3" yang lain.
--
-- SESUDAH: `T-AKN-001-IX-2026`
--            |      |   |   `- tahun
--            |      |   `----- bulan, angka Romawi
--            |      `--------- urutan dalam TAHUN itu
--            `---------------- tetap
--
-- Urutannya MENGULANG TIAP TAHUN. Karena itulah tahun ikut di nomornya;
-- tanpa pengulangan, bagian tahun cuma hiasan.
--
-- ---------------------------------------------------------------------
-- JALANKAN BERURUTAN. Bagian 1 TIDAK idempoten.
-- ---------------------------------------------------------------------
--
-- `ALTER TABLE ... ADD COLUMN` di MySQL akan GAGAL bila kolomnya sudah ada
-- (galat 1060). Itu bukan masalah — artinya bagian ini sudah pernah
-- dijalankan; lanjutkan ke bagian 2.


-- ---------------------------------------------------------------------
-- 0. PERIKSA DULU — aman dijalankan berkali-kali
-- ---------------------------------------------------------------------
SELECT
  COUNT(*)                                             AS total_tender,
  SUM(CASE WHEN isDelete = 1 THEN 1 ELSE 0 END)        AS terhapus,
  MIN(YEAR(date))                                      AS tahun_awal,
  MAX(YEAR(date))                                      AS tahun_akhir,
  SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END)        AS tanpa_tanggal
FROM tenders;

-- `tanpa_tanggal` HARUS 0. Baris tanpa tanggal tidak dapat diberi bulan dan
-- tahun, dan bagian 2 akan menghasilkan NULL untuk baris itu — nomor dokumen
-- kosong yang tidak akan pernah terisi sendiri. Kalau angkanya bukan 0,
-- BERHENTI dan beri tahu saya.


-- ---------------------------------------------------------------------
-- 1. KOLOM BARU
-- ---------------------------------------------------------------------
ALTER TABLE tenders
  ADD COLUMN documentNumber VARCHAR(32) NULL AFTER number;


-- ---------------------------------------------------------------------
-- 2. ISI ULANG: urutan per tahun + nomor dokumennya
-- ---------------------------------------------------------------------
--
-- Baris TERHAPUS ikut dihitung dan ikut diberi nomor.
--
-- Itu disengaja, dan aturannya sudah ada sebelum ini: nomor tender tidak
-- pernah dipakai ulang. Kalau yang terhapus dilewati, tender berikutnya akan
-- mewarisi nomor milik tender yang pernah ada — dan rujukan lama ke nomor itu
-- diam-diam menunjuk dokumen yang berbeda.
--
-- Diurutkan `date, id`: tanggal dokumennya yang menentukan, bukan urutan
-- pencatatannya. `id` cuma pemutus seri untuk tanggal yang sama, supaya
-- hasilnya sama persis setiap kali dijalankan.

UPDATE tenders t
JOIN (
  SELECT
    id,
    YEAR(date) AS thn,
    ELT(
      MONTH(date),
      'I', 'II', 'III', 'IV', 'V', 'VI',
      'VII', 'VIII', 'IX', 'X', 'XI', 'XII'
    ) AS bln,
    ROW_NUMBER() OVER (PARTITION BY YEAR(date) ORDER BY date, id) AS urut
  FROM tenders
  WHERE date IS NOT NULL
) u ON u.id = t.id
SET
  t.number = u.urut,
  t.documentNumber = CONCAT(
    'T-AKN-', LPAD(u.urut, 3, '0'), '-', u.bln, '-', u.thn
  );

-- Butuh window function (`ROW_NUMBER`): MySQL 8.0+ atau MariaDB 10.2+.
-- Kalau server menolaknya, beri tahu saya — versinya lebih tua dan
-- pengisiannya harus lewat cara lain.


-- ---------------------------------------------------------------------
-- 3. INDEKS UNIK
-- ---------------------------------------------------------------------
--
-- Dipasang SESUDAH pengisian, bukan sebelum: kalau ada tender kembar yang
-- tidak terduga, galatnya muncul di sini dengan datanya sudah terisi dan
-- dapat diperiksa — bukan menggagalkan pengisiannya di tengah jalan.
--
-- Kalau langkah ini gagal dengan "Duplicate entry", JANGAN dipaksa. Jalankan
-- pemeriksaan di bagian 4 dan kirimkan hasilnya kepada saya.

ALTER TABLE tenders
  ADD UNIQUE INDEX uq_tenders_documentNumber (documentNumber);


-- ---------------------------------------------------------------------
-- 4. PERIKSA HASILNYA
-- ---------------------------------------------------------------------

-- 4a. Tidak boleh ada yang kosong.
SELECT COUNT(*) AS nomor_kosong
FROM tenders
WHERE documentNumber IS NULL OR documentNumber = '';

-- 4b. Tidak boleh ada yang kembar.
SELECT documentNumber, COUNT(*) AS jumlah
FROM tenders
GROUP BY documentNumber
HAVING COUNT(*) > 1;

-- 4c. Urutan per tahun harus rapat 1..N (tidak ada lompatan).
SELECT
  YEAR(date) AS tahun,
  COUNT(*)   AS jumlah,
  MIN(number) AS terkecil,
  MAX(number) AS terbesar
FROM tenders
WHERE date IS NOT NULL
GROUP BY YEAR(date)
ORDER BY tahun;
-- `terkecil` = 1 dan `terbesar` = `jumlah` untuk setiap tahun.

-- 4d. Lihat sepuluh yang terbaru.
SELECT id, number, documentNumber, date, name
FROM tenders
ORDER BY date DESC, id DESC
LIMIT 10;
