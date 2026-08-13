"""
Pengujian kelengkapan pendaftaran.

`routes/routes.py` dan `constants/permission_matrix.py` adalah dua berkas
yang disentuh setiap kali ada fitur baru — dan karena itu dua berkas yang
paling sering tertimpa ketika dua orang bekerja bersamaan.

Kehilangannya tidak menimbulkan galat saat aplikasi dijalankan: rutenya
sekadar tidak ada, dan gejalanya muncul sebagai 404 di layar pengguna, atau
sebagai 403 yang tidak masuk akal. Pengujian ini menangkapnya sebelum
sampai ke sana.

Bila ada yang gagal di sini, hampir selalu jawabannya sama: satu blok di
`routes.py` atau satu baris di matriks hilang saat menggabungkan perubahan.
"""

import re
from pathlib import Path

import pytest

from constants.permission_matrix import ACTIONS, MATRIX

AKAR = Path(__file__).resolve().parents[1]


def _isi(relatif: str) -> str:
    return (AKAR / relatif).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Setiap berkas rute harus terdaftar
# ---------------------------------------------------------------------------


def _berkas_rute() -> list[str]:
    """Berkas rute yang seharusnya aktif, kecuali yang sengaja tidak dipakai."""
    dilewati = {
        "routes.py",
        "__init__.py",
        # Berkas mati: salinan asset_routes dengan modul yang tidak ada di
        # matriks. Ditandai di berkasnya sendiri.
        "attendance_routes.py",
    }
    return sorted(
        p.name
        for p in (AKAR / "routes").glob("*.py")
        if p.name not in dilewati
    )


def test_semua_berkas_rute_terdaftar():
    """
    Rute yang ada berkasnya tetapi tidak didaftarkan menghasilkan 404 pada
    seluruh endpoint-nya — tanpa satu pun pesan galat saat aplikasi start.
    """
    daftar = _isi("routes/routes.py")
    hilang = []

    for berkas in _berkas_rute():
        nama = berkas.replace("_routes.py", "")
        if f"routes.{nama}_routes" not in daftar:
            hilang.append(berkas)

    assert not hilang, f"belum didaftarkan di routes.py: {', '.join(hilang)}"


def test_setiap_router_diimpor_juga_dipasang():
    """Impor tanpa `include_router` sama saja dengan tidak terdaftar."""
    daftar = _isi("routes/routes.py")
    diimpor = set(re.findall(r"import router as (\w+)", daftar))
    dipasang = set(re.findall(r"include_router\(\s*(\w+)", daftar))

    assert diimpor == dipasang, (
        f"diimpor tetapi tidak dipasang: {sorted(diimpor - dipasang)}; "
        f"dipasang tetapi tidak diimpor: {sorted(dipasang - diimpor)}"
    )


def test_tidak_ada_prefix_kembar():
    """Dua router pada prefix yang sama membuat salah satunya tak terjangkau."""
    daftar = _isi("routes/routes.py")
    prefix = re.findall(r'include_router\([^,]+,\s*prefix="([^"]+)"', daftar)
    kembar = {p for p in prefix if prefix.count(p) > 1}

    assert not kembar, f"prefix dipakai lebih dari sekali: {sorted(kembar)}"


# ---------------------------------------------------------------------------
# Setiap modul yang dijaga harus ada di matriks
# ---------------------------------------------------------------------------


def _izin_dipakai() -> set[tuple[str, str]]:
    hasil: set[tuple[str, str]] = set()
    for p in (AKAR / "routes").glob("*.py"):
        if p.name == "attendance_routes.py":
            continue
        hasil |= set(
            re.findall(r'require\(\s*"([^"]+)"\s*,\s*"([^"]+)"', p.read_text(encoding="utf-8"))
        )
    return hasil


def test_modul_yang_dijaga_ada_di_matriks():
    """
    Modul yang tidak ada di matriks membuat SELURUH endpoint-nya selalu
    ditolak — 403 tanpa sebab yang terlihat, meski penggunanya direktur.
    """
    asing = sorted({m for m, _ in _izin_dipakai() if m not in MATRIX})
    assert not asing, f"dipakai di rute tetapi tidak ada di matriks: {asing}"


def test_aksi_yang_dijaga_dikenali():
    tidak_dikenal = sorted({a for _, a in _izin_dipakai() if a not in ACTIONS})
    assert not tidak_dikenal, f"aksi tidak dikenal: {tidak_dikenal}"


def test_aksi_yang_dijaga_tidak_bernilai_nol():
    """Nilai 0 berarti aksi itu tidak berlaku — menjaganya berarti menolak selamanya."""
    mati = sorted(
        f"{m}:{a}"
        for m, a in _izin_dipakai()
        if m in MATRIX and a in ACTIONS and MATRIX[m][ACTIONS.index(a)] == 0
    )
    assert not mati, f"dijaga izin yang tidak pernah terpenuhi: {mati}"


