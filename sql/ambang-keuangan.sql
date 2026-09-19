-- Pita acuan rasio keuangan.
--
-- HANYA MENYIMPAN YANG DIUBAH. Baris yang tidak ada berarti "pakai bawaan",
-- dan bawaannya hidup di kode (`AMBANG_BAWAAN`). Dua akibatnya disengaja:
--
--   * tabel ini boleh kosong sama sekali dan halamannya tetap benar — tidak
--     ada langkah penyemaian yang bila terlewat membuat seluruh pita
--     menjadi nol;
--   * menghapus satu baris MENGEMBALIKAN bawaannya, bukan menghapus
--     pitanya.
--
-- `kode` unik: satu pita per rasio, dan penyimpanan kedua atas rasio yang
-- sama menimpa, bukan menumpuk.

CREATE TABLE IF NOT EXISTS finance_thresholds (
  id         INT            NOT NULL AUTO_INCREMENT,
  kode       VARCHAR(50)    NOT NULL,
  bawah      DECIMAL(14,4)  NULL,
  atas       DECIMAL(14,4)  NULL,
  updatedAt  DATETIME       NULL,
  updatedBy  INT            NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_finance_thresholds_kode (kode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
