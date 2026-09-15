# Nomor dokumen tender — BACKEND

**ADA PERUBAHAN SKEMA.** `sql/tender-nomor-dokumen.sql` harus dijalankan.

Urutan: SQL → `cek_skema.py` → restart. Frontend-nya di zip terpisah.

---

## Bentuknya

```
T-AKN-001-IX-2026
  |    |   |   `- tahun
  |    |   `----- bulan, angka Romawi
  |    `--------- urutan dalam TAHUN itu
  `-------------- tetap
```

Urutannya **mengulang tiap tahun** (pilihan Anda). Karena itulah tahun ikut di
nomornya — tanpa pengulangan, bagian tahun cuma hiasan.

## Tiga keputusan

**1. Bulan & tahun dari TANGGAL TENDERNYA, bukan hari ini.**
Tender yang dicatat 2 Oktober untuk dokumen bertanggal 28 September bernomor
`...-IX-...`. Nomor dokumen menyebut kapan dokumennya berlaku; memakai tanggal
pencatatan membuat nomornya bercerita tentang kapan seseorang sempat membukanya.

**2. Nomornya DISIMPAN, bukan dihitung saat ditampilkan.**
Nomor dokumen adalah identitas: begitu terbit, ia dirujuk di percakapan, di
berkas cetak, di surat ke pemasok. Kalau dihitung dari `date`, menyunting
tanggal tender diam-diam mengubah nomornya — dan rujukan yang sudah beredar
menunjuk sesuatu yang tidak ada lagi.

**3. Tender yang DIHAPUS tetap terhitung.**
Aturan ini sudah ada sebelum format barunya dan tetap berlaku. Kalau yang
terhapus dilewati, tender berikutnya mewarisi nomor milik tender yang pernah
ada — dan rujukan lama ke nomor itu diam-diam menunjuk dokumen yang berbeda.

## SQL-nya

Berkasnya bertahap dan ada pemeriksaannya:

- **Bagian 0** aman diulang — cek dulu. `tanpa_tanggal` **harus 0**; kalau
  bukan, BERHENTI dan beri tahu saya.
- **Bagian 1** `ADD COLUMN` (tidak idempoten; galat 1060 = sudah pernah jalan,
  lanjut saja).
- **Bagian 2** isi ulang urutan per tahun + nomor dokumennya. Butuh window
  function — MySQL 8.0+ / MariaDB 10.2+.
- **Bagian 3** indeks unik, dipasang SESUDAH pengisian: kalau ada yang kembar,
  galatnya muncul dengan datanya sudah terisi dan dapat diperiksa.
- **Bagian 4** verifikasi: tidak ada yang kosong, tidak ada yang kembar, dan
  urutan tiap tahun rapat 1..N.

> Tender lama ikut dapat nomor baru. Kalau ada yang pernah menyebut "tender 3",
> sekarang ia `T-AKN-003-VIII-2026` — masih terlacak, tidak lagi sama persis.

## Uji

**946 lolos** (dari 937). `test/nomor_tender_test.py`, 9 uji: bentuknya persis,
dua belas bulan Romawi, nol di depan adalah minimum (tender ke-1000 tidak
terpotong jadi `000`), urutan per tahun, yang terhapus tetap terhitung,
tanggalnya dari tendernya, dan SQL-nya tidak menyaring `isDelete`.

> Satu uji saya sempat merah karena **membaca docstring, bukan kode**:
> penjelasan "kenapa `isDelete` tidak disaring" membuat pencarian kata
> `isDelete` di badan fungsi menemukan prosanya. Pemindainya sekarang membuang
> docstring juga. Kelas kesalahan yang sama pernah membuat uji migrasi
> mobilisasi HIJAU padahal saringannya sudah dicabut — di sini arahnya
> kebetulan terbalik, sebabnya persis sama.
