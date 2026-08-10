#!/usr/bin/env bash
#
# Cadangan basis data TERRABOT.
#
# Dijalankan terjadwal (lihat crontab di bagian bawah berkas ini). Skrip ini
# sengaja tidak menyimpan kata sandi di dalam kode: sambungan dibaca dari
# DATABASE_URL yang sudah dipakai aplikasi.
#
# Pemakaian:
#   ./scripts/backup_db.sh              # cadangan sekali jalan
#   ./scripts/backup_db.sh --verify     # cadangan lalu uji hasilnya
#
set -euo pipefail

# ---------------------------------------------------------------- konfigurasi
BACKUP_DIR="${BACKUP_DIR:-$HOME/terrabot-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENV_FILE="${ENV_FILE:-$(dirname "$0")/../.env}"

# ------------------------------------------------------------------- sambungan
# DATABASE_URL berbentuk: mysql://pengguna:sandi@host:port/nama_basis_data
if [[ -z "${DATABASE_URL:-}" && -f "$ENV_FILE" ]]; then
  # Hanya baris DATABASE_URL yang diambil, agar isi .env lain tidak ikut
  # masuk ke lingkungan skrip ini.
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  DATABASE_URL="${DATABASE_URL%\"}"
  DATABASE_URL="${DATABASE_URL#\"}"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "GAGAL: DATABASE_URL tidak ditemukan (cek $ENV_FILE)." >&2
  exit 1
fi

proto_hilang="${DATABASE_URL#*://}"

# Dipisah pada '@' TERAKHIR, bukan yang pertama: kata sandi boleh memuat '@'
# dan pemisahan dari kiri akan memotongnya di tengah.
kredensial="${proto_hilang%@*}"
sisanya="${proto_hilang##*@}"

DB_USER="${kredensial%%:*}"
DB_PASS="${kredensial#*:}"
hostport="${sisanya%%/*}"
DB_HOST="${hostport%%:*}"
DB_PORT="${hostport#*:}"
[[ "$DB_PORT" == "$DB_HOST" ]] && DB_PORT=3306
DB_NAME="${sisanya#*/}"
DB_NAME="${DB_NAME%%\?*}"

# -------------------------------------------------------------------- cadangan
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/${DB_NAME}-${STAMP}.sql.gz"

echo "Mencadangkan '$DB_NAME' dari $DB_HOST:$DB_PORT ..."

# Kata sandi dikirim lewat variabel lingkungan, bukan argumen baris perintah:
# argumen terlihat oleh semua pengguna lewat `ps`.
MYSQL_PWD="$DB_PASS" mysqldump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --events \
  --set-gtid-purged=OFF \
  --default-character-set=utf8mb4 \
  "$DB_NAME" | gzip -9 > "$FILE.tmp"

# Berkas diberi nama akhir hanya setelah mysqldump selesai tanpa galat,
# supaya cadangan yang terputus di tengah tidak tersimpan sebagai cadangan sah.
mv "$FILE.tmp" "$FILE"

UKURAN="$(du -h "$FILE" | cut -f1)"
echo "Selesai: $FILE ($UKURAN)"

# --------------------------------------------------------------- uji hasilnya
# Cadangan yang tidak pernah diuji sama saja dengan tidak punya cadangan.
if ! gzip -t "$FILE" 2>/dev/null; then
  echo "GAGAL: berkas cadangan rusak." >&2
  rm -f "$FILE"
  exit 1
fi

if ! zcat "$FILE" | tail -5 | grep -q "Dump completed"; then
  echo "GAGAL: dump tidak selesai sempurna." >&2
  rm -f "$FILE"
  exit 1
fi

JUMLAH_TABEL="$(zcat "$FILE" | grep -c '^CREATE TABLE' || true)"
echo "Berisi $JUMLAH_TABEL tabel."

if [[ "$JUMLAH_TABEL" -lt 5 ]]; then
  echo "GAGAL: jumlah tabel tidak wajar, cadangan kemungkinan tidak lengkap." >&2
  rm -f "$FILE"
  exit 1
fi

# ------------------------------------------------------------------ pembersihan
# Cadangan lama dihapus SETELAH cadangan baru terbukti sah, supaya kegagalan
# hari ini tidak ikut menghapus cadangan kemarin.
HAPUS="$(find "$BACKUP_DIR" -name "${DB_NAME}-*.sql.gz" -mtime "+$RETENTION_DAYS" -print -delete | wc -l)"
[[ "$HAPUS" -gt 0 ]] && echo "Menghapus $HAPUS cadangan lebih tua dari $RETENTION_DAYS hari."

echo "OK."

# ---------------------------------------------------------------------- jadwal
# Tambahkan ke crontab agar berjalan setiap hari pukul 02:00:
#
#   crontab -e
#   0 2 * * * /path/ke/scripts/backup_db.sh >> $HOME/terrabot-backups/backup.log 2>&1
#
# Cadangan di mesin yang sama TIDAK melindungi dari kerusakan disk atau
# kehilangan server. Salin berkasnya ke tempat lain, misalnya:
#
#   0 3 * * * rclone copy $HOME/terrabot-backups remote:terrabot-backups
