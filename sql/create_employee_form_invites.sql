-- Undangan pengisian formulir karyawan.
--
-- Satu tautan sekali kirim untuk satu karyawan. Karyawan mengisi datanya
-- sendiri tanpa akun dan tanpa masuk; tokennya yang menandai siapa dia —
-- bukan nama atau NIK yang diketik sendiri, yang satu huruf salah saja
-- membuat jawabannya tidak tertaut ke siapa pun.

CREATE TABLE `employee_form_invites` (
  `id` int NOT NULL AUTO_INCREMENT,
  `employeeID` int NOT NULL,
  `versionID` int NOT NULL,

  -- Token acak, bukan urutan.
  --
  -- Nomor berurutan dapat ditebak: yang menerima tautannya sendiri tinggal
  -- mengubah satu angka untuk membuka data rekannya. Panjangnya menampung
  -- 32 byte acak yang disandikan URL-safe.
  `token` varchar(64) NOT NULL,

  -- Batas waktu, tiga hari sejak diterbitkan.
  --
  -- Tautan yang tidak pernah kedaluwarsa akan tersimpan di riwayat pesan dan
  -- grup — dan siapa pun yang menemukannya kelak dapat membuka data pribadi
  -- orang tersebut.
  `expiresAt` datetime NOT NULL,

  -- Waktu pengisian TERAKHIR, bukan penanda sekali pakai.
  --
  -- Orang kerap menyadari ada yang keliru setelah menekan kirim; token yang
  -- langsung mati memaksanya menghubungi HRD untuk satu huruf.
  `usedAt` datetime DEFAULT NULL,

  `createdAt` datetime NOT NULL,
  `createdBy` int NOT NULL,
  `isDelete` tinyint(1) NOT NULL DEFAULT '0',

  PRIMARY KEY (`id`),

  -- Token unik; dua undangan bertoken sama membuat yang kedua membuka data
  -- orang pertama.
  UNIQUE KEY `uq_invite_token` (`token`),

  -- Pencarian selalu lewat token, dan tabel ini bertambah satu baris setiap
  -- undangan diterbitkan.
  KEY `idx_invite_employee` (`employeeID`),
  KEY `idx_invite_version` (`versionID`),
  KEY `idx_invite_created_by` (`createdBy`),

  CONSTRAINT `fk_invite_employee` FOREIGN KEY (`employeeID`)
    REFERENCES `employees` (`id`),
  CONSTRAINT `fk_invite_version` FOREIGN KEY (`versionID`)
    REFERENCES `employee_form_versions` (`id`),
  CONSTRAINT `fk_invite_created_by` FOREIGN KEY (`createdBy`)
    REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
