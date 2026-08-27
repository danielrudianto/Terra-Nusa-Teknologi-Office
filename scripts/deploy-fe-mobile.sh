#!/usr/bin/env bash
#
# Deploy TERRABOT — frontend MOBILE (m.terrabot.alphakonstruksi.id).
#
# Kembaran `deploy-fe.sh`, dengan tiga beda yang semuanya disengaja:
#
#   1. Sasaran buildnya `--configuration mobile`, keluar ke
#      `dist/frontend-mobile/browser`.
#   2. Tujuannya `frontend/frontend-mobile`, di DALAM folder desktop.
#   3. Karena itu, `deploy-fe.sh` HARUS mengecualikan `frontend-mobile` dari
#      penghapusannya — kalau tidak, deploy desktop membuang folder ini setiap
#      kali dijalankan. Pengecualian itu sudah dipasang di sana; skrip ini
#      hanya mengingatkannya bila hilang.
#
# Membangun dari sumber lalu menyalin hasilnya ke folder yang disajikan
# Nginx. Berhenti pada kegagalan pertama, dan MEMERIKSA hasil build sebelum
# menyalin — build Angular dapat "berhasil" tanpa menyalin index.html, dan
# itu baru terasa ketika halamannya dibuka.
#
# Pemakaian:
#   ./deploy-fe-mobile.sh            # tarik, pasang, bangun, salin
#   ./deploy-fe-mobile.sh --lewati-tarik
#
# Ditaruh di scripts/ repo backend bersama deploy-fe.sh, karena keduanya
# mengurus folder di luar repo dan bukan bagian dari kode aplikasi.

set -euo pipefail

SUMBER="/var/www/terrabot/frontend-src"
TUJUAN="/var/www/terrabot/frontend/frontend-mobile"

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
# tidak berubah — dan paket jarang berubah antar deploy.
#
# Pemasangan karena itu hanya dijalankan bila `package-lock.json` benar-benar
# berbeda dari yang terpasang terakhir, atau bila node_modules belum ada.
# Penandanya sama persis dengan yang dipakai `deploy-fe.sh`, dan keduanya
# BERBAGI node_modules yang sama (sama-sama dari frontend-src) — sehingga
# setelah salah satunya memasang, yang lain melewatinya.
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
echo "==> Membangun mobile (perlu beberapa menit)"

# Build Angular memerlukan memori besar. Pada server kecil, yang dibunuh
# sistem saat kehabisan memori sering justru MySQL — bukan proses build-nya.
TERSEDIA_MB="$(free -m | awk '/^Mem:/ {print $7}')"
if [[ "${TERSEDIA_MB:-0}" -lt 2048 ]]; then
  kuning "    memori tersedia hanya ${TERSEDIA_MB} MB; build dapat terhenti"
  kuning "    pertimbangkan menambah swap, atau bangun di mesin lain"
fi

# Cache build Angular (.angular/cache) SENGAJA TIDAK dibuang: ia menyimpan
# hasil kompilasi berkas yang tidak berubah, dan itulah yang membuat build
# kedua dan seterusnya jauh lebih cepat daripada yang pertama. Bila suatu saat
# cache tampak rusak (jarang), cukup hapus manual: `rm -rf .angular/cache`.

# `npm run build`, BUKAN `npx ng build`.
#
# Yang pertama menjalankan `prebuild:mobile` lebih dulu — dan itulah yang
# menuliskan `src/app/versi.ts` dengan tanggal serta commit build ini. Tanpa
# itu aplikasi mobile melaporkan versi build yang lain, dan penelusuran galat
# menunjuk ke commit yang salah.
npm run build -- --configuration mobile || gagal "build"

# Angular menaruh hasilnya di sub-folder `browser`, bukan langsung di
# `dist/frontend-mobile`. Menyalin dari yang salah menghasilkan folder tanpa
# index.html — persis kegagalan yang pertama kali ditemui.
HASIL="$SUMBER/dist/frontend-mobile/browser"
[[ -d "$HASIL" ]] || gagal "folder hasil tidak ada: $HASIL"

