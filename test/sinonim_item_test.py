"""
Sinonim pencarian katalog barang.

Meilisearch memperlakukan sinonim SEARAH: mendaftarkan "hitam" -> ["black"]
membuat pencarian "hitam" menemukan "black", tetapi tidak sebaliknya.

Kesalahan seperti itu tidak menimbulkan galat apa pun — hanya pencarian yang
diam-diam tidak menemukan apa pun dari satu arah, dan yang mencarinya
menyimpulkan barangnya belum ada lalu membuat entri kembar.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMBER = open(os.path.join(AKAR, "utils", "meilisearch_item.py")).read()

_ns: dict = {}
_i = SUMBER.index("_PASANGAN = [")
_j = SUMBER.index("item_synonyms = _dua_arah")
exec(compile(SUMBER[_i:_j], "sinonim", "exec"), _ns)

PASANGAN = _ns["_PASANGAN"]
PETA = _ns["_dua_arah"](PASANGAN)


def _terhubung(a: str, b: str) -> bool:
    return b.lower() in [x.lower() for x in PETA.get(a.lower(), [])]


def test_setiap_pasangan_dua_arah():
    """
    Setiap istilah menemukan setiap istilah lain dalam kelompoknya.

    Diperiksa menyeluruh, bukan pada beberapa contoh: satu arah yang terlewat
    tidak terlihat sampai ada yang mencarinya dari sisi itu.
    """
    kurang = []
    for utama, lainnya in PASANGAN:
        semua = [utama, *lainnya]
        for a in semua:
            for b in semua:
                if a.lower() == b.lower():
                    continue
                if not _terhubung(a, b):
                    kurang.append(f"{a} -/-> {b}")
    assert not kurang, "; ".join(kurang[:10])


def test_warna_dasar_ada():
    """Warna paling sering dipakai memilah barang sejenis."""
    for en, idn in (
        ("black", "hitam"),
        ("white", "putih"),
        ("red", "merah"),
        ("green", "hijau"),
        ("blue", "biru"),
        ("yellow", "kuning"),
    ):
        assert _terhubung(en, idn), en
        assert _terhubung(idn, en), idn


def test_sebutan_lapangan_terhubung():
    """
    Sebutan lapangan yang tidak menyerupai istilah resminya.

    "kuku macan" tidak punya satu pun kata yang sama dengan "wire rope clip";
    tanpa sinonim, yang mencarinya tidak akan pernah menemukannya walaupun
    barangnya ada di katalog.
    """
    assert _terhubung("kuku macan", "wire rope clip")
    assert _terhubung("klem seling", "wire rope clip")
    assert _terhubung("wire rope clip", "kuku macan")


def test_soket_menjangkau_seluruh_ejaan():
    """`stopkontak`, `stop kontak`, `socket`, dan `soket` satu kelompok."""
    for a in ("soket", "socket", "stopkontak", "stop kontak"):
        for b in ("soket", "socket", "stopkontak", "stop kontak"):
            if a != b:
                assert _terhubung(a, b), f"{a} -> {b}"


def test_tidak_ada_istilah_kosong_atau_ganda():
    """Istilah kosong membuat Meilisearch menolak seluruh pengaturannya."""
    for utama, lainnya in PASANGAN:
        semua = [utama, *lainnya]
        assert all(x.strip() for x in semua), utama
        kecil = [x.lower() for x in semua]
        assert len(kecil) == len(set(kecil)), f"{utama}: ada yang berulang"


def test_dipasang_saat_setup():
    """Peta sinonim benar-benar dikirim ke Meilisearch, bukan hanya disusun."""
    assert "index.update_synonyms(item_synonyms)" in SUMBER
