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


def unik_model() -> dict[str, set[tuple[str, ...]]]:
    """
    Tabel -> himpunan indeks UNIK yang disebut model.

    Dibaca dari `UniqueConstraint(...)` dan `unique=True` pada Column.
    """
    akar = os.path.join(AKAR, "models")
    hasil: dict[str, set[tuple[str, ...]]] = {}
    for p in sorted(glob(os.path.join(akar, "*.py"))):
        s = open(p).read()
        for m in re.finditer(r'(\w+)\s*=\s*Table\(\s*\n?\s*[\'"](\w+)[\'"]', s):
            nama = m.group(2)
            awal = m.end()
            lanjut = s.find("= Table(", awal)
            blok = s[awal:lanjut] if lanjut != -1 else s[awal:]

            kunci: set[tuple[str, ...]] = set()

            # `name=` DIBUANG dari daftar kolom.
            #
            # `UniqueConstraint("code", name="uq_projects_code")` memuat dua
            # teks berkutip, dan yang kedua adalah nama constraint-nya —
            # bukan kolom. Menghitungnya sebagai kolom membuat setiap
            # constraint bernama dilaporkan tidak cocok dengan basis data.
            for u in re.finditer(r'UniqueConstraint\(([^)]*)\)', blok):
                isi = re.sub(r'name\s*=\s*[\'"][^\'"]*[\'"]', '', u.group(1))
                kolom = tuple(sorted(re.findall(r'[\'"](\w+)[\'"]', isi)))
                if kolom:
                    kunci.add(kolom)

            # Definisi kolom dibaca sampai kurung penutupnya yang SEIMBANG.
            #
            # `[^)]*` berhenti pada kurung tutup pertama — dan `String(100)`
            # sudah memuat satu, sehingga `unique=True` di belakangnya tidak
            # pernah terlihat. Akibatnya seluruh kolom unik dilaporkan
            # sebagai indeks asing.
            for m2 in re.finditer(r'Column\(\s*[\'"](\w+)[\'"]', blok):
                i = m2.end()
                dalam, akhir = 1, len(blok)
                for n, ch in enumerate(blok[i:]):
                    if ch == '(':
                        dalam += 1
                    elif ch == ')':
                        dalam -= 1
                        if dalam == 0:
                            akhir = i + n
                            break
                if re.search(r'unique\s*=\s*True', blok[i:akhir]):
                    kunci.add((m2.group(1),))
                # Kunci utama SENGAJA tidak dihitung.
                #
                # Sisi basis data mengecualikannya lewat `INDEX_NAME <>
                # 'PRIMARY'`, sehingga menghitungnya di sisi model membuat
                # setiap tabel melapor kekurangan satu indeks — tiga puluh
                # lima temuan yang seluruhnya kolom `id`.
                #
                # Kedua sisi harus mengecualikan hal yang sama; yang
                # dibandingkan di sini hanya indeks unik SELAIN kunci utama.
            hasil[nama] = kunci
    return hasil


async def unik_basis_data(tabel: str) -> set[tuple[str, ...]] | None:
    """
    Indeks UNIK yang benar-benar ada di basis data.

    Kunci utama dikecualikan: ia selalu unik dan tidak pernah dinyatakan
    sebagai `UniqueConstraint` di model.
    """
    try:
        baris = await database.fetch_all(
            """
            SELECT INDEX_NAME, COLUMN_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :t
              AND NON_UNIQUE = 0
              AND INDEX_NAME <> 'PRIMARY'
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """,
            {"t": tabel},
        )
    except Exception:
        return None

    per_indeks: dict[str, list[str]] = {}
    for b in baris:
        per_indeks.setdefault(b["INDEX_NAME"], []).append(b["COLUMN_NAME"])
    return {tuple(sorted(v)) for v in per_indeks.values()}


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

        # Indeks UNIK yang ada di basis data tetapi tidak di model.
        #
        # Ini yang paling berbahaya di antara semua ketidakcocokan: kolom
        # yang hilang gagal seketika dan langsung ketahuan, sedangkan indeks
        # unik yang tidak diketahui baru menolak ketika seseorang menyimpan
        # baris KEDUA — kadang berminggu-minggu setelah dipasang.
        #
        # Sudah terjadi: `uq_submission` membatasi satu jawaban formulir per
        # karyawan, padahal kode sengaja menyimpan tiap pembaruan sebagai
        # baris baru demi riwayatnya. Yang memperbarui data untuk kedua
        # kalinya menerima galat 500 tanpa keterangan.
        unik_harapan = unik_model()
        unik_asing: list[tuple[str, tuple[str, ...]]] = []
        unik_kurang: list[tuple[str, tuple[str, ...]]] = []

        for tabel in harapan:
            ada = await unik_basis_data(tabel)
            if ada is None:
                continue
            diminta = unik_harapan.get(tabel, set())
            for u in sorted(ada - diminta):
                unik_asing.append((tabel, u))
            for u in sorted(diminta - ada):
                unik_kurang.append((tabel, u))

        print(f"tabel diperiksa : {len(harapan)}")
        print(f"tabel hilang    : {len(tabel_hilang)}")
        print(f"kolom hilang    : {len(kolom_hilang)}")
        print(f"kolom berlebih  : {len(kolom_lebih)}")
        print(f"unik asing      : {len(unik_asing)}")
        print(f"unik kurang     : {len(unik_kurang)}")
        print()

        for t in tabel_hilang:
            print(f"  TABEL HILANG  {t}")
        for t, k in kolom_hilang:
            print(f"  KOLOM HILANG  {t}.{k}")
        for t, k in kolom_lebih:
            print(f"  BERLEBIH      {t}.{k}")
        for t, u in unik_asing:
            # Indeks unik pada kolom kunci utama adalah kelebihan, bukan
            # batasan yang belum dinyatakan: kunci utamanya sudah menjamin
            # keunikannya. Dibedakan supaya tidak diperlakukan sama dengan
            # temuan yang benar-benar membatasi penyimpanan.
            catatan = "  (kelebihan; kunci utama sudah menjaminnya)" if u == ("id",) else ""
            print(f"  UNIK ASING    {t} ({', '.join(u)}){catatan}")
        for t, u in unik_kurang:
            print(f"  UNIK KURANG   {t} ({', '.join(u)})")

        # Indeks unik MEMPERINGATKAN, tidak menghentikan deploy.
        #
        # Kolom yang hilang pasti menggagalkan setiap permintaan yang
        # menyentuhnya — menghentikan deploy di situ menyelamatkan. Indeks
        # unik berbeda: sebagian memang disengaja dan hanya belum dinyatakan
        # di model, dan menolak seluruh deploy karenanya berarti perbaikan
        # yang sudah benar ikut tertahan.
        #
        # Yang diperlukan adalah temuannya TERLIHAT, bukan deploy yang
        # berhenti.
        if unik_asing or unik_kurang:
            print()
            print("PERINGATAN: indeks unik di basis data tidak sesuai model.")
            print()
            print("  UNIK ASING menolak baris kedua yang menurut kode sah,")
            print("  dengan galat 500 yang tidak menyebut sebabnya. Buang bila")
            print("  memang tidak dikehendaki:")
            print("    ALTER TABLE <tabel> DROP INDEX <nama>;")
            print()
            print("  Bila indeksnya dipakai foreign key, buat indeks biasa")
            print("  untuk kolom itu lebih dulu — MySQL menolak membuang")
            print("  satu-satunya indeks yang menopang sebuah foreign key.")
            print()
            print("  Deploy DILANJUTKAN; ini peringatan, bukan penghalang.")

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
