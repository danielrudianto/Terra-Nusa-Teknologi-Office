-- Riwayat perubahan profil karyawan.
--
-- Profil hanya punya SATU baris per karyawan, dan penyimpanan berikutnya
-- menimpanya. Tanpa tabel ini, satu koreksi yang keliru menghapus nilai
-- sebelumnya untuk selamanya — dan yang menyadarinya sebulan kemudian tidak
-- punya apa pun untuk dikembalikan.
--
-- Jejak audit umum tidak menggantikannya: ia sengaja hanya mencatat NAMA
-- kolom yang tersentuh, bukan isinya, karena jejak audit dibaca level 5
-- secara menyeluruh sedangkan profil dibatasi divisi HRD. Menyalin isi profil
-- ke sana membuat pembatasan wilayahnya tidak ada artinya.
--
-- Yang disimpan adalah keadaan SEBELUM perubahan. Keadaan sesudah selalu
-- dapat dibaca dari profilnya sendiri; yang hilang saat ditimpa adalah yang
-- sebelumnya.

CREATE TABLE IF NOT EXISTS `employee_profile_history` (
  `id`            INT          NOT NULL AUTO_INCREMENT,
  `profileID`     INT          NOT NULL,
  -- Disalin, tidak hanya lewat `profileID`: riwayat dibaca per karyawan, dan
  -- tanpa kolom ini setiap pembacaan memerlukan join ke profil yang isinya
  -- justru sudah berubah.
  `employeeID`    INT          NOT NULL,
  -- Seluruh isi profil sebagaimana adanya sebelum ditimpa.
  `snapshot`      JSON         NOT NULL,
  -- Kolom yang tersentuh pada penyimpanan itu; dipakai layar untuk
  -- menampilkan "apa yang berubah" tanpa membandingkan seluruh isi.
  `changedFields` JSON         NOT NULL,
  `changedAt`     DATETIME     NOT NULL,
  `changedBy`     INT          NOT NULL,
  PRIMARY KEY (`id`),
  -- Riwayat SELALU dibaca per karyawan dan diurutkan menurut waktu.
  KEY `idx_eph_employee` (`employeeID`, `changedAt`),
  KEY `idx_eph_profile` (`profileID`),
  KEY `idx_eph_changed_by` (`changedBy`),
  CONSTRAINT `fk_eph_profile` FOREIGN KEY (`profileID`)
    REFERENCES `employee_profiles` (`id`),
  CONSTRAINT `fk_eph_employee` FOREIGN KEY (`employeeID`)
    REFERENCES `employees` (`id`),
  CONSTRAINT `fk_eph_changed_by` FOREIGN KEY (`changedBy`)
    REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Pastikan tabelnya ada; harus mengembalikan satu baris.
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'employee_profile_history';
