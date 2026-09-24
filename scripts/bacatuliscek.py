"""
Rute yang MENULIS tetapi dijaga sebagai "read".

MASALAH YANG DIJAGA

Akun pemeriksa (`users.isReadOnly`) ditegakkan satu tempat: `is_allowed()`
menolak setiap aksi selain `read`. Penjagaan itu utuh selama pemetaan
"rute tulis -> aksi tulis" juga utuh.

Satu rute POST yang benar-benar membuat sesuatu tetapi dijaga
`require(..., "read")` menembus seluruhnya — akun yang dibuat untuk membaca
dapat menulis lewat pintu itu, dan tidak ada satu pun galat yang muncul.
Konsultan pajak dan akuntansi memakai akun itu; lubangnya persis di tempat
yang paling tidak boleh bocor.

YANG DIIZINKAN, DAN KENAPA

Sebagian rute memang POST tanpa menulis apa pun: penyaringnya terlalu
panjang untuk querystring, sehingga dikirim di body. Keempatnya sudah
diberi keterangan di tempatnya masing-masing, dan justru harus tetap
terbuka bagi pemeriksa — mutasi bank dan rekap pajak bulanan adalah yang
pertama mereka cari.

Rute tanpa `require()` sama sekali juga ada yang sah: masuk, perpanjang
token, ganti sandi sendiri, dan formulir/ujian yang dibuka lewat TOKEN oleh
orang yang belum punya akun.

Daftarnya ditulis PER RUTE, bukan per berkas: menambah rute baru di berkas
yang sama tidak boleh ikut lolos hanya karena tetangganya lolos.
"""

import pathlib
import re
import sys

POLA_RUTE = re.compile(r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']*)["\']', re.I)
POLA_REQUIRE = re.compile(r'require\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)')

#: Kueri yang kebetulan berkata kerja POST — hanya membaca.
KUERI_POST = {
    ("bank_routes.py", "/mutation"),
    ("bank_routes.py", "/mutation/download"),
    ("payment_outgoing_routes.py", "/mutation"),
    ("tax_routes.py", "/monthly-recap"),
}

#: Rute yang memang terbuka: masuk, token, dan sandi sendiri.
TANPA_IZIN = {
    ("auth_routes.py", "/"),
    ("auth_routes.py", "/refresh"),
    ("employee_form_routes.py", "/isi/{token}"),
    ("hr_recruitment_routes.py", "/exam/{token}/biodata"),
    ("hr_recruitment_routes.py", "/exam/{token}/mulai"),
    ("hr_recruitment_routes.py", "/exam/{token}/jawaban"),
    ("hr_recruitment_routes.py", "/exam/{token}/kirim"),
    ("push_routes.py", "/subscribe"),
    ("push_routes.py", "/unsubscribe"),
    ("user_routes.py", "/me/password"),
}


def periksa(akar: str = "routes") -> list[str]:
    masalah = []
    for berkas in sorted(pathlib.Path(akar).glob("*.py")):
        baris = berkas.read_text(errors="ignore").split("\n")
        for i, b in enumerate(baris):
            m = POLA_RUTE.search(b)
            if not m:
                continue
            metode, jalur = m.group(1).lower(), m.group(2)
            if metode == "get":
                continue

            kunci = (berkas.name, jalur)
            # Penjaganya dicari pada tanda tangan fungsinya — 25 baris cukup
            # untuk seluruh rute di basis kode ini.
            blok = "\n".join(baris[i : i + 25])
            r = POLA_REQUIRE.search(blok)

            if r is None:
                if kunci not in TANPA_IZIN:
                    masalah.append(
                        f"{berkas.name}:{i + 1}: {metode.upper()} {jalur} "
                        f"tanpa require() — akun hanya-baca tidak tertahan"
                    )
                continue

            if r.group(2) == "read" and kunci not in KUERI_POST:
                masalah.append(
                    f"{berkas.name}:{i + 1}: {metode.upper()} {jalur} dijaga "
                    f'require("{r.group(1)}", "read") — bila ia menulis, '
                    f"akun hanya-baca menembusnya"
                )
    return masalah


if __name__ == "__main__":
    h = periksa()
    print(f"rute tulis berpenjaga baca: {len(h)}")
    print()
    for x in h[:30]:
        print(f"  {x}")
    sys.exit(1 if h else 0)
