#!/usr/bin/env bash
#
# Pemulihan basis data TERRABOT dari berkas cadangan.
#
# Pemakaian:
#   ./scripts/restore_db.sh <berkas.sql.gz>              # ke basis data uji
#   ./scripts/restore_db.sh <berkas.sql.gz> --production # menimpa yang asli
#
# Tanpa --production, isi cadangan dimasukkan ke basis data terpisah
# bernama <nama>_restore_test. Ini cara memastikan cadangan benar-benar bisa
# dipulihkan tanpa menyentuh data yang sedang dipakai.
#
set -euo pipefail

BERKAS="${1:-}"
MODE="${2:-}"
ENV_FILE="${ENV_FILE:-$(dirname "$0")/../.env}"

if [[ -z "$BERKAS" ]]; then
  echo "Pemakaian: $0 <berkas.sql.gz> [--production]" >&2
  exit 1
fi

if [[ ! -f "$BERKAS" ]]; then
  echo "GAGAL: berkas '$BERKAS' tidak ditemukan." >&2
  exit 1
fi

if ! gzip -t "$BERKAS" 2>/dev/null; then
  echo "GAGAL: berkas cadangan rusak." >&2
  exit 1
fi

# ------------------------------------------------------------------- sambungan
if [[ -z "${DATABASE_URL:-}" && -f "$ENV_FILE" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  DATABASE_URL="${DATABASE_URL%\"}"
  DATABASE_URL="${DATABASE_URL#\"}"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "GAGAL: DATABASE_URL tidak ditemukan." >&2
  exit 1
fi

proto_hilang="${DATABASE_URL#*://}"
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

# ----------------------------------------------------------------- tujuan
if [[ "$MODE" == "--production" ]]; then
  TUJUAN="$DB_NAME"
  echo "PERINGATAN: seluruh isi '$TUJUAN' akan DITIMPA."
  echo "Ketik nama basis data untuk melanjutkan:"
  read -r konfirmasi
  if [[ "$konfirmasi" != "$TUJUAN" ]]; then
    echo "Dibatalkan." >&2
    exit 1
  fi

  # Data yang ada dicadangkan lebih dulu — pemulihan yang keliru tidak boleh
  # menjadi kehilangan data kedua.
  echo "Mencadangkan kondisi saat ini sebelum ditimpa ..."
  "$(dirname "$0")/backup_db.sh"
else
  TUJUAN="${DB_NAME}_restore_test"
  echo "Memulihkan ke basis data uji '$TUJUAN' (data asli tidak disentuh)."
fi

MYSQL_PWD="$DB_PASS" mysql \
  --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
  -e "CREATE DATABASE IF NOT EXISTS \`$TUJUAN\` DEFAULT CHARACTER SET utf8mb4;"

echo "Memuat isi cadangan ..."
zcat "$BERKAS" | MYSQL_PWD="$DB_PASS" mysql \
  --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" "$TUJUAN"

JUMLAH="$(MYSQL_PWD="$DB_PASS" mysql --host="$DB_HOST" --port="$DB_PORT" \
  --user="$DB_USER" -N -B \
  -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TUJUAN';")"

echo "Selesai: $JUMLAH tabel dipulihkan ke '$TUJUAN'."

if [[ "$MODE" != "--production" ]]; then
  echo
  echo "Periksa isinya, lalu hapus bila sudah selesai:"
  echo "  mysql -e \"DROP DATABASE \\\`$TUJUAN\\\`;\""
fi
