from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    JSON,
)
from utils.database import metadata

"""
Data pribadi karyawan yang TIDAK berubah tiap tahun.

Dipisah dari `employees` dengan sengaja. Tabel `employees` dibaca hampir
setiap kali slip gaji, aktivitas, dan agenda disusun; menambahkan dua puluh
kolom data pribadi ke sana membuat setiap kueri itu ikut membawa data yang
tidak dipakainya — dan data paling sensitif di sistem ikut terbaca di
tempat-tempat yang tidak memerlukannya.

Dipisah pula dari formulir berkala. Tempat lahir, pendidikan formal, dan
pengalaman kerja sebelum masuk tidak berubah; meminta karyawan mengisinya
ulang setiap tahun membuat mereka mengetik ulang sebagian besar formulir,
dan yang terjadi kemudian adalah pengisian asal supaya cepat selesai.
"""

employee_profiles_table = Table(
    "employee_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Satu karyawan satu profil.
    #
    # `unique=True` dinyatakan DI SINI, bukan hanya di basis data: tanpa itu
    # `cek_skema` melaporkannya sebagai indeks asing pada setiap deploy, dan
    # temuan yang sebenarnya disengaja membuat temuan lain ikut diabaikan.
    Column(
        "employeeID",
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
        unique=True,
    ),
    # ---- identitas ----
    Column("birthPlace", String(100), nullable=True),
    Column("gender", String(10), nullable=True),  # 'L' | 'P'
    Column("bloodType", String(5), nullable=True),
    Column("religion", String(30), nullable=True),
    Column("maritalStatus", String(20), nullable=True),
    # `npwp` TIDAK ada di sini.
    #
    # Sejak NIK dijadikan NPWP, untuk orang pribadi keduanya adalah nomor
    # yang sama — dan NIK sudah tersimpan di `employees.nik`. Menyediakan
    # kotak terpisah membuat orang mengetik nomor yang sama dua kali, lalu
    # salah satunya tertinggal saat diperbarui.
    #
    # Berbeda dengan NPWP pemasok, klien, dan lawan transaksi: badan usaha
    # tetap punya NPWP tersendiri, dan kolomnya di tabel masing-masing tetap
    # diperlukan.
    # Nama orang tua.
    #
    # Ditaruh di profil, bukan di formulir berkala: nama ibu kandung tidak
    # pernah berubah, dan menanyakannya tiap tahun hanya menambah panjang
    # formulir tanpa menambah satu pun informasi baru.
    #
    # Nama ibu kandung kerap dipakai bank dan BPJS sebagai pertanyaan
    # verifikasi, sehingga wajar diminta sekali di awal.
    Column("motherName", String(150), nullable=True),
    Column("fatherName", String(150), nullable=True),
    Column("citizenship", String(50), nullable=True),
    Column("ethnicity", String(50), nullable=True),
    # Tinggi dan berat badan.
    #
    # Diminta pada pekerjaan lapangan: sebagian alat pelindung diri dan
    # perlengkapan kerja diadakan menurut ukuran, dan menanyakannya
    # belakangan berarti pengadaannya tertunda.
    Column("heightCm", Integer, nullable=True),
    Column("weightKg", Integer, nullable=True),
    # ---- identitas kependudukan ----
    #
    # `ktpNumber` TIDAK ada di sini: NIK adalah nomor KTP itu sendiri, dan
    # sudah tersimpan di `employees.nik` — dipakai slip gaji. Menyimpannya
    # dua kali membuat keduanya pasti berbeda suatu saat, dan tidak ada yang
    # tahu mana yang benar.
    #
    # Alamat KTP tetap di sini karena memang berbeda dari alamat tinggal
    # yang ada di `employees.address`.
    Column("ktpAddress", String(500), nullable=True),
    Column("ktpValidUntil", Date(), nullable=True),
    # SIM disimpan sebagai JSON, bukan tiga kolom terpisah.
    #
    # Golongannya bisa bertambah (A, B1, B2, C, D) dan tidak semua orang
    # punya semuanya. Tiga kolom tetap berarti golongan baru memerlukan
    # migrasi tabel, sedangkan yang tidak punya menyisakan kolom kosong.
    Column("drivingLicenses", JSON, nullable=True),
    # Alamat tinggal, nomor HP, dan surel TIDAK ada di sini.
    #
    # Ketiganya sudah ada di `employees` (`address`, `phoneNumber`, `email`)
    # dan dipakai di luar profil. Menyediakan kotak keduanya membuat orang
    # mengisi hal yang sama dua kali — lalu memperbarui salah satunya saja.
    #
    # Yang tersisa hanya status kepemilikan rumah dan telepon rumah, karena
    # keduanya memang tidak punya tempat lain.
    Column("homeOwnership", String(30), nullable=True),
    Column("homePhone", String(30), nullable=True),
    # ---- jaminan sosial ----
    Column("bpjsKesehatan", String(30), nullable=True),
    Column("bpjsKetenagakerjaan", String(30), nullable=True),
    # ---- rekening ----
    Column("bankName", String(100), nullable=True),
    Column("bankAccountName", String(100), nullable=True),
    Column("bankAccountNumber", String(50), nullable=True),
    # Daftar berulang disimpan sebagai JSON.
    #
    # Pendidikan formal dan pengalaman kerja jumlahnya berbeda tiap orang dan
    # selalu dibaca utuh, tidak pernah disaring per baris. Tabel tersendiri
    # untuk keduanya menambah dua join pada setiap pembacaan tanpa ada kueri
    # yang benar-benar memerlukannya.
    Column("formalEducation", JSON, nullable=True),
    Column("workExperience", JSON, nullable=True),
    # Kemampuan bahasa: daftar {bahasa, lisan, tulisan}.
    Column("languages", JSON, nullable=True),
    # Susunan keluarga seperti kartu keluarga: {hubungan, nama, lahir,
    # pendidikan, pekerjaan}. Anak dan saudara jumlahnya berbeda tiap orang,
    # sehingga daftar — bukan kolom tetap.
    Column("familyMembers", JSON, nullable=True),
    Column("createdAt", DateTime(), nullable=False),
    Column("createdBy", Integer, ForeignKey("users.id"), nullable=False),
    Column("updatedAt", DateTime(), nullable=True),
    Column("updatedBy", Integer, ForeignKey("users.id"), nullable=True),
)
