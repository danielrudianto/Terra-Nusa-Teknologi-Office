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
    "audit_log": (5, 0, 0, 0, 0),
    "bank": (3, 5, 5, 5, 0),
    "calendar": (1, 0, 0, 0, 0),
    "client": (1, 3, 3, 4, 0),
    "dashboard": (1, 0, 0, 0, 0),
    # Data karyawan diurus HRD; batas wilayahnya ditentukan divisi,
    # bukan nilai khusus.
    "employees": (1, 3, 3, 4, 0),
    "expense_opponent": (1, 3, 3, 4, 0),
    "expenses": (1, 1, 1, 2, 3),
    "income": (1, 3, 3, 4, 3),
    "interpayment": (3, 3, 3, 3, 3),
    "loan": (3, 5, 5, 5, 5),
    "master_equipment": (1, 3, 3, 4, 0),
    "master_item": (1, 3, 3, 4, 0),
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
    "purchase": (1, 1, 1, 2, 3),
    "purchase_draft": (1, 1, 1, 2, 3),
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
    "supplier": (1, 3, 3, 4, 0),
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