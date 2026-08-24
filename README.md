# TerraBot — Backend

API untuk sistem manajemen PT Alpha Konstruksi Nusantara: purchase order,
pembelian, pembayaran, penggajian, dan pelaporan proyek.

FastAPI · MySQL · Redis · Meilisearch

---

## Keadaan

| | |
|---|---|
| Endpoint | 187 |
| Tabel | 39 |
| Berkas uji | 31 |
| Uji lolos | 244 |
| Kelompok rute | 34 |

---

## Menjalankan

Perlu Python 3.10 ke atas — kode memakai sintaks `int | None`.

```bash
git clone https://github.com/danielrudianto/Terra-Nusa-Teknologi-Office.git
cd Terra-Nusa-Teknologi-Office

python3 -m venv env
./env/bin/pip install -r requirements.txt
```

Beberapa paket dikompilasi saat dipasang. Bila `bcrypt` atau `hiredis` gagal:

```bash
sudo apt install -y python3-dev build-essential pkg-config
```

`weasyprint` merender PDF lewat Pango; tanpa pustaka sistemnya, ia terpasang
tetapi gagal saat mencetak:

```bash
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
```

Salin `.env`, lalu:

```bash
./env/bin/python main.py
```

Dokumentasi interaktif ada di `/docs`.

---

## Lingkungan

```ini
APP_ENV=production
PORT=7500

DATABASE_URL=mysql://pengguna:sandi@localhost/tnt
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080

MEILISEARCH_MASTER_KEY=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

CORS_ORIGINS=
SLOW_REQUEST_MS=1000
```

**Tanpa spasi di sekitar `=`.** systemd membaca berkas ini apa adanya, dan
`KUNCI = nilai` membuat seluruh berkasnya ditolak.

`SECRET_KEY` menandatangani seluruh token login. Bila bocor, siapa pun dapat
membuat token atas nama siapa pun, termasuk level tertinggi:

```bash
openssl rand -hex 32
```

`APP_ENV` menentukan dua hal sekaligus: `reload` dimatikan di produksi, dan
alamat pengembangan (`localhost`) dikeluarkan dari daftar CORS. `CORS_ORIGINS`
bila diisi **menggantikan** seluruh daftar, bukan menambah.

---

## Susunan

```
routes/        titik masuk HTTP, penjaga izin
controllers/   aturan yang berlaku sebelum data disentuh
repository/    kueri; satu-satunya lapis yang menulis basis data
models/        definisi tabel SQLAlchemy
schemas/       bentuk muatan masuk dan keluar
services/      surel (O365), PDF (WeasyPrint)
utils/         auth, izin, jejak audit, galat, singgahan
test/          31 berkas uji
scripts/       cadangan, pemeriksa skema
```

Alurnya satu arah: `routes → controllers → repository → models`. Rute tidak
pernah menyentuh basis data langsung.

---

## Hal yang tidak terlihat dari kodenya

Bagian ini lahir dari kesalahan nyata. Masing-masing pernah menjatuhkan
sesuatu.

**Objek baris bukan `dict`.** Yang dikembalikan pustaka `databases` adalah
`Record`. Ia **tidak punya `.get()`** — memanggilnya membuat pustaka mencari
kolom bernama `"get"`, lalu gagal dengan pesan yang tidak menyebut sebabnya
sama sekali. Pakai `row["kolom"]` atau `getattr(row, "kolom", bawaan)`.

**Kolom bertipe JSON jangan di-`json.dumps` dulu.** SQLAlchemy sudah
menyandikannya sendiri; menyandikan lebih dulu membuat isinya tersandi dua
kali, dan pembacanya menerima teks yang tampak benar tetapi tidak punya satu
pun kunci.

**Default kolom sisi-Python tidak pernah berlaku.** `Column(..., default=dt.now)`
dievaluasi mesin SQLAlchemy saat eksekusi; `databases` menjalankan kueri yang
sudah dikompilasi, sehingga langkah itu dilewati dan nilainya sampai ke MySQL
sebagai `NULL`. Isi `createdAt` secara manual.

