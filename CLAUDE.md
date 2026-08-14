# CLAUDE.md

Panduan untuk siapa pun — termasuk Claude Code — yang bekerja di repo ini.

Seluruh angka dan klaim di bawah **diverifikasi terhadap kode**, bukan
diingat. Bila menemukan yang tidak cocok, percayai kodenya dan perbarui
berkas ini.

Terakhir diperiksa: **14 Agustus 2026**

---

## Apa ini

Backend TerraBot — sistem keuangan dan SDM untuk **PT Alpha Konstruksi
Nusantara**. Cakupannya: pembelian, pembayaran, beban, faktur penjualan,
slip gaji, data karyawan, proyek, aset, dan rekening bank.

**Tumpukannya FastAPI + Python.** Bukan Bun, bukan Elysia, bukan Prisma.

> Berkas ini sebelumnya menyatakan proyeknya "Bun + Elysia.js … Migrated
> from Python + FastAPI" — persis kebalikan dari kenyataannya. Sisa berkas
> `prisma/generated/*.ts` juga masih ter-commit, cukup untuk membuat
> penghitung bahasa GitHub menyimpulkan proyeknya TypeScript. Keduanya sudah
> dibereskan; bila muncul lagi, itu tanda ada yang menariknya kembali.

---

## Menjalankan

```bash
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
python main.py          # uvicorn, port 7500, reload aktif
```

Layanan pendamping yang diharapkan di localhost:

| Layanan | Port | Dipakai untuk |
|---|---|---|
| MySQL | 3306 | seluruh data |
| Meilisearch | 7700 | pencarian pemasok, barang, alat |
| Redis | 6379 | singgahan rekening bank |

`.env` (di-gitignore) memerlukan `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`,
dan `MEILISEARCH_MASTER_KEY`.

---

## Keadaan saat ini

| | |
|---|---|
| Uji | **145 lolos**, 1 dilewati |
| Model | 35 berkas, **37 tabel** |
| Rute | 36 berkas, 34 awalan |
| Repository | 29 berkas |

---

## Yang wajib diketahui tentang `databases`

Ini bukan SQLAlchemy ORM biasa. Dua hal berikut sudah masing-masing
menjatuhkan satu endpoint.

**Objek yang dikembalikan `require()` dan `get_current_user()` adalah
Record, bukan `dict`.** Ia tidak punya `.get()`; memanggilnya melempar
`AttributeError` dengan jejak tumpukan yang tidak menyebut sebabnya. Pakai
`user["kolom"]`, bungkus `try/except` bila kolomnya mungkin tidak ada.

**Default kolom sisi-Python tidak pernah berlaku.**
`Column(..., default=dt.now)` dievaluasi mesin SQLAlchemy saat eksekusi;
`databases` menjalankan kueri yang sudah dikompilasi, sehingga langkah itu
dilewati dan nilainya sampai ke MySQL sebagai `NULL`. Karena itu `createdAt`
diisi manual di banyak tempat — ikuti pola itu.

**Kueri mentah diberikan sebagai STRING, bukan dibungkus `text()`.**
`databases` membungkusnya sendiri lalu memasang `bindparams`. Bila sudah
berupa `TextClause`, ia justru memanggil `.values(**values)` — metode yang
hanya dimiliki INSERT/UPDATE — dan melempar `AttributeError`.

---

## Susunan

```
main.py                 aplikasi FastAPI, CORS, kait awal, uvicorn
routes/routes.py        seluruh awalan didaftarkan di sini
routes/*.py             satu berkas per domain
controllers/*.py        orkestrasi
repository/*.py         akses data (metode statis async)
models/*.py             tabel SQLAlchemy Core + skema Pydantic
constants/              matriks izin, modul per divisi, templat klausul
utils/                  database, auth, permission, errors, logger, redis,
                        meilisearch, audit_context, login_guard, config
scripts/cek_skema.py    bandingkan kolom model dengan basis data
test/                   pytest
```

---

## Izin

Tiga lapis, diperiksa berurutan di `utils/permission.py`:

**Izin khusus per pengguna** menimpa segalanya — dipakai sebagai
pengecualian, dan tercatat.

**Batas wilayah divisi** berlaku di bawah level 4. Level 4 (General Manager)
dan 5 (pemilik) tidak dibatasi divisi.

