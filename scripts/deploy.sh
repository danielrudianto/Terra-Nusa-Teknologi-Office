#!/usr/bin/env bash
#
# Deploy TERRABOT — backend.
#
# Menggantikan urutan yang selama ini diketik tangan:
#
#   git pull && pip install && cek_skema && systemctl restart
#
# Bedanya bukan sekadar lebih singkat. Skrip ini BERHENTI pada kegagalan
# pertama. Menempel beberapa perintah sekaligus di terminal tidak melakukan
# itu — bila `git pull` gagal, sisanya tetap berjalan dan yang ter-deploy
# adalah kode lama. Itu sudah pernah terjadi.
#
# Pemakaian:
#   ./scripts/deploy.sh              # tarik, pasang, periksa, nyalakan ulang
#   ./scripts/deploy.sh --periksa    # hanya periksa, tidak mengubah apa pun

set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"

PY="$AKAR/env/bin/python"
LAYANAN="terrabot"

merah()  { printf '\033[31m%s\033[0m\n' "$*"; }
hijau()  { printf '\033[32m%s\033[0m\n' "$*"; }
kuning() { printf '\033[33m%s\033[0m\n' "$*"; }

gagal() {
  merah "GAGAL: $*"
  exit 1
}

HANYA_PERIKSA=0
[[ "${1:-}" == "--periksa" ]] && HANYA_PERIKSA=1

# ---------------------------------------------------------------------
# 0. Prasyarat
# ---------------------------------------------------------------------
[[ -x "$PY" ]] || gagal "virtualenv tidak ditemukan di $AKAR/env"
[[ -f "$AKAR/.env" ]] || gagal ".env tidak ada"

# `sudo git` meninggalkan berkas milik root di dalam .git, dan perintah git
# berikutnya gagal dengan pesan yang tidak menyebut sebabnya.
if [[ ! -w "$AKAR/.git" ]]; then
  gagal ".git tidak dapat ditulis — jalankan: sudo chown -R \$USER:\$USER .git"
fi

# Repo yang belum punya commit membuat seluruh perintah git di bawah gagal
# dengan pesan tentang "ambiguous argument HEAD", yang tidak menyebut
# sebabnya sama sekali.
git rev-parse HEAD > /dev/null 2>&1 || gagal "bukan repo git yang berisi commit"


# ---------------------------------------------------------------------
# 1. Tarik perubahan
# ---------------------------------------------------------------------
if [[ $HANYA_PERIKSA -eq 0 ]]; then
  echo "==> Menarik perubahan"

  # Perubahan lokal menghentikan `git pull` di tengah. Yang paling sering
  # berubah sendiri adalah requirements.txt setelah `pip install`.
  if ! git diff --quiet; then
    kuning "    ada perubahan lokal:"
    git diff --name-only | sed 's/^/      /'
    gagal "bereskan dulu — 'git checkout -- <berkas>' atau commit"
  fi

  SEBELUM="$(git rev-parse HEAD)"
  git pull --ff-only || gagal "git pull ditolak; jalankan 'git pull --rebase' lalu ulangi"
  SESUDAH="$(git rev-parse HEAD)"

  if [[ "$SEBELUM" == "$SESUDAH" ]]; then
    echo "    tidak ada perubahan baru"
  else
    git --no-pager log --oneline "$SEBELUM..$SESUDAH" | sed 's/^/      /'
  fi

  # ---------------------------------------------------------------------
  # 2. Paket
  # ---------------------------------------------------------------------
  if git diff --name-only "$SEBELUM" "$SESUDAH" | grep -q '^requirements.txt$'; then
    echo "==> requirements.txt berubah — memasang"
    # Lewat `python -m pip`, BUKAN `env/bin/pip`: skrip pip di venv ini
    # shebang-nya rusak ("cannot execute: required file not found"),
    # sedangkan modulnya sendiri sehat.
    "$PY" -m pip install -q -r requirements.txt || gagal "pip install"
  fi
fi

# ---------------------------------------------------------------------
# 3. Skema basis data
# ---------------------------------------------------------------------
# Dijalankan SEBELUM layanan dinyalakan ulang. Kolom yang belum ada
# menghasilkan galat 500 yang tidak menyebut kolom mana — jauh lebih mahal
# dicari nanti daripada dicegah sekarang.
echo "==> Memeriksa skema"
"$PY" scripts/cek_skema.py || gagal "skema basis data tidak sesuai"

# ---------------------------------------------------------------------
# 4. Uji
# ---------------------------------------------------------------------
if [[ -d test ]]; then
  echo "==> Menjalankan uji"
  "$PY" -m pytest test/ -q || gagal "ada uji yang tidak lolos"
fi

if [[ $HANYA_PERIKSA -eq 1 ]]; then
  hijau "Pemeriksaan selesai; tidak ada yang diubah."
  exit 0
fi

# ---------------------------------------------------------------------
# 5. Nyalakan ulang
# ---------------------------------------------------------------------
echo "==> Menyalakan ulang $LAYANAN"
sudo systemctl restart "$LAYANAN"

# ---------------------------------------------------------------------
# 6. Uji hidup
# ---------------------------------------------------------------------
# Layanan yang "active" belum tentu melayani. Yang menentukan adalah ia
# menjawab permintaan.
#
# DITUNGGU, bukan diperiksa sekali.
#
# Sebelumnya: `sleep 3` lalu satu kali curl. `--max-time 10` di sana tidak
# menolong — ia membatasi lamanya SATU permintaan, bukan mengulangnya, dan
# koneksi yang ditolak kembali seketika ("after 0 ms"). Padahal start-up
# backend ini memakan tiga detik lebih: memeriksa skema, DESCRIBE tiap
# tabel, lalu memuat CSS WeasyPrint. Tiga detik karena itu tepat di batas —
# kadang lolos, kadang tidak, dan deploy yang sebenarnya berhasil dilaporkan
# GAGAL. Laporan gagal yang tidak benar lebih berbahaya daripada tidak ada
# laporan: yang membacanya berhenti mempercayainya.
PORTA="$(grep -E '^PORT=' .env | cut -d= -f2 || echo 7500)"
PORTA="${PORTA:-7500}"
BATAS_TUNGGU=60

echo "==> Menunggu $LAYANAN menjawab di porta $PORTA"
mulai=$SECONDS
hidup=0
while (( SECONDS - mulai < BATAS_TUNGGU )); do
  # Layanan yang MATI tidak akan pernah menjawab — jangan tunggu sampai
  # habis; sebutkan apa adanya, karena sebab dan penanganannya berbeda.
  if ! sudo systemctl is-active --quiet "$LAYANAN"; then
    merah "Layanan berhenti saat dinyalakan. Enam puluh baris log terakhir:"
    sudo journalctl -u "$LAYANAN" -n 60 --no-pager
    exit 1
  fi

  if curl -fsS --max-time 5 "http://127.0.0.1:${PORTA}/docs" > /dev/null 2>&1; then
    hidup=1
    break
  fi
  sleep 1
done

if [[ $hidup -eq 1 ]]; then
  hijau "Backend hidup di porta ${PORTA} setelah $(( SECONDS - mulai )) detik."
else
  merah "Layanan menyala tetapi tidak menjawab di porta ${PORTA} setelah ${BATAS_TUNGGU} detik."
  sudo journalctl -u "$LAYANAN" -n 60 --no-pager
  exit 1
fi

hijau "Selesai."
