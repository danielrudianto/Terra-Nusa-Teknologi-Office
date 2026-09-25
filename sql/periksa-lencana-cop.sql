-- Kenapa lencana CoP dan keping "Draf" menyebut angka yang berbeda.
--
-- Keduanya menghitung hal yang BERBEDA, dan keduanya benar untuk
-- pertanyaannya masing-masing:
--
--   * Keping "Draf" di daftar  = SELURUH CoP yang BAP-nya belum disetujui,
--                                termasuk yang kamu buat sendiri.
--   * Lencana di menu          = yang menunggu KEPUTUSAN KAMU — dan kamu
--                                tidak boleh menyetujui dokumen buatanmu
--                                sendiri (kecuali level 5), ditambah CoP
--                                tahap ketiga yang menunggu persetujuan.
--
-- Ganti :uid dengan id pengguna yang melihat lencananya.

SET @uid = 1;

-- 1. Angka keping "Draf" pada daftar CoP.
SELECT COUNT(*) AS keping_draf
FROM certificate_of_payments
WHERE isDelete = 0 AND isBapApproved = 0;

-- 2. Angka lencana, dipecah menjadi dua bagian penyusunnya.
SELECT
  SUM(isDelete = 0 AND isBapApproved = 0
      AND status <> 'cancelled' AND createdBy <> @uid)              AS lencana_bagian_bap,
  SUM(isDelete = 0 AND isBapApproved = 1 AND isCopCreated = 1
      AND isApproved = 0 AND status <> 'cancelled'
      AND createdBy <> @uid)                                        AS lencana_bagian_cop
FROM certificate_of_payments;

-- 3. Selisihnya: draf yang DIBUAT SENDIRI oleh pengguna itu.
--    Inilah yang biasanya menjelaskan seluruh bedanya.
SELECT COUNT(*) AS draf_buatan_sendiri
FROM certificate_of_payments
WHERE isDelete = 0 AND isBapApproved = 0 AND createdBy = @uid;

-- 4. Kolom `status` pada CoP TIDAK PERNAH BERUBAH.
--
--    Ia hanya ditulis sekali saat dokumen dibuat, selalu 'draft'; tidak ada
--    satu pun jalur yang menuliskan 'approved' maupun 'cancelled'. Empat
--    kueri di server menyaring `status <> 'cancelled'` — penyaring yang
--    SELALU benar, jadi tidak pernah membuang apa pun.
--
--    Bukan galat hari ini. Tetapi ia terbaca seperti penjagaan yang bekerja,
--    dan bila kelak ada yang mulai menuliskan 'cancelled', perilaku empat
--    tempat itu berubah sekaligus tanpa satu pun perubahan yang tampak.
--    Kueri ini untuk memastikannya: harusnya HANYA 'draft' yang muncul.
SELECT status, COUNT(*) AS jumlah
FROM certificate_of_payments
WHERE isDelete = 0
GROUP BY status;
