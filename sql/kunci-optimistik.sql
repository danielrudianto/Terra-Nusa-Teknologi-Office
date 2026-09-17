-- ---------------------------------------------------------------------------
-- Penguncian optimistik: kolom versi baris.
--
-- MASALAHNYA
--
-- Dua orang membuka dokumen yang sama, dua-duanya menyimpan. Yang terakhir
-- menang, dan pekerjaan yang pertama hilang tanpa jejak di layar — tidak ada
-- galat, tidak ada peringatan, dan yang kehilangan baru tahu ketika ia membuka
-- kembali dokumennya dan isinya bukan yang ia tulis.
--
-- Pada CoP hal ini bukan kemungkinan teoretis: alurnya empat tahap dengan dua
-- penyetuju, jadi memang dirancang untuk disentuh lebih dari satu orang.
--
-- CARA KERJANYA
--
-- Setiap baris membawa `rowVersion`. Yang menyimpan harus menyebutkan versi
-- yang ia baca; penyimpanannya hanya berlaku bila versi itu masih yang
-- terbaru:
--
--     UPDATE ... SET ..., rowVersion = rowVersion + 1
--      WHERE id = :id AND rowVersion = :versi
--
-- Bila ada yang mendahului, versinya sudah bertambah, tidak ada baris yang
-- cocok, dan penyimpanannya ditolak — bukan diam-diam menimpa.
--
-- KENAPA ANGKA, BUKAN `updatedAt`
--
-- Beberapa tabel sudah punya `updatedAt` dan menggodanya untuk dipakai. Dua
-- alasan tidak:
--
--   1. `DATETIME` di MySQL berketelitian DETIK secara bawaan. Dua penyimpanan
--      dalam detik yang sama menghasilkan nilai yang sama, jadi bentroknya
--      justru tidak terdeteksi tepat pada kasus tercepat — yang paling mungkin
--      terjadi.
--   2. `updatedAt` tidak diisi pada semua jalur penulisan. Penjaga yang
--      bergantung pada kolom yang kadang kosong adalah penjaga yang kadang
--      tidak ada.
--
-- Angka yang selalu bertambah tidak punya dua persoalan itu.
--
-- EFEK SAMPING YANG MENGUNTUNGKAN
--
-- `expense.update` sudah memeriksa `result == 0` lalu menjawab "not found".
-- Secara bawaan MySQL menghitung baris yang BERUBAH, bukan yang cocok — jadi
-- menyimpan formulir tanpa mengubah satu nilai pun menghasilkan 0, dan
-- jawabannya 404 untuk data yang sebenarnya ada. Karena `rowVersion` SELALU
-- bertambah, barisnya selalu berubah, dan hitungannya kembali dapat dipercaya.
--
-- PENERAPAN
--
--     mysql -u <pengguna> -p <basisdata> < sql/kunci-optimistik.sql
--     ./env/bin/python scripts/cek_skema.py
--     sudo systemctl restart terrabot
--
-- Aman dijalankan ulang: setiap pernyataan memeriksa dulu apakah kolomnya
-- sudah ada. `ALTER TABLE ... ADD COLUMN` yang diulang akan gagal dengan galat
-- 1060 dan menghentikan sisa berkasnya di tengah jalan — yang berarti
-- sebagian tabel terpasang dan sebagian tidak, keadaan yang jauh lebih sulit
-- ditelusuri daripada kegagalan yang bersih.
-- ---------------------------------------------------------------------------

DELIMITER //

DROP PROCEDURE IF EXISTS tambah_row_version//

CREATE PROCEDURE tambah_row_version(IN nama_tabel VARCHAR(64))
BEGIN
  DECLARE sudah INT DEFAULT 0;

  SELECT COUNT(*) INTO sudah
    FROM information_schema.COLUMNS
   WHERE TABLE_SCHEMA = DATABASE()
     AND TABLE_NAME = nama_tabel
     AND COLUMN_NAME = 'rowVersion';

  IF sudah = 0 THEN
    SET @pernyataan = CONCAT(
      'ALTER TABLE `', nama_tabel, '` ',
      'ADD COLUMN `rowVersion` INT NOT NULL DEFAULT 0'
    );
    PREPARE p FROM @pernyataan;
    EXECUTE p;
    DEALLOCATE PREPARE p;
  END IF;
END//

DELIMITER ;

-- Lima tabel, dipilih karena penyimpanannya MENIMPA SELURUH FORMULIR.
--
-- Persetujuan dan perubahan status tidak ikut: keduanya sudah dijaga
-- keadaannya sendiri — dokumen yang sudah disetujui menolak disetujui lagi —
-- jadi penimpaan diam-diam tidak mungkin terjadi lewat jalur itu.
CALL tambah_row_version('certificate_of_payments');
CALL tambah_row_version('purchases');
CALL tambah_row_version('purchase_orders');
CALL tambah_row_version('tenders');
CALL tambah_row_version('expenses');

DROP PROCEDURE IF EXISTS tambah_row_version;
