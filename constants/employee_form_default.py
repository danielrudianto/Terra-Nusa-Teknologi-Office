"""
Susunan bawaan formulir keadaan karyawan.

Isinya HANYA yang berubah. Data yang menempel pada orangnya — tempat lahir,
pendidikan formal, pengalaman kerja sebelum masuk — ada di profil dan tidak
ditanyakan ulang. Meminta karyawan mengetik ulang delapan puluh persen
formulir tiap tahun membuat mereka mengisi asal supaya cepat selesai, dan
datanya justru lebih buruk daripada tidak dikumpulkan.

Susunan ini disalin ke kolom `fields` saat versi baru dibuat, BUKAN dibaca
langsung dari sini setiap kali. Jawaban tahun lalu harus tetap dibaca dengan
pertanyaan tahun lalu; bila definisinya dibaca dari kode, mengubah berkas ini
akan diam-diam mengubah arti seluruh jawaban lama.

Jenis isian yang dikenali:
  teks      satu baris
  panjang   beberapa baris
  angka     bilangan
  tanggal   tanggal
  pilih     satu dari daftar `opsi`
  ya-tidak  sakelar
  daftar    baris berulang, tiap baris berisi `kolom`
"""

FORMULIR_BAWAAN = {
    "sections": [
        {
            "key": "keluarga",
            "title": "Keluarga & tanggungan",
            "description": (
                "Perubahan di sini memengaruhi PTKP, sehingga perlu diketahui "
                "sebelum perhitungan pajak tahun berjalan."
            ),
            "fields": [
                {
                    "key": "maritalStatus",
                    "label": "Status pernikahan",
                    "type": "pilih",
                    "options": ["Belum kawin", "Kawin", "Cerai", "Duda/Janda"],
                },
                {
                    "key": "dependents",
                    "label": "Jumlah tanggungan",
                    "type": "angka",
                    "hint": "Yang diakui untuk PTKP, maksimal tiga orang.",
                },
                {
                    "key": "family",
                    "label": "Pasangan dan anak",
                    "type": "daftar",
                    "columns": [
                        {"key": "relation", "label": "Hubungan", "type": "pilih",
                         "options": ["Pasangan", "Anak"]},
                        {"key": "name", "label": "Nama", "type": "teks"},
                        {"key": "birthday", "label": "Tanggal lahir", "type": "tanggal"},
                        {"key": "job", "label": "Pekerjaan", "type": "teks"},
                    ],
                },
            ],
        },
        {
            "key": "kontak",
            "title": "Alamat & kontak",
            "description": "Isi bila ada perubahan sejak pengisian terakhir.",
            "fields": [
                {"key": "currentAddress", "label": "Alamat tinggal saat ini",
                 "type": "panjang"},
                {"key": "mobilePhone", "label": "Nomor HP", "type": "teks"},
                {"key": "personalEmail", "label": "Email pribadi", "type": "teks"},
            ],
        },
        {
            "key": "darurat",
            "title": "Kontak darurat",
            "description": (
                "Bagian yang paling berbahaya bila basi. Pastikan nomornya "
                "masih aktif, bukan sekadar menyalin isian tahun lalu."
            ),
            "fields": [
                {
                    "key": "emergencyContacts",
                    "label": "Yang dapat dihubungi",
                    "type": "daftar",
                    "columns": [
                        {"key": "name", "label": "Nama", "type": "teks"},
                        {"key": "relation", "label": "Hubungan", "type": "teks"},
                        {"key": "phone", "label": "Nomor telepon", "type": "teks"},
                        {"key": "address", "label": "Alamat", "type": "teks"},
                    ],
                },
            ],
        },
        {
            "key": "kesehatan",
            "title": "Riwayat kesehatan",
            "description": (
                "Diperlukan untuk penempatan kerja lapangan dan penanganan "
                "keadaan darurat di lokasi."
            ),
            "fields": [
                {
                    "key": "conditions",
                    "label": "Riwayat penyakit",
                    "type": "daftar",
                    "columns": [
                        {"key": "name", "label": "Penyakit", "type": "teks"},
                        {"key": "since", "label": "Sejak", "type": "teks"},
                        {"key": "note", "label": "Keterangan", "type": "teks"},
                    ],
                },
                {"key": "accident", "label": "Pernah mengalami kecelakaan kerja?",
                 "type": "ya-tidak"},
                {"key": "accidentNote", "label": "Bila ya, jelaskan",
                 "type": "panjang"},
                {"key": "smoking", "label": "Merokok", "type": "pilih",
                 "options": ["Tidak", "Kadang", "Setiap hari"]},
                {"key": "lastCheckup", "label": "Pemeriksaan kesehatan terakhir",
                 "type": "teks", "hint": "Kapan dan di mana."},
            ],
        },
        {
            "key": "pelatihan",
            "title": "Pelatihan & sertifikasi",
            "description": (
                "Yang didapat sejak pengisian terakhir. Sertifikat keahlian "
                "kerap punya masa berlaku, sehingga tanggalnya penting."
            ),
            "fields": [
                {
                    "key": "trainings",
                    "label": "Kursus, pelatihan, sertifikasi",
                    "type": "daftar",
                    "columns": [
                        {"key": "name", "label": "Nama", "type": "teks"},
                        {"key": "organizer", "label": "Penyelenggara", "type": "teks"},
                        {"key": "date", "label": "Tanggal", "type": "teks"},
                        {"key": "validUntil", "label": "Berlaku sampai", "type": "teks"},
                    ],
                },
            ],
        },
        {
            "key": "kesediaan",
            "title": "Kesediaan",
            "description": (
                "Dapat berubah seiring keadaan keluarga; karena itu ditanyakan "
                "ulang, bukan diambil dari jawaban saat melamar."
            ),
            "fields": [
                {"key": "relocate", "label": "Bersedia ditempatkan di kota lain",
                 "type": "ya-tidak"},
                {"key": "overtime", "label": "Bersedia lembur", "type": "ya-tidak"},
                {"key": "shift", "label": "Bersedia kerja shift", "type": "ya-tidak"},
                {"key": "availabilityNote", "label": "Catatan", "type": "panjang"},
            ],
        },
    ]
}


