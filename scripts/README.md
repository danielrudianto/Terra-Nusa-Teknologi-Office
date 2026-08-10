# Cadangan Basis Data TERRABOT

Dua skrip untuk mencadangkan dan memulihkan basis data.

| Berkas | Fungsi |
|---|---|
| `backup_db.sh` | Membuat cadangan terkompresi, lalu memeriksa hasilnya |
| `restore_db.sh` | Memulihkan cadangan — bawaannya ke basis data uji |

---

## Pemasangan

```bash
chmod +x scripts/*.sh
```

Pastikan `mysqldump` dan `mysql` tersedia:

```bash
which mysqldump mysql
# bila belum ada (Ubuntu/Debian):
sudo apt install mysql-client
```

Skrip membaca sambungan dari **`DATABASE_URL`** di berkas `.env` — variabel
yang sama dengan yang dipakai aplikasi. Tidak ada kata sandi yang ditulis di
dalam skrip.

---

## Mencadangkan

```bash
./scripts/backup_db.sh
```

Hasilnya:

```
Mencadangkan 'terrabot' dari localhost:3306 ...
Selesai: /home/daniel/terrabot-backups/terrabot-20260810-020000.sql.gz (4.2M)
Berisi 28 tabel.
OK.
```

### Yang diperiksa sebelum cadangan dianggap sah

Cadangan yang tidak pernah diuji sama saja dengan tidak punya cadangan. Skrip
menolak dan menghapus hasilnya bila:

1. Berkas gzip rusak
2. Dump tidak memuat penanda `Dump completed` (artinya terputus di tengah)
3. Jumlah tabel di bawah 5 (artinya tidak lengkap)

Selama proses berjalan, berkas bernama `.tmp` dan baru diberi nama akhir
setelah semua pemeriksaan lolos. Dump yang gagal tidak akan pernah terlihat
seperti cadangan yang benar.

---

## Menjadwalkan

```bash
crontab -e
```

Tambahkan:

```cron
0 2 * * * /home/daniel/Terra-Nusa-Teknologi-Office/scripts/backup_db.sh >> /home/daniel/terrabot-backups/backup.log 2>&1
```

Setiap hari pukul 02:00, log ditulis ke `backup.log`.

Periksa beberapa hari kemudian:

```bash
tail -20 ~/terrabot-backups/backup.log
ls -lh ~/terrabot-backups/
```

---

## ⚠️ Salin ke luar server

Cadangan yang tersimpan di mesin yang sama **tidak melindungi** dari disk
rusak, server hilang, atau ransomware. Ini bagian yang paling sering
dilupakan, dan justru yang menentukan saat kejadian.

Contoh dengan `rclone` (Google Drive, S3, dan lainnya):

```bash
rclone config                      # sekali saja, ikuti panduannya
rclone copy ~/terrabot-backups remote:terrabot-backups
```

Tambahkan ke crontab, satu jam setelah cadangan dibuat:

```cron
0 3 * * * rclone copy /home/daniel/terrabot-backups remote:terrabot-backups
```

---

## Memulihkan

### Menguji cadangan (aman, dianjurkan rutin)

```bash
./scripts/restore_db.sh ~/terrabot-backups/terrabot-20260810-020000.sql.gz
```

Isinya dimasukkan ke basis data terpisah bernama `terrabot_restore_test`.
**Data yang sedang dipakai tidak disentuh.** Ini cara membuktikan cadangannya
benar-benar bisa dipulihkan.

Setelah diperiksa, hapus:

```bash
mysql -e "DROP DATABASE \`terrabot_restore_test\`;"
```

Lakukan ini sebulan sekali. Cadangan yang tidak pernah dicoba dipulihkan
sering kali baru ketahuan bermasalah saat benar-benar dibutuhkan.

### Memulihkan sungguhan

```bash
./scripts/restore_db.sh ~/terrabot-backups/terrabot-20260810-020000.sql.gz --production
```

Skrip akan:

1. Meminta Anda **mengetik nama basis data** sebagai konfirmasi
2. **Mencadangkan kondisi saat ini lebih dulu** — pemulihan yang keliru tidak
   boleh menjadi kehilangan data kedua
3. Baru menimpa isinya

Hentikan aplikasi sebelum memulihkan ke produksi:

```bash
# hentikan backend, lalu:
./scripts/restore_db.sh <berkas> --production
# jalankan backend lagi
```

---

## Pengaturan

Semua lewat variabel lingkungan, tanpa mengubah skrip:

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `BACKUP_DIR` | `$HOME/terrabot-backups` | Tempat menyimpan cadangan |
| `RETENTION_DAYS` | `30` | Cadangan lebih tua dari ini dihapus |
| `ENV_FILE` | `../.env` | Letak berkas `.env` |

Contoh:

```bash
BACKUP_DIR=/mnt/backup RETENTION_DAYS=90 ./scripts/backup_db.sh
```

Cadangan lama dihapus **setelah** cadangan baru terbukti sah — kegagalan hari
ini tidak ikut menghapus cadangan kemarin.

---

## Bila bermasalah

**`DATABASE_URL tidak ditemukan`**
Berkas `.env` tidak terbaca. Tunjuk letaknya:
```bash
ENV_FILE=/path/ke/.env ./scripts/backup_db.sh
```

**`mysqldump: command not found`**
Pasang klien MySQL: `sudo apt install mysql-client`

**`Access denied`**
Pengguna pada `DATABASE_URL` perlu izin `SELECT`, `LOCK TABLES`, dan
`SHOW VIEW` untuk mencadangkan.

**`GAGAL: dump tidak selesai sempurna`**
Sambungan terputus di tengah, atau ruang disk habis. Periksa:
```bash
df -h ~/terrabot-backups
```

---

## Catatan teknis

`mysqldump` dijalankan dengan `--single-transaction`, sehingga cadangan
diambil dari satu titik waktu yang konsisten **tanpa mengunci tabel** —
aplikasi tetap bisa dipakai selama pencadangan berjalan.

Kata sandi dikirim lewat variabel lingkungan `MYSQL_PWD`, bukan argumen baris
perintah. Argumen terlihat oleh semua pengguna di server lewat `ps`.