**Tangga level** 1–5, didaftar di `constants/permission_matrix.py` sebagai
`(read, create, update, delete, approve)`. Nilai `0` berarti tidak berlaku.

**Pengecualian yang tidak boleh dilonggarkan tanpa berpikir:**
`MODUL_WILAYAH_MUTLAK` — `salary_slip`, `employees`, `employee_profile`,
`employee_form` — hanya terbuka bagi divisi HRD dan FAT, **berapa pun
levelnya**. Tanpa itu, General Manager membaca gaji seluruh karyawan tanpa
seorang pun pernah memutuskan bahwa ia boleh.

**Yang membuat tidak boleh menyetujui.** Berlaku pada pembayaran keluar.

---

## Pola yang berlaku

**Hapus lunak di mana-mana.** `isDelete` plus `deletedAt`/`deletedBy`.
Sebagian tabel lama menyimpannya sebagai TinyInt (0/1), bukan BOOLEAN —
periksa modelnya sebelum menyaring.

**Boolean daripada enum teks** — `isActive`, `isCancelled`.

**Halaman** pada seluruh endpoint daftar: `page`, `pageSize`, `sortBy`,
`sortByDirection`.

**Galat berkode.** `utils/errors.py` memetakan kode ke pesan yang
diterjemahkan frontend lewat `ServerMessageService`. Repository mengembalikan
`{"error": ..., "status": N}`; rute membukanya menjadi `HTTPException`.

**Jejak audit mencatat NAMA kolom, bukan nilainya**, pada data pribadi.
Jejak audit terbuka bagi level 5 seluruhnya; menyalin isi profil atau gaji ke
sana membuat pembatasan wilayahnya tidak ada artinya.

**Argumen jejak audit disusun dari parameter, bukan dari dict masukan.**
Membaca `data["projectID"]` pernah melempar `KeyError` **setelah** datanya
tersimpan — pengguna melihat 500, mencoba lagi, dan tersimpan dua kali.
Dijaga `test/audit_argumen_test.py`.

---

## Sebelum menyatakan sesuatu selesai

```bash
python3 -m pytest test/ -q        # 145 lolos, 1 dilewati
python3 scripts/cek_skema.py      # kolom model vs basis data
```

`cek_skema.py` membaca SETIAP `Table()` dalam tiap berkas dan menerima
definisi `Column(` multi-baris. Keduanya pernah salah, dan akibatnya enam
tabel tidak pernah diperiksa tanpa ada yang menyadarinya.

**Verifikasi harus bisa gagal.** Bila membuat pemeriksa, uji dulu dengan
kerusakan buatan — pemeriksa yang tidak pernah menemukan apa pun mungkin
memang buta.

---

## Yang belum beres

**CORS masih `*`** di `main.py`. Situs mana pun dapat memanggil API dengan
kredensial pengguna yang sedang login. Perbaikannya satu baris; yang
dibutuhkan hanya daftar domain produksinya.

**`env/` dan `data.ms/` ter-commit** — ribuan berkas, dan `env/` berpotensi
memuat kredensial. Perlu diperiksa isinya, di-gitignore, lalu dikeluarkan
dari riwayat bila memang ada rahasia di sana.

**Slip gaji pernah ter-commit** di `storage/salary_slips/`. Sudah
di-gitignore, tetapi berkasnya **masih ada di riwayat** — membersihkannya
memerlukan penulisan ulang riwayat.

**Cadangan belum pernah diuji pulih.** Skripnya ada di `scripts/`. Bila
belum pernah dicoba memulihkan, itu asumsi — bukan cadangan.

**Halaman posisi keuangan** — `GET /finance-status` sudah ada, layarnya
belum.

---

## Catatan

**ACCURATE** adalah pembukuan resmi AKN; TerraBot tidak menggantikannya.
Standar akuntansi yang berlaku **SAK ETAP**, bukan PSAK penuh.

Kategori pajak karyawan: `TK/0`–`TK/3`, `K/0`–`K/3`. Mata uang IDR.

Dokumen cetak — purchase order, slip gaji, rekap Excel — **tetap berbahasa
Indonesia** apa pun bahasa aplikasinya, karena mengikuti bahasa dokumen
resminya.
