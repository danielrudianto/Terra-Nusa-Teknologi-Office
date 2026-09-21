-- payment_incoming.salesInvoiceID: FK menunjuk tabel yang SALAH (purchases).
--
-- Akibatnya: penerimaan atas faktur ber-id X hanya bisa disimpan bila ADA
-- pembelian ber-id X. Selama jumlah pembelian > jumlah faktur ini tidak
-- ketahuan; begitu id faktur melewati id pembelian terbesar, mencatat
-- penerimaan gagal dengan galat FK. Dan SQLAlchemy tidak mengenal hubungan
-- penerimaan <-> faktur sama sekali.
--
-- Jalankan BERURUTAN. Langkah 1 & 2 hanya membaca.

-- 1) Nama FK yang sekarang (biasanya `payment_incoming_ibfk_1`).
SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME
  FROM information_schema.KEY_COLUMN_USAGE
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME = 'payment_incoming'
   AND COLUMN_NAME = 'salesInvoiceID'
   AND REFERENCED_TABLE_NAME IS NOT NULL;

-- 2) Penerimaan yang menunjuk faktur yang tidak ada. HARUS 0 sebelum lanjut;
--    kalau tidak, FK baru ditolak MySQL (dan barisnya perlu dilihat dulu).
SELECT p.id, p.salesInvoiceID, p.date, p.amount
  FROM payment_incoming p
  LEFT JOIN sales_invoices s ON s.id = p.salesInvoiceID
 WHERE p.salesInvoiceID IS NOT NULL AND s.id IS NULL;

-- 3) Ganti FK-nya. Sesuaikan nama pada DROP dengan hasil langkah 1.
ALTER TABLE payment_incoming DROP FOREIGN KEY payment_incoming_ibfk_1;
ALTER TABLE payment_incoming
  ADD CONSTRAINT payment_incoming_sales_invoice_fk
  FOREIGN KEY (salesInvoiceID) REFERENCES sales_invoices (id);
