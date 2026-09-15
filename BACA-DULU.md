# Arus kas proyek — BACKEND

**Tidak ada perubahan skema.** Tidak ada `.sql` baru, tidak ada kolom baru.
Ekstrak di atas repo backend, commit, deploy.

> Dikirim sebagai **dua zip** (backend & frontend) alih-alih satu, supaya
> masing-masing tetap bisa diekstrak langsung di atas reponya tanpa
> memindahkan folder. Jalankan yang ini dulu — frontend memanggil rutenya.

---

## Yang ditambahkan

| Berkas | Isi |
|---|---|
| `repository/project_cashflow_repository.py` | kueri kas keluar & kas masuk |
| `controllers/project_cashflow_controller.py` | perakitan + aturan "kosong bukan galat" |
| `routes/project_routes.py` | `GET /projects/{project_name}/cashflow` |
| `test/arus_kas_proyek_test.py` | 11 uji |

---

## Kenapa ini bukan pengulangan "arus per minggu" yang sudah ada

Laporan proyek yang sekarang menghitung dari **tanggal dokumen** — tanggal
pembelian, tanggal faktur. Itu menjawab *"sudah berkomitmen berapa"*. Ia tidak
menjawab *"kapan uangnya keluar dari rekening"*, dan pada pekerjaan konstruksi
jarak keduanya berminggu-minggu sampai berbulan-bulan.

Dua proyek dengan biaya dan tagihan yang **sama persis** bisa sangat berbeda
kasnya: yang satu menagih di muka, yang lain menalangi enam bulan. Perbedaan
itu tidak terlihat sama sekali pada tanggal dokumen.

Jadi modul ini membaca tabel **pembayaran**, bukan tabel dokumen.

---

## Penjaga izinnya sengaja LEBIH TINGGI dari rute di sebelahnya

Rute laporan proyek yang sudah ada dijaga `purchase:read` — **level 1**.
Rute arus kas ini dijaga `payment_outgoing:read` — **level 3**.

Kalau ia menumpang `purchase:read`, tanggal dan nominal uang keluar dari
rekening terbuka bagi lapangan dan pengadaan — yang oleh matriks izin justru
**sengaja dijauhkan** dari data kas. Rute yang mengembalikan hal yang sama
lewat pintu yang lebih rendah membatalkan keputusan itu tanpa mengubah satu
baris pun di matriksnya.

`payment_incoming` juga level 3, jadi satu penjaga ini tidak melonggarkan sisi
mana pun.

**Akibat yang disengaja:** departemen yang tidak memegang `payment_outgoing`
(engineering, misalnya) mendapat 403 — dan layarnya **menyembunyikan tabnya**,
bukan menampilkan galat. Pola yang sama sudah dipakai bagian kemajuan bagi
konsultan pajak.

---

## Tiga keputusan yang menentukan angkanya

**1. Disaring `isDelete` saja, BUKAN `isApprove`.**
Mengikuti kalender kas dan saldo bank, yang keduanya menghitung pembayaran
begitu tercatat. Penolakan dan pembatalan sudah mencabut `isApprove`
**sekaligus** menyetel `isDelete`, jadi `isDelete = 0` sudah berarti
pembayarannya berlaku. Menambahkan `isApprove` di sini akan membuat laporan
proyek melaporkan kas yang berbeda dari kalender untuk uang yang sama.

**2. Dokumen induknya ikut disaring `isDelete`.**
Tanpa ini, **menghapus** sebuah pembelian justru **menaikkan** kas keluar
proyeknya — arah yang berlawanan dengan dugaan siapa pun, dan tanpa galat.

**3. Join-nya menyebut kolomnya sendiri (`onclause` eksplisit).**
Lihat temuan di bawah.

---

## Temuan yang perlu Anda tahu: FK salah tabel

```python
# models/payment_incoming_model.py
Column("salesInvoiceID", Integer, ForeignKey("purchases.id"), nullable=True),
```

Kolomnya bernama `salesInvoiceID` tetapi FK-nya menunjuk **`purchases.id`**.

Akibatnya SQLAlchemy tidak mengenal satu pun hubungan antara
`payment_incoming` dan `sales_invoices`, sehingga `join(sales_invoice_tables)`
tanpa `onclause` **gagal** dengan `NoForeignKeysError`.

> Saya sempat menulis di komentar bahwa ia akan "menyambung diam-diam ke tabel
> yang salah". **Keliru** — saya rusak sengaja untuk mengeceknya, dan ia
> melempar. Komentarnya sudah dibetulkan.

Yang tetap perlu diingat adalah **sebabnya**: pesan galatnya menunjuk ke "tidak
ada FK", bukan ke "FK-nya salah tabel" — dan yang membacanya akan mencari FK
yang hilang, bukan FK yang keliru arah.

**Tidak saya ubah dari sini**: itu perubahan skema, dan memperbaikinya
menyentuh seluruh pembaca `payment_incoming`. Bilang kalau mau dibereskan
terpisah.

---

## Yang TIDAK tercakup — dan disebutkan di jawabannya

Kas keluar proyek hanya dapat dirunut lewat **pembelian** dan **reimbursement**.
`expenses` dan `salary_slips` **tidak punya kolom proyek sama sekali**, jadi
biaya operasional dan gaji yang sebenarnya terpakai di proyek ini tidak ikut.

Garis kas keluarnya karena itu **batas bawah, bukan angka utuh**. Jawaban
rutenya menyertakan `cakupanKeluar: ["pembelian", "reimbursement"]`, dan
layarnya mencetak keterangan itu di sebelah angkanya — supaya pemakai
berikutnya (unduhan, layar lain, integrasi) tidak mewarisi angkanya tanpa
mewarisi batasannya.

---

## Uji

**937 lolos** (dari 926). `test/arus_kas_proyek_test.py`, 11 uji — diperiksa
lewat **SQL yang dihasilkan**, bukan lewat hasil tiruan, karena ketiga
kekeliruan yang paling mungkin di sini tidak menghasilkan galat apa pun,
melainkan angka lain.

Dibuktikan menggigit:

```
join kas masuk disederhanakan  → test_kas_masuk_menyambung_ke_faktur... GAGAL
tambah saringan isApprove      → test_tidak_menyaring_isApprove GAGAL
induk tak disaring isDelete    → test_dokumen_induk_yang_terhapus... GAGAL
```