# ---------------------------------------------------------------------------
# Perbaikan yang pernah hilang saat penggabungan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "berkas,penanda,keterangan",
    [
        (
            "routes/auth_routes.py",
            '"id": result["id"]',
            "id pengguna dikirim saat login; dipakai layar untuk mengenali diri sendiri",
        ),
        (
            "routes/auth_routes.py",
            '"name": result["name"]',
            "nama ikut di refresh token; tanpanya jejak aktivitas kehilangan pelaku",
        ),
        (
            "routes/permission_routes.py",
            '"departments"',
            "divisi dikirim ke layar; membedakan orang keuangan dari orang tanpa divisi",
        ),
        (
            "routes/dashboard_routes.py",
            'require("bank", "read")',
            "posisi kas dijaga bank:read, bukan dashboard:read",
        ),
        (
            "routes/calendar_routes.py",
            'require("payment_outgoing", "read")',
            "kalender memuat jadwal pembayaran, dijaga seperti data pembayaran",
        ),
    ],
)
def test_perbaikan_tidak_hilang(berkas, penanda, keterangan):
    assert penanda in _isi(berkas), f"hilang dari {berkas}: {keterangan}"


# ---------------------------------------------------------------------------
# Kolom yang dirujuk harus ada pada modelnya
# ---------------------------------------------------------------------------


def test_kolom_yang_dirujuk_ada_di_model():
    """
    Merujuk kolom yang sudah tidak ada membuat seluruh endpoint-nya gagal
    dengan galat yang hanya menyebut nama kolomnya — tanpa menyebut berkas
    maupun barisnya.

    Terjadi ketika sebuah kolom diganti: `project_contracts.value` pernah
    diganti menjadi `dpp` + `ppn`, sementara penjumlahannya di daftar proyek
    masih memakai nama lama. Akibatnya seluruh halaman proyek balas 500.
    """
    import glob

    # Nama variabel tabel -> kolom yang dimilikinya.
    peta: dict[str, set[str]] = {}
    for berkas in (AKAR / "models").glob("*.py"):
        isi = berkas.read_text(encoding="utf-8")
        for m in re.finditer(r'(\w+)\s*=\s*Table\(\s*"(\w+)"(.*?)\n\)', isi, re.S):
            var, _, badan = m.groups()
            peta[var] = set(re.findall(r'Column\(\s*"(\w+)"', badan))

    # Fungsi mati yang sudah ditandai di berkasnya sendiri; dikecualikan
    # agar pengujian ini menyorot kekeliruan yang benar-benar aktif.
    DIKECUALIKAN = {("utils/auth_utils.py", "users_table.c.username")}

    salah = []
    for berkas in glob.glob(str(AKAR / "**" / "*.py"), recursive=True):
        if "/env/" in berkas or "/test" in berkas:
            continue
        for no, baris in enumerate(
            Path(berkas).read_text(encoding="utf-8").split("\n"), 1
        ):
            if baris.lstrip().startswith("#"):
                continue
            for m in re.finditer(r"(\w+)\.c\.(\w+)", baris):
                var, kolom = m.groups()
                if var in peta and peta[var] and kolom not in peta[var]:
                    rel = Path(berkas).relative_to(AKAR)
                    if (str(rel), f"{var}.c.{kolom}") in DIKECUALIKAN:
                        continue
                    salah.append(f"{rel}:{no} -> {var}.c.{kolom}")

    assert not salah, "kolom tidak ada pada modelnya:\n  " + "\n  ".join(salah)


def test_model_menerima_field_yang_dikirim_repository():
    """
    Pydantic membuang field yang tidak dikenal tanpa memberi tahu.

    `get_payment_by_id` mengirim `id=` ke `PaymentOutgoing` yang tidak
    memiliki field itu; objeknya terbentuk tanpa galat, dan kekeliruannya
    baru muncul ketika ada yang membaca `.id` — jauh dari tempat asalnya,
    sebagai "object has no attribute 'id'".

    Pengujian ini memeriksa setiap model yang dibentuk dengan `id=` di
    repository benar-benar memiliki field tersebut.
    """
    import glob
    import importlib

    from pydantic import BaseModel

    model_punya_id: dict[str, bool] = {}
    for berkas in (AKAR / "models").glob("*.py"):
        nama_modul = f"models.{berkas.stem}"
        try:
            modul = importlib.import_module(nama_modul)
        except Exception:
            continue
        for nama in dir(modul):
            kelas = getattr(modul, nama)
            if (
                isinstance(kelas, type)
                and issubclass(kelas, BaseModel)
                and kelas is not BaseModel
                and kelas.__module__ == nama_modul
            ):
                model_punya_id[nama] = "id" in kelas.model_fields

    salah = []
    for berkas in glob.glob(str(AKAR / "repository" / "*.py")):
        isi = Path(berkas).read_text(encoding="utf-8")
        for nama, punya in model_punya_id.items():
            if punya:
                continue
            if re.search(nama + r"\(\s*\n?\s*id=", isi):
                salah.append(f"{Path(berkas).name} -> {nama}(id=...)")

    assert not salah, "model dibentuk dengan id= tetapi tidak punya field id:\n  " + "\n  ".join(salah)
