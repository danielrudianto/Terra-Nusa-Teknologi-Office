#!/usr/bin/env bash
#
# Deploy TERRABOT — frontend.
#
# Membangun dari sumber lalu menyalin hasilnya ke folder yang disajikan
# Nginx. Berhenti pada kegagalan pertama, dan MEMERIKSA hasil build sebelum
# menyalin — build Angular dapat "berhasil" tanpa menyalin berkas yang
# diperlukan, dan itu baru terasa ketika halamannya dibuka.
#
# Pemakaian:
#   ./deploy-fe.sh            # tarik, pasang, bangun, salin
#   ./deploy-fe.sh --lewati-tarik
#
# Ditaruh di /var/www/terrabot/ (di luar repo), karena skrip ini mengurus
# dua folder sekaligus dan bukan bagian dari kode aplikasi.

set -euo pipefail

SUMBER="/var/www/terrabot/frontend-src"
TUJUAN="/var/www/terrabot/frontend"
PROYEK="terra-nusa-teknologi-office-frontend"

merah()  { printf '\033[31m%s\033[0m\n' "$*"; }
hijau()  { printf '\033[32m%s\033[0m\n' "$*"; }
kuning() { printf '\033[33m%s\033[0m\n' "$*"; }

gagal() {
  merah "GAGAL: $*"
  exit 1
}

LEWATI_TARIK=0
[[ "${1:-}" == "--lewati-tarik" ]] && LEWATI_TARIK=1

cd "$SUMBER" || gagal "folder sumber tidak ada: $SUMBER"

# ---------------------------------------------------------------------
# 1. Tarik perubahan
# ---------------------------------------------------------------------
if [[ $LEWATI_TARIK -eq 0 ]]; then
  echo "==> Menarik perubahan"

  # `npm install` mengubah package-lock.json, dan itu menghentikan `git pull`
  # di tengah. Berkas itu selalu boleh dibuang di server: yang berlaku adalah
  # yang ada di repo.
  if ! git diff --quiet -- package-lock.json; then
    kuning "    package-lock.json berubah setempat — dikembalikan"
    git checkout -- package-lock.json
  fi

  if ! git diff --quiet; then
    kuning "    ada perubahan lokal lain:"
    git diff --name-only | sed 's/^/      /'
    gagal "bereskan dulu"
  fi

  SEBELUM="$(git rev-parse HEAD)"
  git pull --ff-only || gagal "git pull ditolak; jalankan 'git pull --rebase'"
  SESUDAH="$(git rev-parse HEAD)"

  if [[ "$SEBELUM" == "$SESUDAH" ]]; then
    echo "    tidak ada perubahan baru"
  else
    git --no-pager log --oneline "$SEBELUM..$SESUDAH" | sed 's/^/      /'
  fi
fi

# ---------------------------------------------------------------------
# 2. Paket — HANYA saat berubah
# ---------------------------------------------------------------------
echo "==> Menyelaraskan paket"

# `npm ci` MENGHAPUS node_modules lalu memasang ulang dari nol SETIAP kali
# dipanggil. Di server kecil itu satu-dua menit yang terbuang bila paketnya
# tidak berubah sama sekali — dan paket jarang berubah antar deploy.
#
# Karena itu pemasangan hanya dijalankan bila `package-lock.json` benar-benar
# berbeda dari yang terpasang terakhir, atau bila node_modules memang belum
# ada. Sidik jari lock disimpan DI DALAM node_modules: begitu foldernya dibuang
# (mis. `npm ci` yang mengulang), penandanya ikut hilang, sehingga tidak pernah
# ada yang "dilewati" di atas folder yang sebetulnya kosong.
#
# `npm ci` (bukan `npm install`) tetap dipakai saat memang memasang: ia menolak
# bila lock tidak sejalan dengan package.json — yang di server justru
# diinginkan, supaya yang terpasang persis sama dengan yang diuji.
PENANDA="node_modules/.deploy-lock-hash"
LOCK_SEKARANG="$(sha256sum package-lock.json | awk '{print $1}')"

pasang() {
  if ! npm ci --silent; then
    kuning "    npm ci gagal — membersihkan node_modules dan mengulang"
    rm -rf node_modules
    npm ci --silent || gagal "npm ci"
  fi
  # Penanda ditulis SESUDAH pemasangan berhasil — bila build/pemasangan
  # terputus, penanda lama tidak tertinggal menipu deploy berikutnya.
  echo "$LOCK_SEKARANG" > "$PENANDA"
}

if [[ -d node_modules && -f "$PENANDA" && "$(cat "$PENANDA" 2>/dev/null)" == "$LOCK_SEKARANG" ]]; then
  echo "    paket tidak berubah — pemasangan dilewati"
else
  echo "    paket berubah atau node_modules belum ada — memasang"
  pasang
fi

# ---------------------------------------------------------------------
# 3. Bangun
# ---------------------------------------------------------------------
echo "==> Membangun (perlu beberapa menit)"

