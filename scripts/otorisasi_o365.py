"""
Otorisasi ulang token Microsoft 365.

Dijalankan MANUAL di server, sekali, ketika:

- client secret di Azure diganti — token lama diterbitkan dengan secret yang
  lama dan tidak dapat diperbarui lagi; gejalanya
  `Refresh token operation failed: invalid_client`
- token terhapus atau rusak

TIDAK dipanggil dari kode aplikasi. Alur otorisasinya menunggu masukan di
konsol, dan di dalam proses server yang menunggu itu menggantung selamanya:
permintaannya tidak pernah menjawab, dan yang menekan tombol hanya melihat
layar berputar tanpa akhir.

Cara menjalankan, dari akar backend:

    cd /var/www/terrabot/backend
    source env/bin/activate
    python scripts/otorisasi_o365.py

Skrip akan menampilkan sebuah tautan. Buka di peramban, masuk dengan akun
surel yang dipakai mengirim, setujui izinnya, lalu SALIN SELURUH ALAMAT
halaman yang muncul sesudahnya — termasuk bagian setelah tanda tanya — dan
tempelkan kembali ke konsol.

Halaman tujuannya kemungkinan menampilkan galat atau halaman kosong. Itu
normal: yang diperlukan hanya alamatnya, bukan isinya.
"""

import os
import sys

from dotenv import load_dotenv
from O365 import Account, FileSystemTokenBackend

# Dijalankan dari akar backend, sehingga `.env` dan `storage/` sejajar.
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Dipinjam dari `mail_service`, TIDAK disalin.
#
# Dua salinan pembacaan token akan berbeda pada pemutakhiran O365 berikutnya —
# dan yang berbeda adalah skrip ini dengan yang benar-benar dipakai mengirim,
# sehingga layar di sini menyatakan hijau untuk keadaan yang ditolak backend.
from services.mail_service import alamat_pengirim  # noqa: E402

CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MAIL_FROM = (os.getenv("MAIL_FROM") or "").strip().lower()

# Sama persis dengan yang dipakai `services/mail_service.py`.
#
# Berbeda sedikit saja — jalur, nama berkas, atau scope — dan aplikasinya akan
# mencari token di tempat yang tidak pernah diisi skrip ini.
TOKEN_PATH = "storage/tokens"
TOKEN_FILENAME = "o365_token.txt"
SCOPES = ["message_all"]


def utama() -> int:
    if not CLIENT_ID or not CLIENT_SECRET:
        print(
            "GAGAL: MICROSOFT_CLIENT_ID atau MICROSOFT_CLIENT_SECRET belum "
            "terbaca.\n"
            "Jalankan dari akar backend, bukan dari dalam folder scripts."
        )
        return 1

    print(f"Client ID    : {CLIENT_ID[:8]}…")
    print(f"Token disimpan ke: {TOKEN_PATH}/{TOKEN_FILENAME}")
    if MAIL_FROM:
        print(f"HARUS masuk sebagai: {MAIL_FROM}")
    else:
        print(
            "PERINGATAN: MAIL_FROM belum diisi di .env, jadi tidak ada yang\n"
            "            dapat memeriksa akun mana yang benar. Akun yang Anda\n"
            "            pakai masuk sebentar lagi akan menjadi PENGIRIM\n"
            "            seluruh surel sistem."
        )
    print()

    backend = FileSystemTokenBackend(
        token_path=TOKEN_PATH, token_filename=TOKEN_FILENAME
    )
    account = Account((CLIENT_ID, CLIENT_SECRET), token_backend=backend)

    if account.authenticate(scopes=SCOPES):
        print()
        print("BERHASIL. Token baru tersimpan.")

        # Akun yang baru saja masuk DISEBUTKAN, tidak dibiarkan tersirat.
        #
        # Di sinilah alamat pengirim seluruh sistem sebenarnya ditentukan, dan
        # sampai sekarang layarnya tidak pernah menyebut akun mana yang dipakai.
        # Masuk dengan akun yang salah karena itu terasa persis sama dengan
        # masuk dengan akun yang benar — dan selisihnya baru terlihat berhari
        # kemudian, di kotak masuk orang lain.
        pengirim = alamat_pengirim(account)
        print()
        print(f"Pengirim sekarang: {pengirim or '(tidak terbaca)'}")

        if MAIL_FROM and pengirim and pengirim != MAIL_FROM:
            print()
            print("AKUNNYA SALAH.")
            print(f"  MAIL_FROM di .env : {MAIL_FROM}")
            print(f"  yang barusan masuk: {pengirim}")
            print()
            print("Seluruh surel sistem akan keluar atas nama akun itu, dan")
            print("backend akan MENOLAK mengirim selama keduanya berbeda.")
            print()
            print("Ulangi:")
            print(f"    rm {TOKEN_PATH}/{TOKEN_FILENAME}")
            print("    python scripts/otorisasi_o365.py")
            return 1

        print()
        print("Hidupkan ulang backend supaya membacanya:")
        print("    sudo systemctl restart terrabot")
        return 0

    print()
    print("GAGAL. Periksa:")
    print("  - client secret di .env sama dengan Value di Azure")
    print("  - Redirect URI di Azure memuat alamat yang muncul di peramban")
    return 1


if __name__ == "__main__":
    sys.exit(utama())
