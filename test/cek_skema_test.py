"""
Pemeriksa skema harus membaca SELURUH model.

Pemeriksa yang melewatkan sebagian model jauh lebih buruk daripada tidak
ada pemeriksa: laporannya bersih, dan kepercayaan atas laporan itu membuat
orang berhenti memeriksa sendiri.

Sudah tiga kali salah:
  1. hanya `Table()` PERTAMA tiap berkas yang dibaca — satu tabel luput,
  2. `Column(` multi-baris tidak cocok — satu kolom luput per tabel,
  3. hanya kutip GANDA yang diterima — dua belas kolom satu tabel luput,
     lalu dilaporkan sebagai "berlebih" seolah masalahnya di basis data.
"""

import os
import re
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _peta_model():
    """Jalankan `kolom_model()` dari skrip apa adanya."""
    src = open(os.path.join(AKAR, "scripts", "cek_skema.py")).read()
    i = src.index("def kolom_model()")
    j = src.index("async def kolom_basis_data")
    ns = {"os": os, "re": re, "glob": glob, "AKAR": AKAR}
    exec(compile(src[i:j], "cek_skema", "exec"), ns)
    return ns["kolom_model"]()


def test_setiap_tabel_terbaca():
    """
    Setiap `Table()` dalam berkas model harus muncul di petanya.

    Termasuk tabel kedua dan seterusnya dalam satu berkas yang sama.
    """
    peta = _peta_model()
    for p in glob(os.path.join(AKAR, "models", "*.py")):
        s = open(p).read()
        for m in re.finditer(r"""=\s*Table\(\s*\n?\s*['"](\w+)['"]""", s):
            # `autoload_with=engine` berarti kolomnya dibaca dari basis data,
            # bukan didaftarkan di kode. `mutation` adalah VIEW MySQL yang
            # dipakai kalender; ia memang tidak punya `Column()` satu pun,
            # dan tidak ada yang dapat dibandingkan untuknya.
            blok = s[m.end() : s.find("= Table(", m.end())]
            if "autoload_with" in blok[:200]:
                continue
            assert m.group(1) in peta, f"{os.path.basename(p)}: {m.group(1)} luput"


def test_jumlah_kolom_cocok_dengan_berkasnya():
    """
    Jumlah kolom yang terbaca harus sama dengan yang tertulis.

    Dihitung ulang dengan pola yang sengaja longgar — kutip apa pun, spasi
    apa pun — lalu dibandingkan. Selisih berarti pemeriksanya melewatkan
    sesuatu, apa pun sebabnya.
    """
    peta = _peta_model()
    LONGGAR = re.compile(r"""Column\(\s*['"](\w+)['"]""")

    for p in glob(os.path.join(AKAR, "models", "*.py")):
        s = open(p).read()
        tabel = re.findall(r"""=\s*Table\(\s*\n?\s*['"](\w+)['"]""", s)
        if len(tabel) != 1:
            # Berkas bertabel jamak dipisah per blok; dicakup uji di atas.
            continue
        nyata = len(LONGGAR.findall(s))
        terbaca = len(peta.get(tabel[0], []))
        assert terbaca == nyata, (
            f"{os.path.basename(p)}: terbaca {terbaca}, tertulis {nyata}"
        )


def test_model_kutip_tunggal_ikut_terbaca():
    """
    Model berkutip tunggal tidak boleh diperlakukan berbeda.

    `expense_opponents` ditulis dengan kutip tunggal dan sempat terbaca
    hanya satu kolom dari tiga belas.
    """
    peta = _peta_model()
    assert len(peta.get("expense_opponents", [])) >= 13