# Build Angular memerlukan memori besar, sering di atas 2 GB. Pada server
# kecil, yang dibunuh sistem saat kehabisan memori sering justru MySQL —
# bukan proses build-nya. Peringatan ini muncul sebelum hal itu terjadi.
TERSEDIA_MB="$(free -m | awk '/^Mem:/ {print $7}')"
if [[ "${TERSEDIA_MB:-0}" -lt 2048 ]]; then
  kuning "    memori tersedia hanya ${TERSEDIA_MB} MB; build dapat terhenti"
  kuning "    pertimbangkan menambah swap, atau bangun di mesin lain"
fi

# Cache build Angular (.angular/cache) SENGAJA TIDAK dibuang: ia menyimpan
# hasil kompilasi berkas yang tidak berubah, dan itulah yang membuat build
# kedua dan seterusnya jauh lebih cepat daripada yang pertama. Membersihkannya
# tiap deploy membuat setiap build dingin dari nol. Bila suatu saat cache
# tampak rusak (jarang), cukup hapus manual: `rm -rf .angular/cache`.

# `npm run build`, BUKAN `npx ng build`.
#
# Yang pertama menjalankan `prebuild` lebih dulu — dan `prebuild` itulah yang
# menuliskan `src/app/versi.ts` dengan tanggal serta commit build ini.
# `npx ng build` melewatinya, sehingga aplikasi menampilkan keterangan versi
# dari build yang lain — atau gagal sama sekali bila berkasnya belum ada.
npm run build -- --configuration production || gagal "build"

HASIL="$SUMBER/dist/$PROYEK/browser"
[[ -d "$HASIL" ]] || gagal "folder hasil tidak ada: $HASIL"

# ---------------------------------------------------------------------
# 4. Periksa hasil SEBELUM menyalin
# ---------------------------------------------------------------------
# Entri `assets` yang tidak menemukan berkasnya TIDAK menggagalkan build —
# Angular hanya tidak menyalin apa pun. Worker PDF pernah hilang dengan cara
# ini, dan baru terasa ketika seseorang membuka halaman PDF.
echo "==> Memeriksa hasil build"

WAJIB=(
  "index.html"
  "assets/pdf.worker.min.mjs"
)
for berkas in "${WAJIB[@]}"; do
  [[ -f "$HASIL/$berkas" ]] || gagal "hasil build tidak memuat $berkas"
  echo "    ada: $berkas"
done

# ---------------------------------------------------------------------
# 5. Salin
# ---------------------------------------------------------------------
echo "==> Menyalin ke $TUJUAN"
mkdir -p "$TUJUAN"

# `--delete` membuang berkas lama yang sudah tidak dihasilkan lagi. Tanpa
# itu, potongan build lama menumpuk dan suatu saat ada yang termuat.
#
# `frontend-mobile` DIKECUALIKAN. Folder itu deploy terpisah
# (`deploy-fe-mobile.sh`) yang kebetulan berada di dalam tujuan ini; tanpa
# pengecualian, `--delete` membuangnya setiap kali desktop dideploy, dan
# aplikasi mobile lenyap tanpa ada yang menyentuhnya. Cabang cp di bawah
# menyalin ke dalam folder tanpa mengosongkan seluruhnya, agar folder mobile
# ikut selamat di sana.
if command -v rsync > /dev/null; then
  rsync -a --delete --exclude=frontend-mobile "$HASIL/" "$TUJUAN/"
else
  # Membuang isi SATU per satu, melewati frontend-mobile — bukan
  # `rm -rf "$TUJUAN"/*`, yang ikut menghapusnya.
  find "$TUJUAN" -mindepth 1 -maxdepth 1 ! -name frontend-mobile \
    -exec rm -rf {} +
  cp -a "$HASIL/." "$TUJUAN/"
fi

[[ -f "$TUJUAN/index.html" ]] || gagal "penyalinan tidak menghasilkan index.html"

# ---------------------------------------------------------------------
# 6. Uji hidup
# ---------------------------------------------------------------------
# Diuji dengan NAMA DOMAINnya, bukan 127.0.0.1.
#
# Nginx melayani lebih dari satu domain dari mesin yang sama, dan permintaan
# tanpa `Host` yang cocok jatuh ke blok server pertama — yang belum tentu
# frontend ini. Pemeriksaan tanpa domain karena itu melaporkan 404 pada
# deploy yang sebenarnya berhasil, dan peringatan yang keliru membuat
# peringatan berikutnya ikut diabaikan.
DOMAIN="${DOMAIN_FRONTEND:-terrabot.alphakonstruksi.id}"

if curl -fsS --max-time 10 -o /dev/null "https://${DOMAIN}/"; then
  hijau "Frontend tersaji di https://${DOMAIN}"
else
  kuning "Berkas tersalin, tetapi https://${DOMAIN} tidak menjawab."
  kuning "Periksa: sudo nginx -t && sudo systemctl status nginx"
fi

hijau "Selesai."
echo
echo "Bila tampilannya tidak berubah di peramban, tekan Ctrl+Shift+R sekali."
