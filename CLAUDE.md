# CLAUDE.md

Panduan untuk Claude Code (claude.ai/code) saat bekerja di repo ini.
Pelengkap `README.md` — baca README dulu untuk gambaran utuh; file ini fokus ke
hal yang mudah bikin salah langkah.

## Apa Ini

Backend TerraBot: sistem manajemen keuangan & HR PT Alpha Konstruksi Nusantara
(AKN). Domain inti: purchase order, pembelian, pembayaran (masuk/keluar),
reimbursement, expense, sales invoice, certificate of payment (CoP), slip gaji,
karyawan, absensi, proyek, tender, rekrutmen, pajak (PPh/PPN), dan bank.

**Stack:** Python 3.10+ · FastAPI · SQLAlchemy Core + pustaka `databases` (async)
· MySQL · Redis · Meilisearch · WeasyPrint (PDF) · O365/MSAL (email) · pywebpush.

> Repo ini SUDAH sepenuhnya Python. Kalau ketemu sisa artefak Node/Bun
> (`bun.lock`, `prisma/`, `tsconfig.json`, `package.json`), itu bekas migrasi
> lama — abaikan, jangan dijadikan acuan.

## Menjalankan

Butuh Python 3.10+ (kode pakai sintaks `int | None`).

```bash
python3 -m venv env
./env/bin/pip install -r requirements.txt
./env/bin/python main.py          # jalan di :7500 (atur lewat PORT)
```

- Dokumentasi interaktif: `/docs`.
- `reload` menyala otomatis KECUALI `APP_ENV=production` (lihat `main.py`).
- Butuh MySQL, Redis, dan Meilisearch aktif di `127.0.0.1`. Startup lifespan di
  `main.py` connect DB, setup + sync Meilisearch (item, equipment, supplier),
  lalu sync Redis. Kegagalan tiap servis dicatat log, tapi lihat catatan view
  `balance` di bawah — yang itu bikin app GAGAL nyala.

Paket yang dikompilasi (`bcrypt`, `hiredis`) dan WeasyPrint (Pango) perlu pustaka
sistem — lihat README bagian "Menjalankan".

## Arsitektur — alur satu arah

```
routes/        titik masuk HTTP + penjaga izin (Depends)
controllers/   aturan bisnis, orkestrasi
repository/    SATU-SATUNYA lapis yang baca/tulis DB (async via `databases`)
models/        definisi tabel SQLAlchemy Core (bukan ORM session)
schemas/       Pydantic — bentuk payload masuk & keluar
services/      mail_service (O365), pdf_service (WeasyPrint), user_service
utils/         auth, permission, database, redis, meilisearch, errors,
               audit_context, logger, login_guard, webpush
constants/     matriks izin & modul departemen
startup/       create_tables, sync helper, otorisasi Microsoft
scripts/       cek_skema.py, backup/restore, deploy.sh, konfigurasi nginx
sql/           perubahan skema manual (diterapkan langsung ke DB)
test/          uji pytest (berkas *_test.py)
```

Alur: `routes → controllers → repository → models`. **Rute tidak pernah
menyentuh DB langsung** — semua kueri lewat repository. `main.py` meng-`include`
`routes/routes.py`, yang mengumpulkan semua APIRouter per domain.

## Autentikasi

- JWT via PyJWT. `SECRET_KEY` + `ALGORITHM` (HS256) dari `.env`.
- Dependency `get_current_user` (`utils/auth_utils.py`) mendekode token, memuat
  user, dan **MENOLAK akun nonaktif/terhapus** (`isActive`/`isDeleted`) — ini
  satu-satunya pintu yang dilewati semua permintaan bertoken, jadi jangan
  duplikasi cek itu di tiap rute.