#: Jenis isian yang dikenali layar. Dipakai memeriksa definisi versi baru
#: agar jenis yang salah tulis ketahuan saat versinya dibuat, bukan saat
#: karyawan sudah membuka formulirnya dan menemukan isian yang kosong.
JENIS_ISIAN = {"teks", "panjang", "angka", "tanggal", "pilih", "ya-tidak", "daftar"}


def periksa_definisi(definisi: dict) -> list[str]:
    """
    Periksa susunan formulir; kembalikan daftar masalah.

    Kosong berarti sah. Dikembalikan sebagai daftar, bukan melempar pada
    masalah pertama, supaya penyusunnya melihat seluruh kesalahannya
    sekaligus dan tidak memperbaikinya satu per satu.
    """
    masalah: list[str] = []
    bagian = (definisi or {}).get("sections")
    if not isinstance(bagian, list) or not bagian:
        return ["Formulir tidak punya satu bagian pun."]

    kunci_terpakai: set[str] = set()
    for i, b in enumerate(bagian):
        nama = b.get("key") or f"bagian ke-{i + 1}"
        if not b.get("key"):
            masalah.append(f"{nama}: tanpa `key`.")
        if not b.get("title"):
            masalah.append(f"{nama}: tanpa judul.")

        isian = b.get("fields")
        if not isinstance(isian, list) or not isian:
            masalah.append(f"{nama}: tidak punya isian.")
            continue

        for f in isian:
            k = f.get("key")
            if not k:
                masalah.append(f"{nama}: ada isian tanpa `key`.")
                continue
            # Kunci harus unik LINTAS bagian: jawaban disimpan datar,
            # sehingga dua isian berkunci sama saling menimpa diam-diam.
            if k in kunci_terpakai:
                masalah.append(f"{nama}: kunci `{k}` dipakai dua kali.")
            kunci_terpakai.add(k)

            jenis = f.get("type")
            if jenis not in JENIS_ISIAN:
                masalah.append(f"{nama}.{k}: jenis `{jenis}` tidak dikenali.")
            if jenis == "pilih" and not f.get("options"):
                masalah.append(f"{nama}.{k}: jenis `pilih` tanpa daftar opsi.")
            if jenis == "daftar" and not f.get("columns"):
                masalah.append(f"{nama}.{k}: jenis `daftar` tanpa kolom.")
    return masalah
