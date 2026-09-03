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
    # Pengingat agenda: milik SETIAP orang, bukan wilayah satu divisi.
    #
    # Matriksnya sudah menetapkan buat/ubah/hapus di akses 1, dan batas
    # sesungguhnya adalah KEPEMILIKAN — hanya pembuatnya yang dapat mengubah
    # dan menghapus, berapa pun levelnya. Membuat pengingat bagi SELURUH
    # pengguna dijaga terpisah lewat `approve` di akses 4.
    #
    # Tanpa ada di sini, matriks itu tidak pernah berlaku: pemeriksaan wilayah
    # divisi berjalan LEBIH DAHULU, sehingga setiap orang yang punya divisi
    # ditolak "Anda tidak memiliki akses" meski levelnya jauh mencukupi —
    # sementara yang tidak punya divisi justru bisa. Persis kebalikan dari
    # yang dimaksud, dan sama seperti yang pernah terjadi pada `audit_log`.
    "reminder",
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
        # Rencana pengeluaran: perencanaan kas adalah pekerjaan FAT.
        "payment_plan",
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
        # Aset perusahaan.
        #
        # Accounting yang mencatat perolehannya, menghitung penyusutannya, dan
        # menyesuaikan nilainya ketika dilepas — sehingga merekalah yang perlu
        # mencatat dan mengubah, bukan sekadar melihat.
        #
        # Procurement tetap memilikinya, tetapi hanya untuk dibaca; lihat
        # `DEPARTMENT_READ_ONLY` di bawah.
        "asset",
        # Certificate of payment, HANYA-BACA (lihat `DEPARTMENT_READ_ONLY`).
        #
        # FAT-lah yang menerbitkan pembelian untuk MENAGIHKAN sebuah CoP yang
        # sudah disetujui — dan formulir pembelian menawarkan "isi dari CoP"
        # hanya kepada yang boleh membaca modul ini. Tanpa CoP di wilayahnya,
        # justru divisi yang menjalankan penagihannya yang tidak melihat
        # pilihan itu, sementara engineering yang tidak membuat pembelian
        # melihatnya.
        #
        # Membuat, memeriksa, dan menyetujui CoP tetap wilayah engineering:
        # ketiganya dijaga terpisah oleh `_divisi_cop_terpenuhi` di
        # controller, sehingga hanya-baca di sini tidak membuka satu pun di
        # antaranya bagi FAT.
        "certificate_of_payment",
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
    # Divisi ini akhirnya punya modulnya sendiri.
    #
    # Sebelumnya sengaja dibiarkan kosong — pekerjaan engineering (metode
    # kerja, volume per titik, progres lapangan, data hasil uji) belum ada
    # satu pun di sistem — dengan peringatan agar tidak menempatkan siapa pun
    # di sini. Certificate of Payment adalah yang pertama: progres lapangan
    # yang dicatat orang lapangan, diperiksa engineering, lalu disetujui.
    #
    # `purchase_order` ikut, HANYA-BACA (lihat `DEPARTMENT_READ_ONLY`).
    # CoP dibuat di atas SPK: yang mengisinya harus dapat membuka SPK-nya
    # untuk memilih baris pekerjaan yang dikerjakan minggu itu. Tanpa itu ia
    # hanya melihat daftar kosong. Membuat dan mengubah PO tetap wilayah
    # procurement — di sini benar-benar hanya membaca.
    "engineering": UMUM
    | {
        "certificate_of_payment",
        "purchase_order",
    },
    "procurement": UMUM
    | {
        "purchase_order",
        "purchase_draft",
        # Tender pengadaan; wilayah procurement sepenuhnya.
        #
        # FAT sengaja TIDAK diberi: tender adalah proses memilih pemasok,
        # bukan pencatatan keuangan. Yang perlu dilihat keuangan adalah
        # purchase order yang terbit sesudahnya.
        "tender",
        "supplier",
        "master_item",
        "master_equipment",
        "asset",
        "client",
    },
    # Konsultan akuntansi & pajak — pihak LUAR perusahaan.
    #
    # Wilayahnya sengaja disusun dari kebutuhan satu pekerjaan: mencocokkan
    # angka yang dilaporkan ke kantor pajak dengan dokumen yang mendasarinya.
    # Karena itu isinya dokumen sumber dan laporannya, bukan alat kerja
    # harian — tidak ada purchase order, tender, CoP, maupun payment plan:
    # ketiganya proses internal yang tidak diperlukan untuk memeriksa
    # pelaporan pajak, dan memasukkannya berarti membuka isi perjanjian
    # dengan pemasok kepada pihak luar tanpa keperluan.
    #
    # SELURUHNYA hanya-baca — lihat `DEPARTMENT_READ_ONLY`. Ini yang
    # membedakannya dari FAT: dua divisi yang menyentuh dokumen yang sama,
    # satu mencatat dan satu memeriksa. Level tidak dapat menyatakan
    # perbedaan itu; level 3 yang cukup untuk membaca pajak sekaligus cukup
    # untuk mengubah aset, klien, dan pemasok.
    "konsultan": UMUM
    | {
        # Halaman Perpajakan — alasan utama peran ini ada.
        "tax",
        # Laba rugi konsolidasi: "versi kita" yang dicocokkan dengan
        # pembukuannya. Lihat catatan pada `laba_rugi` di matriks.
        "laba_rugi",
        # Dokumen sumber yang menjadi dasar angka pajaknya.
        "purchase",
        "expenses",
        "expense_opponent",
        "income",
        "sales_invoice",
        "reimbursement",
        # Mutasi bank TIDAK punya modul sendiri: rutenya dijaga
        # `payment_outgoing`. Tanpa modul ini, "lihat mutasi" tidak dapat
        # diberikan sama sekali.
        "payment_outgoing",
        # Penerimaan atas faktur penjualan. Tanpa ini ia melihat tagihan
        # terbit tetapi tidak melihat mana yang sudah dibayar — dan
        # rekonsiliasi PPN keluaran terhadap kas menjadi mustahil.
        "payment_incoming",
        # Penyusutan masuk ke laba rugi; angkanya berasal dari sini.
        "asset",
        # NPWP lawan transaksi ada pada keduanya, dan itulah yang dicocokkan
        # dengan faktur pajak.
        "client",
        "supplier",
        # SLIP GAJI — untuk PPh 21, dan hanya untuk itu.
        #
        # Isinya gaji orang per orang, data paling sensitif setelah data
        # pribadi karyawan. Diberikan karena rekapitulasi PPh 21 di halaman
        # Perpajakan memang dihitung dari sini: menutupnya berarti pekerjaan
        # itu pindah ke luar sistem, dan yang pindah ke luar sistem tidak
        # meninggalkan jejak sama sekali.
        #
        # `MODUL_WILAYAH_MUTLAK` tetap berlaku: ia terbuka HANYA karena
        # modul ini disebut di sini, bukan karena levelnya.
        "salary_slip",
    },
}