**Label subkueri harus disebut dua kali.** Sekali pada kuerinya, sekali lagi
saat disalin ke kelas jawaban. Yang lupa disalin dihitung basis data lalu
dibuang tanpa satu pun galat.

**View `balance` dan `mutation` wajib ada.** `balance` dimuat dengan
`autoload_with`, sehingga aplikasinya **gagal menyala** bila view itu tidak
ada — bukan sekadar satu halaman yang rusak. Definisinya ada di `sql/`.

**Dump berisi `DEFINER`.** Mengimpor sebagai pengguna biasa gagal dengan
galat 1227. Buang klausulnya, atau buat viewnya terpisah.

---

## Keamanan

**Sandi di-hash di repository**, bukan di controller — di situ penulisannya
benar-benar terjadi, sehingga tidak ada jalur yang dapat melewatinya. Nilai
yang sudah berupa hash tidak di-hash ulang.

**Kolom sandi tidak pernah keluar** dari server. Dibuang di repository, satu
pintu yang dilewati seluruh pembacaan pengguna.

**Akun nonaktif ditolak** pada `get_current_user`. Tanpa itu, menonaktifkan
seseorang tidak berpengaruh sampai tokennya kedaluwarsa — dan refresh token
berlaku tujuh hari.

**Galat tak terduga tidak membocorkan jejaknya.** Yang keluar hanya kode
`INTERNAL`; pesan aslinya kerap memuat nama tabel, nama kolom, dan potongan
SQL.

**Yang membuat tidak boleh menyetujui** pada pembayaran keluar, kecuali level
4 ke atas.

---

## Jejak audit

Setiap tindakan yang membuat, mengubah, atau menghapus dokumen tercatat di
`audit_logs` beserta pelaku, waktu, dan kolom apa yang berubah.

Pelakunya diisi sendiri lewat `ContextVar` yang disetel middleware dari token,
sehingga pemanggil tidak perlu meneruskannya. Kegagalan pencatatan **tidak**
menggagalkan tindakan utamanya — ia dicatat ke log.

---

## Uji

```bash
./env/bin/python -m pytest test/ -q
```

Uji di sini memeriksa aturan, bukan hanya jalannya kode: bahwa sandi di-hash,
bahwa dokumen yang sudah disetujui tidak dapat diubah, bahwa jejak audit
menyertakan pelakunya. Sebagian ditulis setelah bug lolos ke produksi.

Uji lolos tidak menjamin bebas masalah tipe di produksi — `float` versus
`Decimal`, dan `Record` versus `dict`, keduanya lolos uji tetapi gagal saat
berjalan.

---

## Deploy

Aplikasi berjalan sebagai layanan systemd di balik Nginx. Pembaruan rutin:

```bash
git pull
./env/bin/pip install -r requirements.txt
./env/bin/python scripts/cek_skema.py
sudo systemctl restart terrabot
```

`cek_skema.py` jangan dilewati. Kolom yang belum ada menghasilkan galat 500
yang tidak menyebut kolom mana; perubahan skema tersimpan di `sql/`.

Aplikasi tidak pernah menghadap internet langsung — MySQL, Redis, dan
Meilisearch hanya mendengarkan `127.0.0.1`, dan hanya Nginx yang membuka
porta ke luar.

Cadangan dan pemulihan ada di `scripts/`; keterangannya di
`scripts/README.md`.

---

## Catatan

**ACCURATE** adalah pembukuan resmi AKN; TerraBot tidak menggantikannya.
Standar akuntansi yang berlaku **SAK ETAP**, bukan PSAK penuh.

Seluruh dokumen cetak — purchase order, slip gaji, rekap — berbahasa
Indonesia mengikuti bahasa dokumen resminya, bukan bahasa antarmuka.
