"""
Nilai tagihan beban memuat PPN — sama dengan pembelian.

Beban jasa KAP: DPP 20 jt, PPN 11%, PPh 23 2%. Yang dibayar ke pemasok
20 + 2,2 − 0,4 = 21,8 jt. Sebelumnya PPN dikeluarkan ("disetor terpisah"),
sehingga layar Bayar hanya menawarkan 19,6 jt dan penjaga kelebihan bayar
menolak pembayaran penuh yang benar.
"""

from controllers.payment_outgoing_controller import nilai_beban


def test_ppn_ikut_dibayar_ke_pemasok():
    b = {"dpp": 20_000_000, "ppn": 11, "pbbkb": 0, "pphPercentage": 2}
    assert nilai_beban(b) == 21_800_000


def test_tanpa_ppn_tidak_berubah():
    b = {"dpp": 20_000_000, "ppn": 0, "pbbkb": 0, "pphPercentage": 2}
    assert nilai_beban(b) == 19_600_000


def test_baris_lama_tanpa_kolom_ppn_tidak_jatuh():
    b = {"dpp": 1_000_000, "pbbkb": 0, "pphPercentage": 0}
    assert nilai_beban(b) == 1_000_000
