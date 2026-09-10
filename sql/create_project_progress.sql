-- ============================================================================
-- Kemajuan pekerjaan proyek, dicatat per tanggal
-- ============================================================================
--
-- Laporan proyek sampai sekarang hanya dapat menjawab satu pertanyaan: berapa
-- biaya yang sudah keluar dibanding nilai kontrak. Itu setengah jawaban.
-- Biaya 60% belum tentu buruk bila pekerjaannya juga sudah 60% — dan sangat
-- buruk bila pekerjaannya baru 30%. Tanpa angka kemajuan, keduanya terbaca
-- persis sama.
--
-- Tabel ini menyediakan setengah yang hilang. Isinya sengaja hanya apa yang
-- benar-benar dicatat orang di lapangan: tanggal, persen, dan keterangan.
--
-- Dijalankan MANUAL ke basis data, seperti seluruh perubahan skema di folder
-- ini. Setelah itu `scripts/cek_skema.py` harus bersih sebelum layanan
-- di-restart.
-- ============================================================================

CREATE TABLE IF NOT EXISTS `project_progress` (
  `id`          INT            NOT NULL AUTO_INCREMENT,

  -- Foreign key SUNGGUHAN, berbeda dari purchases dan kawan-kawannya yang
  -- menyambung lewat teks `projectName`. Tabel ini baru, jadi tidak ada data
  -- lama berkode tidak seragam yang perlu ditampung — persis alasan
  -- `project_contracts` juga sudah memakai foreign key.
  `projectID`   INT            NOT NULL,

  -- Tanggal KEADAAN yang dilaporkan, bukan tanggal pencatatannya. Progress
  -- kerap dicatat beberapa hari setelah opnamenya; memakai tanggal input
  -- menggeser seluruh kurva ke kanan dan membuatnya tidak sejajar dengan
  -- kurva biaya, yang memakai tanggal dokumen.
  `date`        DATE           NOT NULL,

  -- Persen kemajuan KUMULATIF, 0-100 — bukan tambahan per periode. Yang
  -- dibaca orang di lapangan adalah "sudah berapa persen"; menjumlahkan
  -- tambahan membuat satu baris keliru merusak seluruh sisa kurvanya.
  --
  -- Boleh turun. Pekerjaan yang harus diulang memang mengurangi kemajuan,
  -- dan memaksanya naik terus menyembunyikan persoalan yang paling mahal.
  `percentage`  DECIMAL(6,2)   NOT NULL,

  `description` VARCHAR(500)   NULL,

  `createdAt`   DATETIME       NOT NULL,
  `createdBy`   INT            NOT NULL,
  `updatedAt`   DATETIME       NULL DEFAULT NULL,
  `updatedBy`   INT            NULL DEFAULT NULL,
  `isDelete`    TINYINT(1)     NOT NULL DEFAULT 0,
  `deletedAt`   DATETIME       NULL DEFAULT NULL,
  `deletedBy`   INT            NULL DEFAULT NULL,

  PRIMARY KEY (`id`),

  -- Riwayat SELALU dibaca per proyek dan diurutkan menurut tanggal; indeks
  -- gabungan inilah bentuk yang dipakai kuerinya.
  KEY `idx_project_progress_project_date` (`projectID`, `date`),

  CONSTRAINT `fk_project_progress_project`
    FOREIGN KEY (`projectID`) REFERENCES `projects` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- SENGAJA TIDAK ADA indeks unik pada (projectID, date).
--
-- Baris yang dihapus tetap tersimpan (`isDelete`), sehingga indeks unik akan
-- menolak pencatatan ulang pada tanggal yang sama setelah baris pertamanya
-- dihapus — galat 500 yang tidak menyebut sebabnya, persis jenis "UNIK ASING"
-- yang sudah diperingatkan `cek_skema.py`. Yang menjaga tanggal ganda adalah
-- controller, yang dapat membedakan baris hidup dari baris terhapus.

-- Pemeriksaan.
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_progress';
