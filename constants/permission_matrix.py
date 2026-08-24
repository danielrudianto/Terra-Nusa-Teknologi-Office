"""
Matriks izin: level minimum tiap modul untuk tiap aksi.

Urutan nilai: (read, create, update, delete, approve)

Tingkatan:

    1  Staff               mencatat pekerjaan sehari-hari
    2  Supervisor          membetulkan kekeliruan input timnya
    3  Manager             mengelola data induk, menyetujui transaksi rutin
    4  General Manager     menghapus data induk, melihat pembukuan menyeluruh
    5  Directors & Owner   rekening, pinjaman, pengguna, jejak aktivitas

Arti nilai khusus:
    0  -> aksi tidak berlaku pada modul ini
    9  -> tidak pernah diberikan lewat level; hanya lewat izin khusus
          (tidak dipakai satu pun saat ini — dipertahankan karena mungkin
          diperlukan untuk modul yang benar-benar harus disebut per orang)

Tiga hal yang dijaga dan sebaiknya tidak diubah tanpa pertimbangan:

  * Pembayaran keluar tidak dapat disetujui oleh orang yang membuatnya.
    Aturan ini ditegakkan di controller, bukan lewat beda level — beda level
    saja tidak mencegah seorang atasan menyetujui pembayarannya sendiri.
  * Rekening bank dan pinjaman hanya level 5. Keduanya menyangkut uang
    perusahaan secara langsung.
  * Slip gaji dibatasi oleh DIVISI, bukan level. Hanya HRD dan FAT yang
    berwenang; seorang level 3 di procurement tidak melihatnya.

Level pengguna disimpan pada kolom users.authenticationLevel (1-5).
"""

ACTIONS = ("read", "create", "update", "delete", "approve")

# Aksi yang tidak berlaku / hanya lewat izin khusus.
NOT_APPLICABLE = 0
SPECIAL_ONLY = 9

