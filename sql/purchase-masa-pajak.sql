-- MASA PAJAK pengkreditan PPN masukan pada pembelian.
--
-- `purchases.date` adalah tanggal dokumen pembeliannya. Masa pajak adalah
-- BULAN ketika PPN masukannya dikreditkan, dan keduanya kerap berbeda:
-- pemasok menerbitkan faktur pajak bulan Juli atas invoice bulan Juni.
-- Yang menentukan dokumen masuk SPT mana adalah fakturnya.
--
-- Kolomnya BOLEH KOSONG, dan kosong berarti "ikut tanggal dokumen".
-- Itulah yang membuat migrasi ini aman: seluruh baris lama bernilai NULL,
-- sehingga laporan masa-masa yang sudah lewat tidak berubah sedikit pun
-- setelah kolomnya ditambahkan. Mengisinya dengan tebakan justru langsung
-- menjadi angka laporan yang tidak pernah diputuskan siapa pun.

ALTER TABLE purchases
  ADD COLUMN taxPeriod DATE NULL AFTER dueDate;

-- Laporan PPN menyaring dan mengelompokkan menurut COALESCE(taxPeriod, date).
-- Tanpa indeks ini, tiap pembukaan laporan memindai seluruh tabel.
--
-- Kolom turunannya disimpan (STORED) karena MySQL tidak mengizinkan indeks
-- pada kolom turunan yang tidak tersimpan.
ALTER TABLE purchases
  ADD COLUMN masaPajakEfektif DATE
    GENERATED ALWAYS AS (COALESCE(taxPeriod, date)) STORED;

ALTER TABLE purchases
  ADD KEY idx_purchase_masa_pajak (masaPajakEfektif);