# ---------------------------------------------------------------------
# 4. Periksa hasil SEBELUM menyalin
# ---------------------------------------------------------------------
# Berkas index diberi nama `index.mobile.html` di sumbernya, dan hanya keluar
# sebagai `index.html` bila `angular.json` menyetel `index.output`. Bila
# setelan itu hilang, buildnya tetap "berhasil" tetapi menghasilkan
# `index.mobile.html` — dan Nginx yang mencari `index.html` membalas 404 pada
# deploy yang tampak sukses.
echo "==> Memeriksa hasil build"

[[ -f "$HASIL/index.html" ]] || gagal \
  "hasil build tidak memuat index.html (cek angular.json: index.output pada konfigurasi mobile)"
echo "    ada: index.html"

# ---------------------------------------------------------------------
# 5. Salin
# ---------------------------------------------------------------------
echo "==> Menyalin ke $TUJUAN"
mkdir -p "$TUJUAN"

# `--delete` di sini AMAN: sasarannya folder mobile itu sendiri, bukan
# induknya. Yang berbahaya adalah `--delete` pada `frontend/` di deploy
# desktop — lihat catatan di kepala berkas ini.
if command -v rsync > /dev/null; then
  rsync -a --delete "$HASIL/" "$TUJUAN/"
else
  rm -rf "${TUJUAN:?}/"*
  cp -a "$HASIL/." "$TUJUAN/"
fi

[[ -f "$TUJUAN/index.html" ]] || gagal "penyalinan tidak menghasilkan index.html"

# ---------------------------------------------------------------------
# 6. Ingatkan bila deploy desktop akan menghapus folder ini
# ---------------------------------------------------------------------
# Folder mobile berada di DALAM sasaran deploy desktop. Bila `deploy-fe.sh`
# tidak mengecualikannya, deploy desktop berikutnya membuangnya — dan mobile
# lenyap tanpa ada yang menyentuhnya.
DESKTOP_DEPLOY="$(dirname "$0")/deploy-fe.sh"
if [[ -f "$DESKTOP_DEPLOY" ]] && ! grep -q "exclude=frontend-mobile" "$DESKTOP_DEPLOY"; then
  kuning "PERINGATAN: deploy-fe.sh belum mengecualikan frontend-mobile."
  kuning "Deploy desktop berikutnya akan MENGHAPUS $TUJUAN."
  kuning "Tambahkan --exclude=frontend-mobile pada rsync di deploy-fe.sh."
fi

# ---------------------------------------------------------------------
# 7. Uji hidup
# ---------------------------------------------------------------------
# Diuji dengan NAMA DOMAINnya, bukan 127.0.0.1: nginx melayani lebih dari
# satu domain, dan permintaan tanpa Host yang cocok jatuh ke blok server
# pertama — yang belum tentu mobile ini.
DOMAIN="${DOMAIN_MOBILE:-m.terrabot.alphakonstruksi.id}"

# Dicoba https dulu, lalu http: sebelum certbot dijalankan, mobile baru
# tersaji di http, dan uji https yang gagal di situ bukan tanda kesalahan.
if curl -fsS --max-time 10 -o /dev/null "https://${DOMAIN}/"; then
  hijau "Mobile tersaji di https://${DOMAIN}"
elif curl -fsS --max-time 10 -o /dev/null "http://${DOMAIN}/"; then
  kuning "Mobile tersaji di http://${DOMAIN} — sertifikat belum dipasang."
  kuning "Jalankan: sudo certbot --nginx -d ${DOMAIN}"
  kuning "Setelah itu, tambahkan https://${DOMAIN} ke daftar CORS backend."
else
  kuning "Berkas tersalin, tetapi ${DOMAIN} tidak menjawab."
  kuning "Periksa: sudo nginx -t && sudo systemctl status nginx"
  kuning "Dan pastikan DNS 'm' sudah menunjuk ke IP server ini."
fi

hijau "Selesai."
echo
echo "Bila tampilannya tidak berubah di ponsel, tekan muat-ulang keras sekali."
