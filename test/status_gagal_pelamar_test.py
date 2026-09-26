"""
Dua jenis gagal pelamar: `ditolak` (sebelum wawancara) dan `gagal_wawancara`
(sesudahnya). Keduanya boleh disetel manusia, dan keduanya masuk ember
"ditolak" — satu pelamar tetap hanya di satu ember.
"""

from sqlalchemy.dialects import mysql

from repository.hr_recruitment_repository import (
    STATUS_GAGAL,
    STATUS_MANUAL,
    _syarat_ember,
)


def _sql(syarat) -> str:
    return " AND ".join(
        str(s.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
        for s in syarat
    )


def test_gagal_wawancara_boleh_disetel_manusia():
    assert "gagal_wawancara" in STATUS_MANUAL
    assert len("gagal_wawancara") <= 20  # kolom status String(20)


def test_ember_ditolak_memuat_kedua_jenis_gagal():
    sql = _sql(_syarat_ember("ditolak"))
    for st in STATUS_GAGAL:
        assert f"'{st}'" in sql


def test_ember_lain_tidak_memuat_gagal_wawancara():
    for ember in ("submit", "wawancara", "diterima"):
        assert "gagal_wawancara" not in _sql(_syarat_ember(ember))
