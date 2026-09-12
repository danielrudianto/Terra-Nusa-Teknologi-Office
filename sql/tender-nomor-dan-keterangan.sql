-- Tender: nomor penawaran pemasok, dan keterangan yang dapat dibandingkan
-- berdampingan.
--
-- Dua hal, satu berkas, karena keduanya menyangkut tabel penawaran dan
-- diterapkan bersamaan.
--
-- ----------------------------------------------------------------------
-- 1. Nomor penawaran dari pemasok
-- ----------------------------------------------------------------------
--
-- Nomor yang dicantumkan pemasok pada surat penawarannya sendiri — bukan
-- nomor yang dibuat sistem ini. Dipakai menunjuk dokumen aslinya saat
-- keputusannya ditinjau kembali, dan saat menanyakan kembali ke pemasoknya.
--
-- BOLEH KOSONG: sebagian penawaran datang lewat WhatsApp tanpa nomor sama
-- sekali, dan memaksakannya membuat yang mencatat mengarang nomor.

ALTER TABLE tender_quotes
    ADD COLUMN quotationNumber VARCHAR(100) NULL AFTER supplierID;

-- ----------------------------------------------------------------------
-- 2. Keterangan pemasok, per kategori
-- ----------------------------------------------------------------------
--
-- Sebelumnya SATU kolom teks bebas (`tender_quotes.notes`), dan seluruh
-- keterangan menumpuk di dalamnya: syarat pembayaran, spesifikasi pengganti,
-- ketentuan mob-demob, masa berlaku. Pada layar perbandingan ia menjadi satu
-- sel sepanjang paragraf per pemasok — dan justru di situlah perbandingan
-- yang paling menentukan seharusnya terjadi.
--
-- Yang membandingkan "uang muka 70%" milik satu pemasok dengan "pelunasan
-- setelah 200 jam" milik pemasok lain harus membaca dua paragraf utuh lebih
-- dulu untuk menemukan kalimat yang sebanding. Dengan kategori, keduanya
-- berada pada BARIS YANG SAMA dan dapat dibaca berdampingan.
--
-- Kategorinya TETAP, empat:
--
--   pembayaran   uang muka, termin, syarat pelunasan
--   teknis       spesifikasi, merek, kapasitas, mutu
--   nonteknis    mob-demob, masa berlaku, administrasi
--   lainnya      yang tidak masuk ketiganya
--
-- Tetap, bukan bebas: kategori yang diketik sendiri menghasilkan "Pembayaran"
-- dan "pembayaran" sebagai dua baris terpisah pada tabel yang seluruh gunanya
-- menyejajarkan hal yang sama.
--
-- `tender_quotes.notes` SENGAJA TIDAK DIHAPUS dan tidak dipindahkan lewat
-- skrip. Penawaran lama tetap membawa teksnya di sana, dan repository
-- menampilkannya sebagai keterangan berkategori `lainnya` selama belum ada
-- baris di tabel ini. Begitu penawaran itu disunting dan keterangannya
-- dicatat per kategori, kolom lamanya dikosongkan — sehingga tidak pernah ada
-- dua sumber yang menampilkan hal berbeda pada waktu yang sama.
--
-- Memindahkannya lewat UPDATE massal akan menggandakan isinya bila berkas ini
-- dijalankan dua kali, dan berkas skema di repo ini memang diterapkan tangan.

CREATE TABLE IF NOT EXISTS tender_quote_notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quoteID INT NOT NULL,
    -- pembayaran | teknis | nonteknis | lainnya
    category VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    -- Urutan tampil di dalam satu kategori; satu kategori boleh berisi lebih
    -- dari satu keterangan.
    sortOrder INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_tender_quote_notes_quote
        FOREIGN KEY (quoteID) REFERENCES tender_quotes (id),
    INDEX idx_tender_quote_notes_quote (quoteID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ----------------------------------------------------------------------
-- Catatan penutupan tender tanpa pemenang
-- ----------------------------------------------------------------------
--
-- TIDAK perlu kolom baru. `tenders` sudah punya `winnerQuoteID` yang boleh
-- NULL, `winnerReason`, `decidedAt`, dan `decidedBy`.
--
-- Tender yang ditutup tanpa pemenang tersimpan sebagai `status = 'selesai'`
-- dengan `winnerQuoteID` NULL dan alasannya di `winnerReason` — berbeda dari
-- `status = 'batal'`, yang berarti tendernya dihentikan sebelum selesai.
-- Keduanya memang keadaan yang berbeda: yang satu prosesnya berjalan sampai
-- habis dan tidak ada yang dipilih, yang lain prosesnya tidak diteruskan.
