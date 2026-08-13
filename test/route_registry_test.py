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