#: Modul yang bagi divisi tertentu hanya boleh DIBACA.
#
# Peta wilayah di atas menjawab "modul ini urusan siapa", dan matriks level
# menjawab "sejauh apa boleh bertindak". Keduanya tidak dapat menyatakan hal
# ketiga: satu modul yang menjadi urusan DUA divisi dengan kedalaman yang
# berbeda.
#
# Aset persis begitu. Procurement perlu melihat perusahaan punya alat apa saja
# sebelum memutuskan menyewa atau membeli; yang mencatat perolehan, menghitung
# penyusutan, dan menyesuaikan nilainya saat dilepas adalah accounting. Tanpa
# pembedaan ini, membuka aset untuk accounting sekaligus memberi procurement
# hak mengubah angka yang bukan urusannya — dan angka itu masuk ke pembukuan.
#
# Berlaku bagi level di bawah 4, sama seperti batas wilayah: general manager
# dan pemilik memang berwenang atas seluruh perusahaan. Izin khusus per
# pengguna tetap menang atas aturan ini, sehingga satu orang procurement yang
# memang perlu mencatat dapat diberi haknya tanpa mengubah kebijakan.
DEPARTMENT_READ_ONLY: dict[str, set[str]] = {
    # Konsultan: SELURUH wilayahnya hanya-baca.
    #
    # Ia memeriksa, bukan mencatat. Satu pun dokumen tidak boleh berubah oleh
    # tangannya — bukan karena tidak dipercaya, melainkan karena perubahan
    # oleh pihak luar tidak dapat dipertanggungjawabkan siapa pun di dalam.
    #
    # Ditulis sebagai selisih terhadap UMUM, bukan disalin: daftar yang
    # disalin akan tertinggal pada modul berikutnya yang ditambahkan ke
    # wilayahnya, dan yang tertinggal itu justru menjadi satu-satunya modul
    # yang dapat ia ubah — tanpa ada yang menyadarinya.
    "konsultan": DEPARTMENT_MODULES["konsultan"] - UMUM,
    "procurement": {"asset"},
    # Engineering membuka SPK untuk memilih baris pekerjaan yang di-CoP-kan,
    # tetapi tidak menerbitkan maupun mengubahnya — itu tetap procurement.
    "engineering": {"purchase_order"},
    # FAT membuka CoP yang sudah disetujui untuk menagihkannya lewat
    # pembelian, tetapi tidak membuat, memeriksa, maupun menyetujuinya — itu
    # tetap engineering. Cerminan dari hubungan engineering↔purchase_order di
    # atas, arah sebaliknya.
    "fat": {"certificate_of_payment"},
}


def read_only_for(departments: set[str]) -> set[str]:
    """
    Modul yang, bagi orang ini, hanya boleh dibaca.

    Yang dibatasi oleh SATU divisi tidak berlaku bila divisi lain yang
    dipegangnya memberikan modul itu secara penuh: orang yang menangani dua
    wilayah memperoleh yang paling luas di antara keduanya — sama seperti
    `modules_for` yang menggabungkan, bukan mengiris.
    """
    kunci = [(d or "").strip().lower() for d in departments or ()]

    terbatas: set[str] = set()
    penuh: set[str] = set()
    for k in kunci:
        modul = DEPARTMENT_MODULES.get(k, set())
        hanya_baca = DEPARTMENT_READ_ONLY.get(k, set())
        terbatas |= modul & hanya_baca
        penuh |= modul - hanya_baca

    return terbatas - penuh


# Nama yang ditampilkan di layar.
DEPARTMENT_LABELS: dict[str, str] = {
    "fat": "Finance, Accounting & Taxing",
    "hrd": "Human Resource Department",
    "engineering": "Engineering",
    "procurement": "Procurement & Purchasing",
    "konsultan": "Konsultan Akuntansi & Pajak",
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