- Access token `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60), refresh
  `REFRESH_TOKEN_EXPIRE_MINUTES` (default 7 hari, 10080).
- Logika login sebenarnya ada di `routes/auth_routes.py`. `authenticate_user()`
  di `auth_utils.py` **kode mati — jangan dipanggil** (pakai kolom yang tidak
  ada + `.first()` yang bukan cara pustaka ini membaca baris).
- Rate-limit login di `utils/login_guard.py`: 5 percobaan gagal → kunci 15 menit,
  per-email dan per-IP, hitungan di Redis. Bila Redis mati, pembatas dilewati
  (biar tidak mengunci semua orang).

## Izin (RBAC)

Pakai `utils/permission.py`. Untuk memagari rute:

```python
async def approve(id: int, current_user = Depends(require("expenses", "approve"))):
```

`require(module, action)` mengembalikan objek user yang sama seperti
`get_current_user`, jadi isi rute tidak perlu diubah.

**Urutan penentuan:** (1) izin khusus per-user menang; (2) modul harus dalam
wilayah departemen user; (3) level user ≥ level minimum modul (matriks di
`constants/permission_matrix.py`).

- **Level 1–5** (1 terendah, 4 = general manager, 5 = pemilik).
- `MODUL_WILAYAH_MUTLAK` (`salary_slip`, `employees`, `employee_profile`,
  `employee_form`, `hr_recruitment`) menegakkan batas departemen untuk SEMUA
  level di bawah 5 — data paling sensitif.
- `LEVEL_BOLEH_SETUJU_SENDIRI = 5`: hanya pemilik yang boleh menyetujui dokumen
  buatannya sendiri; selebihnya pembuat ≠ penyetuju.
- **Menyembunyikan tombol di UI bukan pengamanan** — cek di server inilah yang
  menentukan. Setiap rute yang mengubah data harus lewat `require(...)`.

## Pola penting

**Soft delete di mana-mana.** Kebanyakan tabel pakai `isDelete`/`deletedAt`/
`deletedBy` (users: `isActive`/`isDeleted`). Selalu filter yang belum terhapus.

**Jejak audit.** Perubahan tercatat di `audit_logs` beserta pelaku, waktu, dan
kolom yang berubah. Pelaku diisi otomatis lewat `ContextVar` yang disetel
middleware `audit_context` dari token — controller/repository tidak perlu
meneruskannya. Gagal mencatat audit TIDAK menggagalkan tindakan utama.

**Uang = `Decimal` (MySQL DECIMAL).** Presisi penting (IDR). Hati-hati campur
`float` vs `Decimal` — lolos uji tapi bisa gagal di produksi.

## Gotcha yang tidak terlihat dari kode

Semuanya pernah menjatuhkan sesuatu. Ringkas dari README:

- **Baris = `databases.Record`, bukan `dict`.** Tidak punya `.get()`. Pakai
  `row["kolom"]` atau `getattr(row, "kolom", bawaan)`.
- **Kolom JSON jangan di-`json.dumps` dulu** — SQLAlchemy menyandikannya sendiri;
  kalau tidak, tersandi dua kali.
- **Default kolom sisi-Python tidak berlaku** (mis. `default=dt.now`) karena
  `databases` menjalankan kueri terkompilasi. Isi `createdAt` manual.
- **Label subkueri harus disebut dua kali** (di kueri + di kelas jawaban).
- **View `balance` & `mutation` wajib ada.** `balance` dimuat `autoload_with`,
  jadi app **gagal nyala** kalau view-nya tidak ada — bukan cuma satu halaman
  rusak. Definisi di `sql/`. `mutation` dipakai kalender/saldo (akses via raw
  query, tidak ada di model).
- **Dump berisi `DEFINER`** → impor sebagai user biasa gagal galat 1227.

## Alur Certificate of Payment (CoP) — 4 tahap, 2 approval

Alur BARU (hasil rework, SQL `sql/cop-alur-bap.sql` sudah diterapkan di
produksi). Rutenya di `routes/certificate_of_payment_routes.py`.

1. **BAP dibuat** — engineering L1 (isi volume).
2. **Setujui BAP** — L4+ (`bapApprovedBy`). Harga baru boleh diisi SETELAH ini.
3. **CoP dibuat** — engineering L2+ (`copCreatedBy`, isi harga & potongan).
4. **Setujui CoP** — L4+ (`approvedBy`). Siap ditagih.

Dua approval tidak boleh orang yang sama dan tidak boleh pembuatnya. Kolom lama
`checkedBy/isChecked/checkedAt` → `copCreatedBy/isCopCreated/copCreatedAt`; kolom
baru `isBapApproved/bapApprovedBy/bapApprovedAt`. Penomoran CoP:
`[urut]-[IDvendor]-[proyek]-[tahun]` (mis. `002-042-R501-2026`), per vendor+proyek.
Nomor BAP mengikuti nomor CoP lengkap.

## Perubahan skema & deploy

Skema diubah lewat berkas `.sql` mentah di `sql/`, diterapkan MANUAL ke DB.
Tidak ada ORM migration otomatis.

```bash
git pull
./env/bin/pip install -r requirements.txt
./env/bin/python scripts/cek_skema.py       # JANGAN dilewati
sudo systemctl restart terrabot
```

`cek_skema.py` menandai kolom yang belum ada — kalau dilewati, kolom hilang jadi
galat 500 tanpa menyebut kolom mana. App jalan sebagai layanan systemd
(`terrabot`) di balik Nginx; MySQL/Redis/Meilisearch hanya mendengarkan
`127.0.0.1`.

> **Deliverable:** perubahan dikirim sebagai berkas/tarball; Daniel yang commit
> & deploy sendiri. Asisten tidak push ke repo dan tidak punya akses server/DB.

## Uji

```bash
./env/bin/python -m pytest test/ -q
```

Berkas uji berakhiran `*_test.py` di `test/` (`asyncio_mode=auto`). Uji
memeriksa ATURAN, bukan cuma jalannya kode: sandi di-hash, dokumen yang sudah
disetujui tidak bisa diubah, jejak audit menyertakan pelaku. Uji lolos tidak
menjamin bebas masalah tipe (`float` vs `Decimal`, `Record` vs `dict`).

## Kelompok rute (prefix di `routes/routes.py`)

`/auth` · `/permissions` · `/user-access` · `/users` · `/user-avatars` ·
`/clients` · `/suppliers` · `/tenders` · `/payment-plans` · `/purchases` ·
`/purchase-orders` · `/purchase-draft` · `/reimbursements` · `/banks` ·
`/expenses` · `/expense-opponents` · `/outgoing-payments` · `/incoming-payments` ·
`/interpayments` · `/loans` · `/income` · `/sales-invoices` ·
`/certificate-of-payments` · `/assets` · `/taxes` · `/employees` ·
`/employee-profiles` · `/employee-forms` · `/hr` (rekrutmen) · `/salary-slips` ·
`/calendar` · `/agenda` · `/projects` · `/finance-status` · `/dashboard` ·
`/master-items` · `/master-equipment` · `/audit-logs` · `/push`

## Locale Indonesia

- Kategori pajak karyawan: `TK/0`–`TK/3`, `K/0`–`K/3`.
- Meilisearch punya sinonim lokasi/alat berbahasa Indonesia (`utils/meilisearch*.py`).
- Mata uang IDR — presisi `Decimal` penting.
- Seluruh dokumen cetak (PO, slip gaji, rekap) berbahasa Indonesia.
- Pembukuan resmi AKN = **ACCURATE** (TerraBot tidak menggantikannya); standar
  akuntansi **SAK ETAP**, bukan PSAK penuh.

## Environment

`.env` (gitignored) — TANPA spasi di sekitar `=` (systemd menolak `KUNCI = nilai`):

```ini
APP_ENV=production
PORT=7500
DATABASE_URL=mysql://pengguna:sandi@localhost/tnt
SECRET_KEY=                 # openssl rand -hex 32 ; menandatangani semua token
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=10080
MEILISEARCH_MASTER_KEY=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
CORS_ORIGINS=              # bila diisi, MENGGANTIKAN daftar asal, bukan menambah
SLOW_REQUEST_MS=1000       # ambang catat permintaan lambat
```

`APP_ENV` menentukan dua hal: `reload` mati di produksi, dan alamat `localhost`
dikeluarkan dari daftar CORS.

## Logging

Pakai `log_info()`, `log_error()` (dan `log_warning` bila ada) dari
`utils/logger_utils.py`. Middleware di `main.py` mencatat permintaan yang lebih
lambat dari `SLOW_REQUEST_MS` dan selalu mengirim header `X-Response-Time-ms`.
