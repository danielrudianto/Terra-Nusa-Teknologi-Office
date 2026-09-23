-- ---------------------------------------------------------------------------
-- Draf pembelian: PERIODE, supaya yang menagih tahu draf mana yang mana.
--
-- Logistik lapangan memasukkan draf setiap hari, sehingga satu pemasok dapat
-- punya belasan draf dalam sebulan. Saat tagihannya dibuat, tidak ada
-- keterangan apa pun yang menyebut draf ini untuk periode yang mana — dan
-- yang membuat tagihan harus menebak, atau membuka satu per satu.
--
-- Dua kolom, keduanya BOLEH KOSONG: draf lama tidak punya periode, dan
-- memaksanya berarti seluruh draf yang sudah ada menjadi tidak sah.
-- ---------------------------------------------------------------------------
ALTER TABLE purchase_draft
  ADD COLUMN periodStart DATE NULL AFTER date,
  ADD COLUMN periodEnd   DATE NULL AFTER periodStart;

-- Penyaring daftar memakai kedua kolom ini bersama pemasok.
CREATE INDEX idx_purchase_draft_periode
  ON purchase_draft (periodStart, periodEnd);
