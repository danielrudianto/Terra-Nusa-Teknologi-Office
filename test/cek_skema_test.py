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


# ----------------------------------------------------------------------
# Indeks unik: kedua bentuk penulisannya harus terbaca
# ----------------------------------------------------------------------


def _unik_model():
    """Jalankan `unik_model()` dari skrip apa adanya."""
    src = open(os.path.join(AKAR, "scripts", "cek_skema.py")).read()
    i = src.index("def unik_model()")
    j = src.index("#: Indeks unik yang memang HANYA")
    ns = {"os": os, "re": re, "glob": glob, "AKAR": AKAR}
    exec(compile(src[i:j], "cek_skema", "exec"), ns)
    return ns["unik_model"]()


def test_index_unique_true_ikut_terbaca():
    """
    `Index(..., unique=True)` menyatakan indeks unik, sama seperti
    `UniqueConstraint`.

    Kolom TEXT tidak dapat dijadikan `UniqueConstraint` di MySQL — ia
    menuntut panjang prefix, dan itu hanya dapat dinyatakan lewat
    `Index(..., mysql_length=...)`. `push_subscriptions (endpoint)` memakai
    bentuk itu.

    Selama bentuk ini tidak dikenali, indeks yang SUDAH dinyatakan model
    dilaporkan sebagai indeks asing pada setiap deploy — dan laporan yang
    selalu memuat temuan yang selalu boleh diabaikan mengajari pembacanya
    mengabaikan seluruh laporannya.
    """
    u = _unik_model()
    assert ("endpoint",) in u.get("push_subscriptions", set()), (
        "`Index(..., unique=True)` tidak terbaca; indeks yang sudah "
        "dinyatakan model akan dilaporkan sebagai indeks asing"
    )


def test_nama_indeks_tidak_dihitung_sebagai_kolom():
    """
    Argumen pertama `Index(...)` adalah NAMA indeksnya, bukan kolom.

    Menghitungnya sebagai kolom membuat setiap indeks bernama dilaporkan
    tidak cocok dengan basis data — kegagalan yang sama persis dengan yang
    dulu terjadi pada `UniqueConstraint(..., name=...)`.
    """
    u = _unik_model()
    assert ("endpoint", "uq_push_endpoint") not in u.get(
        "push_subscriptions", set()
    )
    assert ("uq_push_endpoint",) not in u.get("push_subscriptions", set())


def test_indeks_non_unik_tidak_ikut():
    """`Index(...)` tanpa `unique=True` bukan indeks unik."""
    u = _unik_model()
    # `purchases` punya beberapa indeks biasa (masa pajak, CoP) dan TIDAK
    # punya satu pun indeks unik yang dinyatakan model.
    assert not u.get("purchases"), (
        f"indeks biasa ikut terbaca sebagai unik: {u.get('purchases')}"
    )


def test_jawaban_ujian_satu_per_soal():
    """
    Satu pelamar, satu soal, satu jawaban.

    `simpan_jawaban` dipanggil BERKALA oleh layar ujian dan menyimpannya
    dengan pola baca-lalu-ubah-atau-sisipkan. Dua penyimpanan yang bertumpang
    tindih menyisipkan dua baris untuk soal yang sama, dan yang menilai
    kemudian melihat satu soal terjawab dua kali dengan isi berbeda — tanpa
    cara menentukan mana yang terakhir.
    """
    u = _unik_model()
    assert ("candidateID", "questionID") in u.get("hr_answers", set())
