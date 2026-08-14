"""
Cocokkan kolom yang diharapkan model dengan kolom yang benar-benar ada di
basis data.

Dibuat setelah satu SQL migrasi terlewat dijalankan: kolomnya tidak ada,
backend gagal pada setiap penyimpanan, dan galatnya keluar sebagai penolakan
biasa yang tidak menyebut sebabnya sama sekali. Yang terlihat pengguna hanya
"Anda tidak memiliki akses" — pesan yang menyesatkan ke arah izin, bukan ke
arah skema.

Jalankan setelah menarik perubahan, SEBELUM menjalankan servernya:

    python3 scripts/cek_skema.py

Keluar dengan kode 1 bila ada kolom yang kurang, sehingga bisa dipasang di
skrip start bila diinginkan.
"""

import asyncio
import os
import re
import sys
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AKAR)

# `.env` DIMUAT SENDIRI sebelum apa pun mengimpor utils.database.
#
# Servernya dijalankan dengan variabel lingkungan yang sudah tersedia, tetapi
# skrip yang dipanggil langsung tidak — dan `utils/database.py` melempar
# ValueError saat diimpor bila DATABASE_URL kosong, sehingga skripnya gagal
# sebelum satu baris pun berjalan.
#
# Dibaca manual, bukan lewat python-dotenv, agar skrip ini tetap berjalan
# pada lingkungan yang paketnya belum terpasang.
def _muat_env() -> None:
    if os.getenv("DATABASE_URL"):
        return
    berkas = os.path.join(AKAR, ".env")
    if not os.path.exists(berkas):
        return
    for baris in open(berkas):
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, nilai = baris.split("=", 1)
        nilai = nilai.strip().strip('"').strip("'")
        os.environ.setdefault(kunci.strip(), nilai)


_muat_env()

if not os.getenv("DATABASE_URL"):
    raise SystemExit(
        "DATABASE_URL tidak ditemukan. Jalankan dari akar proyek dengan "
        "berkas .env, atau setel variabelnya lebih dulu."
    )

from utils.database import database  # noqa: E402


def kolom_model() -> dict[str, list[str]]:
    """Tabel -> daftar kolom, dibaca dari berkas model."""
    akar = os.path.join(AKAR, "models")
    hasil: dict[str, list[str]] = {}
    for p in sorted(glob(os.path.join(akar, "*.py"))):
        s = open(p).read()
        # SETIAP Table() dalam berkas, bukan hanya yang pertama.
        #
        # Satu berkas boleh memuat lebih dari satu tabel — dan yang kedua
        # akan luput diam-diam bila hanya yang pertama dicari, sehingga
        # kolomnya tidak pernah diperiksa. Sudah terjadi sekali pada
        # employee_form_submissions.
        for m in re.finditer(r'(\w+)\s*=\s*Table\(\s*\n?\s*[\'"](\w+)[\'"]', s):
            awal = m.end()
            # kolom sampai Table() berikutnya, bila ada
            lanjut = s.find("= Table(", awal)
            blok = s[awal:lanjut] if lanjut != -1 else s[awal:]
            # Kutip TUNGGAL maupun ganda diterima.
            #
            # Sebagian model ditulis dengan kutip tunggal. Pola yang hanya
            # menerima kutip ganda melewatkan seluruh kolomnya, lalu — sejak
            # pemeriksaan arah sebaliknya ada — melaporkan semuanya sebagai
            # "berlebih". Laporannya tampak seperti masalah basis data,
            # padahal masalah pemeriksanya sendiri.
            #
            # Spasi dan baris baru setelah `Column(` juga diterima: definisi
            # panjang kerap ditulis multi-baris.
            kolom = re.findall(r"""Column\(\s*['"](\w+)['"]""", blok)
            if kolom:
                hasil[m.group(2)] = kolom
    return hasil


async def kolom_basis_data(nama_tabel: str) -> set[str] | None:
    """Kolom yang benar-benar ada; None bila tabelnya sendiri tidak ada."""
    # Kueri diberikan sebagai STRING, bukan dibungkus `text()`.
    #
    # `databases` membungkusnya sendiri lalu memasang `bindparams`. Bila
    # sudah berupa TextClause, ia justru memanggil `.values(**values)` —
    # metode yang hanya dimiliki INSERT/UPDATE, sehingga melempar
    # AttributeError yang tidak menyebut sebabnya.
    rows = await database.fetch_all(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t",
        {"t": nama_tabel},
    )
    if not rows:
        return None
    return {r["COLUMN_NAME"] for r in rows}


async def main() -> int:
    try:
        await database.connect()
    except Exception as e:
        # Sambungan gagal bukan berarti skemanya salah; membedakannya penting
        # agar orang tidak mencari kolom yang hilang padahal servernya mati.
        print("GAGAL menyambung ke basis data.")
        print(f"  {type(e).__name__}: {e}")
        print()
        print("Periksa DATABASE_URL dan apakah MySQL sedang berjalan.")
        return 2

    try:
        harapan = kolom_model()
        tabel_hilang: list[str] = []
        kolom_hilang: list[tuple[str, str]] = []
        kolom_lebih: list[tuple[str, str]] = []

        for tabel, kolom in harapan.items():
            ada = await kolom_basis_data(tabel)
            if ada is None:
                tabel_hilang.append(tabel)
                continue
            for k in kolom:
                if k not in ada:
                    kolom_hilang.append((tabel, k))
            # Arah sebaliknya: kolom yang ada di basis data tetapi sudah
            # tidak ada di model.
            #
            # Tidak merusak apa pun — tidak ada yang membacanya — sehingga
            # tanpa pemeriksaan ini ia tinggal diam-diam selamanya. Yang
            # menjadikannya penting: isinya tetap tersimpan. Kolom data
            # pribadi yang sudah diputuskan dibuang tetapi masih memuat
            # datanya adalah keadaan terburuk dari keduanya — tidak dipakai,
            # tetapi tetap ada.
            #
            # Dilaporkan sebagai PERINGATAN, bukan kegagalan: server tetap
            # berjalan benar, dan menghentikan penyebaran karenanya akan
            # membuat pemeriksa ini diabaikan.
            for k in ada:
                if k not in kolom:
                    kolom_lebih.append((tabel, k))

        print(f"tabel diperiksa : {len(harapan)}")
        print(f"tabel hilang    : {len(tabel_hilang)}")
        print(f"kolom hilang    : {len(kolom_hilang)}")
        print(f"kolom berlebih  : {len(kolom_lebih)}")
        print()

        for t in tabel_hilang:
            print(f"  TABEL HILANG  {t}")
        for t, k in kolom_hilang:
            print(f"  KOLOM HILANG  {t}.{k}")
        for t, k in kolom_lebih:
            print(f"  BERLEBIH      {t}.{k}")

        if kolom_lebih and not (tabel_hilang or kolom_hilang):
            print()
            print("Kolom berlebih tidak merusak apa pun — tidak ada yang")
            print("membacanya. Tetapi isinya tetap tersimpan; bila memuat data")
            print("pribadi yang sudah diputuskan dibuang, hapus kolomnya.")
            print()
            print("  Skema sesuai dengan model.")
            return 0

        if tabel_hilang or kolom_hilang:
            print()
            print("Ada migrasi yang belum dijalankan. Server akan gagal pada")
            print("setiap operasi yang menyentuh kolom tersebut, dengan galat")
            print("yang tidak menyebut sebabnya.")
            return 1

        print("  Skema sesuai dengan model.")
        return 0
    finally:
        await database.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
