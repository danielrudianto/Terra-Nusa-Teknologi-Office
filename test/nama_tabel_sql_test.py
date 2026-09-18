"""
NAMA TABEL pada kueri SQL MENTAH harus benar-benar ada.

KENAPA PENJAGA INI ADA

`finance_status_repository` sempat menyebut `payments_outgoing` pada dua
kueri, sementara tabelnya bernama `payment_outgoing`. Yang terjadi BUKAN
galat di layar: setiap kueri di berkas itu dibungkus `try/except` yang
mencatat log lalu mengembalikan nol.

Akibatnya "aktual keluar" pada grafik akurasi rencana berbunyi NOL untuk
setiap bulan, dan gaji yang belum cair tidak pernah muncul sebagai
kewajiban — sehingga quick ratio dan modal kerja bersih tampak lebih baik
daripada keadaannya. Grafik yang seluruh batangnya nol terbaca sebagai bulan
yang memang tidak bergerak, bukan sebagai kueri yang gagal.

Uji biasa tidak dapat menangkapnya: tanpa basis data, kuerinya tidak pernah
dijalankan sama sekali.
"""

import os
import re

from sqlalchemy import MetaData

# Memuat seluruh model supaya `metadata` terisi.
import models.purchase_model  # noqa: F401
import models.payment_outgoing_model  # noqa: F401
import models.payment_incoming_model  # noqa: F401
import models.payment_plan_model  # noqa: F401
import models.salary_slip_model  # noqa: F401
import models.expense_model  # noqa: F401
import models.reimbursement_model  # noqa: F401
import models.asset_model  # noqa: F401
import models.sales_invoice_model  # noqa: F401
import models.loans_model  # noqa: F401
import models.certificate_of_payment_model  # noqa: F401
import models.purchase_order_model  # noqa: F401
import models.purchase_order_item_model  # noqa: F401

from utils.database import metadata

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Berkas yang kuerinya diperiksa. Sengaja disebut satu per satu, bukan
#: seluruh repository: yang lain memakai tabel yang belum tentu terdaftar di
#: `metadata` (mis. view `mutation` dan `balance`), dan penjaga yang berisik
#: akan dimatikan orang.
BERKAS = [
    os.path.join(AKAR, "repository", "finance_status_repository.py"),
]

#: Tabel yang memang ADA di basis data tetapi tidak berupa model —
#: view, dan tabel yang dibaca lewat kueri mentah saja.
DIKENAL_DI_LUAR_MODEL = {"mutation", "balance"}

#: HURUF BESAR saja, sengaja: `from x import y` milik Python juga cocok
#: dengan pola ini bila huruf besar-kecilnya diabaikan, dan penjaga yang
#: menyalakan seratus temuan palsu pada baris impor akan dimatikan orang
#: sebelum sempat menangkap yang sungguhan. Seluruh SQL di repo ini memang
#: menulis kata kuncinya dengan huruf besar.
POLA = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b")


def _tabel_terdaftar() -> set:
    return set(metadata.tables.keys()) | DIKENAL_DI_LUAR_MODEL


def test_setiap_nama_tabel_pada_sql_mentah_ada():
    terdaftar = _tabel_terdaftar()
    assert len(terdaftar) > 10, (
        "model tidak termuat; penjaga ini akan meluluskan apa pun"
    )

    temuan = []
    for jalur in BERKAS:
        sumber = open(jalur, encoding="utf-8").read()
        for no, baris in enumerate(sumber.split("\n"), 1):
            for nama in POLA.findall(baris):
                # Nama yang disisipkan dari modelnya (`{TABEL_...}`) sudah
                # benar menurut definisi — itu justru perbaikannya.
                if nama.startswith("{") or nama.upper().startswith("TABEL_"):
                    continue
                # Subkueri diberi alias, bukan nama tabel.
                if nama.lower() in {"select", "dual"}:
                    continue
                if nama not in terdaftar:
                    temuan.append(
                        f"{os.path.relpath(jalur, AKAR)}:{no} -> {nama!r}"
                    )

    assert not temuan, (
        "nama tabel tidak dikenali pada SQL mentah — kuerinya akan gagal "
        "diam-diam dan angkanya menjadi nol:\n  " + "\n  ".join(temuan)
    )


def test_nama_tabel_diambil_dari_modelnya():
    """
    Tetapannya harus BENAR-BENAR membaca `.name` milik modelnya.

    Menuliskannya sebagai teks di tempat yang sama tidak menyelesaikan apa
    pun: ia hanya memindahkan nama yang dapat salah ketik ke satu baris lain,
    dan penggantian nama di model tetap tidak terbawa.
    """
    sumber = open(
        os.path.join(AKAR, "repository", "finance_status_repository.py"),
        encoding="utf-8",
    ).read()
    for tetapan, tabel in (
        ("TABEL_KELUAR", "payments_outgoing_table"),
        ("TABEL_MASUK", "payment_incoming_table"),
        ("TABEL_RENCANA", "payment_plans_table"),
    ):
        assert f"{tetapan} = {tabel}.name" in sumber, (
            f"{tetapan} tidak diambil dari {tabel}.name"
        )