MATRIX: dict[str, tuple[int, int, int, int, int]] = {
    "asset": (1, 3, 3, 4, 0),
    # Baca dibuka ke level 1, TETAPI isinya dibatasi di rutenya: di bawah
    # level 5, yang terlihat hanya aktivitas sendiri.
    #
    # Matriks ini hanya mengenal "boleh membuka halamannya atau tidak", dan
    # tidak dapat menyatakan "boleh, tetapi sebagian". Pembatasan isi karena
    # itu ada di `audit_log_routes.py` — bila kelak aturannya diubah, di sana
    # tempatnya, bukan di sini.
    "audit_log": (1, 0, 0, 0, 0),
    "bank": (3, 5, 5, 5, 0),
    "calendar": (1, 0, 0, 0, 0),
    "client": (1, 3, 3, 4, 0),
    "dashboard": (1, 0, 0, 0, 0),
    # Data karyawan diurus HRD; batas wilayahnya ditentukan divisi,
    # bukan nilai khusus.
    "employees": (1, 3, 3, 4, 0),
    # Profil pribadi karyawan dan formulir keadaan berkala.
    #
    # Isinya susunan keluarga, riwayat kesehatan, dan kontak darurat — data
    # paling pribadi yang disimpan sistem ini. Karena itu keduanya ikut
    # `MODUL_WILAYAH_MUTLAK`: hanya divisi HRD, dan tidak terbuka hanya
    # karena levelnya tinggi.
    #
    # Membaca disamakan dengan membuat (level 3): tidak ada gunanya membuka
    # pembacaan lebih lebar daripada pengisiannya, karena yang membacanya
    # tetap orang yang sama.
    "employee_profile": (3, 3, 3, 4, 0),
    "employee_form": (3, 3, 3, 4, 0),
    # Ujian rekrutmen: bank soal, pelamar, dan penilaian jawabannya.
    #
    # Ikut `MODUL_WILAYAH_MUTLAK` bersama modul karyawan lain: isinya data
    # pribadi orang yang bahkan belum menjadi karyawan, dan jawaban yang
    # menentukan diterima atau tidaknya.
    #
    # Membaca disamakan dengan membuat (level 3): yang memeriksa jawaban
    # adalah orang yang sama dengan yang mengundang pelamarnya, dan membuka
    # pembacaan lebih lebar tidak menolong siapa pun.
    #
    # Menghapus level 5: menghapus pelamar berarti menghapus jawaban dan
    # penilaiannya sekaligus — keputusan yang tidak dapat ditarik kembali.
    "hr_recruitment": (3, 3, 3, 5, 0),
    # Posisi keuangan: kas, piutang, utang, pinjaman, dan quick ratio.
    #
    # Baca level 4, dan tidak ada tindakan lain — modul ini hanya membaca,
    # tidak pernah menulis apa pun. Dibuat sebagai modul tersendiri dan
    # bukan menumpang `tax` (baca level 3) supaya batas aksesnya terbaca
    # langsung dari matriks ini, bukan tersembunyi sebagai pemeriksaan
    # tambahan di dalam rute.
    "finance_status": (4, 0, 0, 0, 0),
    "expense_opponent": (1, 3, 3, 4, 0),
    "expenses": (1, 1, 1, 2, 3),
    "income": (1, 3, 3, 4, 3),
    "interpayment": (3, 3, 3, 3, 3),
    "loan": (3, 5, 5, 5, 5),
    "master_equipment": (1, 3, 3, 4, 0),
    # Sama alasannya dengan pemasok: procurement yang pertama menemukan
    # barang baru. Mengubah tetap dibatasi — nama barang dibaca kembali oleh
    # dokumen lama lewat `item_id`, jadi menyuntingnya mengubah isi dokumen
    # yang sudah terbit.
    "master_item": (1, 1, 3, 4, 0),
    "payment_incoming": (3, 3, 3, 3, 3),
    # Persetujuan pembayaran keluar di akses 4.
    #
    # Pemisahan yang dijaga bukan jarak levelnya, melainkan bahwa yang
    # menyiapkan uang bukan yang mengizinkan. Itu ditegakkan oleh aturan
    # tersendiri di payment_outgoing_controller: pembayaran tidak dapat
    # disetujui oleh orang yang membuatnya, berapa pun levelnya.
    "payment_outgoing": (3, 3, 3, 3, 4),
    # Proyek adalah data induk, tetapi pembuatannya dibatasi akses 4.
    #
    # Kode proyek tidak dapat diubah setelah dibuat — ia satu-satunya
    # penghubung ke seluruh dokumen yang menunjuknya. Proyek yang terlanjur
    # dibuat dengan kode keliru hanya bisa dihapus, bukan diperbaiki, jadi
    # pembuatannya sengaja tidak diserahkan ke tangga level yang lebih bawah.
    #
    # Nilai kontrak ikut modul ini dan bukan modul tersendiri — yang boleh
    # mengubah nilai kontrak adalah yang boleh mengubah proyeknya. Karena itu
    # `update` disamakan dengan `create` di akses 4: menambah adendum berarti
    # mengubah nilai kontrak, dan itu bukan kewenangan setingkat di bawahnya.
    #
    # Proyek yang batal ditandai lewat `isDelete`, bukan keadaan tersendiri.
    "project": (1, 4, 4, 4, 0),
    # Pengingat pada agenda.
    #
    # Empat aksi pertama di akses 1: semua orang boleh membuat pengingatnya
    # sendiri, dan batasnya kepemilikan — hanya pembuatnya yang dapat
    # mengubah dan menghapus, berapa pun levelnya.
    #
    # `approve` dipakai untuk arti berbeda di sini: boleh membuat pengingat
    # bagi SELURUH pengguna.
    "reminder": (1, 1, 1, 1, 4),
    # Hapus di level 3, tetapi HANYA bila belum ada pembayaran.
    #
    # Menghapus pembelian ikut menghapus seluruh pembayarannya dan mencabut
    # persetujuannya. Tanpa syarat tambahan, jalur ini membatalkan pembayaran
    # yang hanya boleh disetujui level 5 — memutar aturan bahwa yang
    # menyiapkan uang bukan yang mengizinkan.
    #
    # Syarat "belum ada pembayaran" tidak dapat dinyatakan di matriks ini,
    # jadi ditegakkan di controller. Yang boleh menghapus meski pembayarannya
    # sudah ada adalah level 4 ke atas.
    "purchase": (1, 1, 1, 3, 3),
    "purchase_draft": (1, 1, 1, 2, 3),
    # Tender pengadaan.
    #
    # `approve` di level 3, terpisah dari `update` di level 1: yang mencatat
    # penawaran belum tentu yang berhak memutuskan pemenangnya — pemisahan
    # yang sama seperti pada pembayaran keluar.
    #
    # `delete` di level 2 karena tender yang pemenangnya sudah ditetapkan
    # tidak dapat dihapus sama sekali; yang terhapus hanya yang belum
    # menghasilkan keputusan.
    "tender": (1, 1, 1, 2, 3),
    # Rencana pengeluaran.
    #
    # Dibaca luas — posisi kas menyangkut seluruh divisi — tetapi hanya FAT
    # yang mencatatnya; wilayahnya dijaga `department_modules`, bukan level.
    #
    # `approve` tidak berlaku: rencana bukan keputusan yang perlu disetujui,
    # melainkan taksiran yang diperbaiki terus-menerus.
    "payment_plan": (1, 1, 1, 2, 0),
    # Certificate of Payment — berita acara progres atas sebuah SPK.
    #
    # `create` di akses 1 karena memang orang lapangan yang mengisinya:
    # dialah yang menyaksikan pekerjaannya, dan menaikkannya berarti progres
    # dicatat oleh orang yang tidak berada di sana.
    #
    # Yang menjaga bukan levelnya melainkan DIVISI-nya (engineering) beserta
    # tiga lapis di controller: yang mencatat bukan yang memeriksa, dan bukan
    # pula yang memutuskan boleh ditagihkan.
    #
    # `update` ikut di akses 1 — pembuatnya membetulkan salah ketik volumenya
    # sendiri — tetapi hanya SELAMA belum diperiksa; syarat itu tidak dapat
    # dinyatakan di matriks ini dan ditegakkan di controller.
    #
    # `approve` di akses 3, sama dengan purchase order: gerbang uang yang
    # sebenarnya tetap berada di pembayaran keluar.
    "certificate_of_payment": (1, 1, 1, 2, 3),
    "purchase_order": (1, 1, 1, 2, 3),
    "reimbursement": (1, 1, 1, 2, 3),
    # Slip gaji mengikuti tangga level seperti modul lain.
    #
    # Yang membatasi siapa boleh melihat bukan levelnya, melainkan
    # divisinya: slip gaji hanya menjadi wilayah HRD dan FAT. Bagian
    # keuangan memerlukannya untuk menghitung PPh 21 setiap bulan, dan
    # menutupnya berarti pekerjaan itu tidak dapat diselesaikan di sistem.
    "salary_slip": (3, 3, 3, 4, 5),
    "sales_invoice": (1, 1, 1, 2, 3),
    # Membuat dibuka ke level 1; mengubah dan menghapus tetap dibatasi.
    #
    # Yang pertama tahu ada pemasok baru adalah procurement, dan mereka
    # level 1. Menahannya membuat pemasok baru harus dititipkan ke orang
    # lain sebelum PO-nya dapat dibuat.
    #
    # Mengubah tetap level 3 karena akibatnya berbeda jauh: nama dan alamat
    # pemasok tercetak di setiap dokumen yang menyebutnya, sehingga satu
    # suntingan mengubah isi dokumen lama yang sudah ditandatangani.
    "supplier": (1, 1, 3, 4, 0),
    "tax": (3, 3, 3, 4, 0),
    "user": (5, 5, 5, 5, 0),
    # Foto profil dipisahkan dari modul "user": avatar tampil di hampir
    # semua layar (aktivitas, riwayat dokumen), sehingga membacanya tidak
    # bisa dibatasi level 5. Mengubahnya terbuka di level 1 karena rutenya
    # sudah menjaga sendiri bahwa seseorang hanya boleh mengubah avatarnya.
    "user_avatar": (1, 0, 1, 0, 0),
}


def required_level(module: str, action: str) -> int:
    """
    Level minimum untuk sebuah aksi.

    Modul yang tidak terdaftar dianggap milik superadmin: lebih aman menolak
    modul baru yang belum sempat dipetakan daripada membiarkannya terbuka.
    """
    if action not in ACTIONS:
        return 5
    baris = MATRIX.get(module)
    if baris is None:
        return 5
    return baris[ACTIONS.index(action)]