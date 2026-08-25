-- Certificate of Payment yang DITAGIHKAN lewat pembelian.
--
-- Satu CoP hanya boleh menjadi dasar SATU pembelian yang aktif. Sebelum ini
-- tidak ada apa pun yang mencegah dua pembelian terbit atas progres yang
-- sama — dan yang membayar tidak punya cara mengetahui mana yang berlaku.

ALTER TABLE purchases
  ADD COLUMN certificateOfPaymentID INT NULL AFTER isCopAttached;

-- Kolom bayangan yang MENJADI NULL ketika pembeliannya dihapus.
--
-- Inilah yang membuat penjagaannya benar-benar ditegakkan basis data DAN
-- tetap mengizinkan penagihan ulang setelah pembelian yang salah dihapus:
--
--   * indeks unik MENGABAIKAN NULL, sehingga berapa pun pembelian terhapus
--     yang menunjuk CoP yang sama tidak saling bertabrakan;
--   * selama masih ada satu pembelian AKTIF, nilainya terisi dan pembelian
--     kedua atas CoP yang sama ditolak — bukan oleh pemeriksaan di kode
--     yang dapat dilewati dua permintaan bersamaan, melainkan oleh basis
--     data itu sendiri.
--
-- STORED, bukan VIRTUAL: MySQL hanya mengizinkan indeks unik pada kolom
-- turunan yang tersimpan.
ALTER TABLE purchases
  ADD COLUMN copAktif INT
    GENERATED ALWAYS AS (IF(isDelete = 0, certificateOfPaymentID, NULL)) STORED;

ALTER TABLE purchases
  ADD UNIQUE KEY uq_purchase_cop_aktif (copAktif);

-- Pencarian "pembelian mana yang menagihkan CoP ini" berjalan lewat kolom
-- aslinya, termasuk untuk yang sudah terhapus (dipakai jejak audit).
ALTER TABLE purchases
  ADD KEY idx_purchase_cop (certificateOfPaymentID);
