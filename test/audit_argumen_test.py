"""
Argumen pemanggilan jejak audit.

`AuditLogRepository.record` sudah tahan galat: kegagalan menulis jejak tidak
menggagalkan operasinya. Tetapi ARGUMENnya disusun di luar fungsi itu, dan
galat di sana terjadi sebelum penjagaannya berlaku.

Akibatnya khas dan sulit dilacak: datanya sudah tersimpan, lalu penyusunan
argumen melempar KeyError, lalu try/except di sekelilingnya mengubahnya
menjadi "Internal server error". Penggunanya melihat gagal, mencoba lagi,
dan tersimpan dua kali. Persis yang terjadi pada `add_contract`.
"""

import ast
import os
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pemanggilan_audit(pohon):
    """Setiap panggilan `AuditLogRepository.record(...)` dalam satu berkas."""
    for simpul in ast.walk(pohon):
        if not isinstance(simpul, ast.Call):
            continue
        f = simpul.func
        if isinstance(f, ast.Attribute) and f.attr == "record":
            if isinstance(f.value, ast.Name) and f.value.id == "AuditLogRepository":
                yield simpul


def test_entity_id_bukan_kunci_dict_masukan():
    """
    `entityID` tidak boleh dibaca dari dict yang datang sebagai masukan.

    Dict masukan hanya memuat apa yang dikirim pemanggilnya. Nilai seperti
    `projectID` kerap disisipkan terpisah saat menyimpan, sehingga tidak
    pernah ada di dalamnya — dan membacanya dari sana melempar KeyError.

    Dict hasil BACA dari tabel aman, karena kolomnya pasti ada. Yang
    dilarang di sini hanya nama yang menandakan masukan.
    """
    MASUKAN = {"data", "values", "payload", "body", "muatan"}
    pelanggaran = []

    for p in glob(os.path.join(AKAR, "repository", "*.py")):
        pohon = ast.parse(open(p).read())
        for panggil in _pemanggilan_audit(pohon):
            for kw in panggil.keywords:
                if kw.arg != "entityID":
                    continue
                for n in ast.walk(kw.value):
                    if (
                        isinstance(n, ast.Subscript)
                        and isinstance(n.value, ast.Name)
                        and n.value.id in MASUKAN
                    ):
                        pelanggaran.append(
                            f"{os.path.basename(p)}:{panggil.lineno} "
                            f"entityID={n.value.id}[...]"
                        )

    assert not pelanggaran, "entityID dibaca dari dict masukan: " + "; ".join(
        pelanggaran
    )


def test_record_menangkap_galatnya_sendiri():
    """
    Kegagalan MENULIS jejak tidak boleh menggagalkan operasinya.

    Jejak audit adalah catatan pendamping; kehilangannya buruk, tetapi
    menggagalkan penyimpanan yang sudah berhasil jauh lebih buruk.
    """
    p = os.path.join(AKAR, "repository", "audit_log_repository.py")
    pohon = ast.parse(open(p).read())

    ketemu = False
    for simpul in ast.walk(pohon):
        if isinstance(simpul, ast.AsyncFunctionDef) and simpul.name == "record":
            ketemu = True
            assert any(
                isinstance(x, ast.Try) for x in simpul.body
            ), "record() tidak membungkus isinya dengan try/except"
    assert ketemu, "record() tidak ditemukan"
