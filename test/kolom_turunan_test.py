"""
Kolom turunan yang tidak boleh dipercayakan kepada kiriman layar.

Tiga temuan dari sapuan 24 Sep 2026, satu bentuk yang sama: dokumen
menyimpan SALINAN kolom milik dokumen lain, sebagai teks, bukan tautan.
Tidak ada penjaga basis data yang menolak salinan yang keliru — yang
terjadi hanya angka yang duduk di baris yang salah, tanpa galat.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _isi(rel: str) -> str:
    with open(os.path.join(AKAR, rel), encoding="utf-8") as f:
        return f.read()


def test_beban_punya_daftar_kolom_boleh_ubah():
    """
    `expenses` satu-satunya tabel dokumen tanpa daftar kolom boleh-ubah.

    Akibat terjauhnya `isPaid`: satu permintaan menandai setoran PPN lunas
    tanpa ada pembayaran di belakangnya. `isPaid` pada beban dihitung
    `PaymentOutgoingController`, bukan dikirim layar.
    """
    s = _isi("repository/expense_repository.py")
    blok = s[s.index("async def update(expense_id"):][:4000]

    assert "BOLEH = {" in blok, "daftar kolom boleh-ubah hilang dari ExpenseRepository.update"

    daftar = blok[blok.index("BOLEH = {") : blok.index("}", blok.index("BOLEH = {"))]
    for terlarang in ("isPaid", "isDelete", "createdBy", "createdAt", "id"):
        assert f'"{terlarang}"' not in daftar, (
            f"`{terlarang}` masuk daftar kolom boleh-ubah beban"
        )

    assert "if k in BOLEH" in blok, "daftarnya ada tetapi tidak dipakai menyaring"


def test_cop_mengambil_proyek_dari_spk_bukan_dari_layar():
    """
    Deret nomor CoP mengurut per VENDOR DAN PROYEK, dan kode proyeknya ikut
    tercetak pada namanya. Proyek yang keliru mengambil nomor dari deret
    proyek lain — dan penomoran memakai MAX, tidak pernah memakai ulang,
    sehingga nomor itu hangus selamanya bagi pemiliknya.

    Vendornya sudah diambil dari SPK sejak awal; proyeknya tertinggal.
    """
    s = _isi("controllers/certificate_of_payment_controller.py")
    i = s.index("hasil = await CertificateOfPaymentRepository.create(")
    blok = re.sub(r"#[^\n]*", "", s[i : s.index("\n                },\n", i)])

    assert '"projectName": spk.get("projectName")' in blok
    assert 'data.get("projectName")' not in blok, (
        "proyek CoP kembali dibaca dari kiriman layar"
    )
    # Vendornya tidak boleh ikut bergeser saat ini dibetulkan.
    assert '"supplierID": spk.get("supplierID")' in blok


def test_penjaga_ganti_kode_proyek_menghitung_rencana_pengeluaran():
    """
    `payment_plans` satu-satunya tabel ber-`projectName` yang biasa sudah
    terisi KETIKA BELUM ADA DOKUMEN SAMA SEKALI — modelnya sendiri
    menyebutnya ("rencana dibuat sebelum dokumennya ada"). Justru itu
    keadaan ketika penjaga penggantian kode menjawab nol.
    """
    s = _isi("repository/project_repository.py")
    blok = s[s.index("async def count_documents(") :][:2500]

    for tabel in (
        "purchases_table",
        "purchase_orders_table",
        "purchase_draft_table",
        "reimbursements_table",
        "sales_invoice_tables",
        "payment_plans_table",
    ):
        assert tabel in blok, f"{tabel} tidak ikut dihitung penjaga ganti kode proyek"
