"""
Modul yang menjadi wilayah tiap divisi.

Ini KEBIJAKAN, bukan aturan teknis — susunannya menentukan siapa melihat apa,
sehingga ubahannya perlu sepengetahuan pemilik proses.

Cara membacanya bersama matriks level:

    divisi -> modul apa yang menjadi urusannya
    level  -> sejauh apa yang boleh dilakukan pada modul itu

Keduanya harus terpenuhi. Seorang level 3 di FAT boleh menghapus data
pembelian, tetapi tidak menyentuh modul procurement; sebaliknya level 3 di
procurement boleh menghapus purchase order, tetapi tidak membuka pembukuan.

Pemilik usaha (level 5) tidak dibatasi divisi, dan memang tidak perlu diberi
satu pun: batas wilayah hanya berlaku bagi yang punya divisi.

Modul yang tidak tercantum pada divisi mana pun hanya dapat dibuka lewat izin
khusus per pengguna.
"""

# Dipakai lintas divisi dan tidak menyimpan data yang perlu dibatasi.
UMUM = {
    "dashboard",
    "calendar",
    "user_avatar",
    # Proyek dibaca hampir setiap divisi: kodenya dipakai di purchase order,
    # pembelian, reimbursement, dan faktur penjualan. Menutupnya per divisi
    # membuat orang tidak dapat memastikan kode yang sedang ia ketik benar.
    #
    # Aman berada di sini karena yang dibatasi bukan divisinya melainkan
    # levelnya: matriks menetapkan baca 1, tetapi buat dan ubah 4 — jadi
    # semua orang melihat daftarnya, hanya sedikit yang bisa mengubahnya.
    "project",
    # Riwayat aktivitas dibaca semua divisi, karena isinya sudah dibatasi
    # di rutenya: di bawah level 5 yang terlihat hanya aktivitas sendiri.
    #
    # Tanpa ada di sini, pengguna yang punya divisi akan tetap terkunci
    # meski levelnya mencukupi — dan yang tidak punya divisi justru bisa
    # membukanya. Kebalikan dari yang dimaksud.
    "audit_log",
}

DEPARTMENT_MODULES: dict[str, set[str]] = {
    # Keuangan, pembukuan, dan perpajakan digabung dalam satu divisi karena
    # ketiganya menyentuh data yang sama: satu transaksi dicatat, dibayar,
    # lalu dilaporkan pajaknya oleh orang-orang yang duduk berdekatan.
    "fat": UMUM
    | {
        # pembukuan
        "purchase",
        # Draft dibaca keuangan untuk mencocokkan tagihan yang belum lengkap
        # berkasnya; pembuatannya tetap pekerjaan procurement.
        "purchase_draft",
        "expenses",
        "expense_opponent",
        "income",
        "sales_invoice",
        "reimbursement",
        "client",
        "supplier",
        "purchase_order",
        # keuangan
        "bank",
        "payment_incoming",
        "payment_outgoing",
        "interpayment",
        "loan",
        # perpajakan
        "tax",
        # Posisi keuangan hanya untuk FAT; level 4 masih dijaga matriks.
        "finance_status",
        # Slip gaji diperlukan untuk menghitung PPh 21 setiap bulan.
        # Tanpanya, pelaporan pajak tidak dapat diselesaikan di sistem dan
        # angkanya akan diminta lewat jalur lain — yang justru tidak
        # meninggalkan jejak sama sekali.
        "salary_slip",
    },
    "hrd": UMUM
    | {
        "employees",
        "salary_slip",
        # Profil pribadi dan formulir keadaan berkala; isinya susunan
        # keluarga, riwayat kesehatan, dan kontak darurat.
        "employee_profile",
        "employee_form",
        # Ujian rekrutmen: bank soal, pelamar, dan penilaian jawabannya.
        #
        # Isinya data pribadi orang yang bahkan belum menjadi karyawan —
        # alamat, tanggal lahir, dan jawaban yang menentukan diterima atau
        # tidaknya. Wilayah HRD, bukan wilayah siapa pun yang kebetulan
        # levelnya tinggi.
        "hr_recruitment",
    },
    # Divisinya sudah ada, modulnya belum.
    #
    # Sengaja dibiarkan kosong: pekerjaan engineering — metode kerja, volume
    # per titik, progres lapangan, data hasil uji — belum ada satu pun di
    # sistem ini. Mengisinya dengan modul alat dan pembelian hanya membuat
    # peta wilayah ini terbaca seolah sudah benar, padahal isinya logistik
    # milik divisi lain.
    #
    # PERHATIAN: selama masih kosong, jangan tempatkan siapa pun di divisi
    # ini. Yang punya divisi dibatasi wilayahnya, sehingga orangnya hanya
    # akan melihat beranda dan kalender. Biarkan tanpa divisi dahulu — tanpa
    # divisi berarti tidak dibatasi, dan aksesnya mengikuti levelnya.
    "engineering": set(UMUM),
    "procurement": UMUM
    | {
        "purchase_order",
        "purchase_draft",
        "supplier",
        "master_item",
        "master_equipment",
        "asset",
        "client",
    },
}

# Nama yang ditampilkan di layar.
DEPARTMENT_LABELS: dict[str, str] = {
    "fat": "Finance, Accounting & Taxing",
    "hrd": "Human Resource Department",
    "engineering": "Engineering",
    "procurement": "Procurement & Purchasing",
}


def modules_for(departments: set[str]) -> set[str]:
    """
    Gabungan modul dari seluruh divisi yang dipegang seseorang.

    Bergabung, bukan beririsan: orang yang menangani dua wilayah melihat
    keduanya.
    """
    hasil: set[str] = set()
    for d in departments or ():
        # Kode diseragamkan sebelum dicocokkan.
        #
        # Pencocokan langsung membuat "FAT" atau " fat" menghasilkan NOL
        # modul — bukan sebagian, melainkan seluruhnya — sehingga pengguna
        # terkunci dari hampir semua menu tanpa pesan apa pun. Layar memang
        # memvalidasi kodenya, tetapi baris yang disisipkan lewat SQL saat
        # penyiapan data tidak melewati validasi itu.
        kunci = (d or "").strip().lower()
        hasil |= DEPARTMENT_MODULES.get(kunci, set())
    return hasil
