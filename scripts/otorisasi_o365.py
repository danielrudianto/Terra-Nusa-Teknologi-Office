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

CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")

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
    print()

    backend = FileSystemTokenBackend(
        token_path=TOKEN_PATH, token_filename=TOKEN_FILENAME
    )
    account = Account((CLIENT_ID, CLIENT_SECRET), token_backend=backend)

    if account.authenticate(scopes=SCOPES):
        print()
        print("BERHASIL. Token baru tersimpan.")
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
