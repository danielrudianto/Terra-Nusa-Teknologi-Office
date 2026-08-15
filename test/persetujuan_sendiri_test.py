"""
Yang membuat dokumen tidak boleh menyetujuinya sendiri.

Aturan kontrol internal yang paling dasar: satu orang tidak boleh menjadi
pengaju sekaligus pemberi izin. Tanpa itu, seluruh rantai persetujuan hanya
formalitas.

DIKECUALIKAN untuk level 4 (general manager) dan 5 (pemilik). Keduanya memang
berwenang atas seluruh dokumen, dan kerap merekalah satu-satunya yang hadir
untuk menyetujui — melarangnya berarti dokumen tertahan tanpa ada orang lain
yang berwenang. Pengecualian itu tetap tercatat pada jejak aktivitas.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Modul yang persetujuannya harus dijaga, beserta fungsi pintunya.
PINTU = {
    "purchase_order_repository.py": "update_status",
    "expense_repository.py": "approve_by_id",
    "reimbursement_repository.py": "approve_reimbursement_by_id",
    "sales_invoice_repository.py": "approve",
}


def _blok(berkas: str, nama: str) -> str:
    s = open(os.path.join(AKAR, "repository", berkas)).read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    return s[i:] if j == -1 else s[i:j]


def test_ambang_pengecualian_level_empat():
    """
    Level 4 ke atas dikecualikan, bukan level 5 saja.

    Ambangnya ditulis SEKALI di `utils/permission.py`. Mengulanginya di tiap
    modul membuat yang tertinggal saat aturannya berubah tidak menimbulkan
    galat — hanya satu modul yang diam-diam lebih longgar.
    """
    s = open(os.path.join(AKAR, "utils", "permission.py")).read()
    assert "LEVEL_BOLEH_SETUJU_SENDIRI = 4" in s
    assert "def boleh_menyetujui_sendiri(" in s


def test_setiap_modul_menjaga():
    for berkas, fungsi in PINTU.items():
        b = _blok(berkas, fungsi)
        assert "boleh_menyetujui_sendiri(" in b, f"{berkas}: tanpa penjagaan"
        assert "SELF_APPROVAL_FORBIDDEN" in b, f"{berkas}: tanpa kode galat"
        assert "createdBy" in b, f"{berkas}: tidak membandingkan pembuatnya"


def test_setiap_modul_menerima_level():
    """
    Tanpa parameternya, penjagaan selalu memakai nilai bawaan dan setiap
    orang diperlakukan sebagai level rendah — atau, bila bawaannya longgar,
    tidak pernah menjaga sama sekali.
    """
    for berkas, fungsi in PINTU.items():
        b = _blok(berkas, fungsi)
        tanda = b[: b.index(":\n")]
        assert "user_level" in tanda, f"{berkas}: tanpa parameter user_level"


def test_purchase_order_dijaga_di_pintu_yang_dipakai():
    """
    Persetujuan purchase order berjalan lewat `update_status`, bukan
    `approve()` — yang terakhir tidak pernah dipanggil dari rute mana pun.

    Menaruh penjagaan hanya di `approve()` berarti aturannya tidak pernah
    berlaku sama sekali.
    """
    b = _blok("purchase_order_repository.py", "update_status")
    assert 'status == "approved"' in b
    assert "boleh_menyetujui_sendiri(" in b


def test_rute_meneruskan_level():
    """Level dibaca dari pengguna yang sedang masuk, bukan dari muatan."""
    peta = {
        "purchase_order_routes.py": "update_purchase_order_status",
        "expenses_routes.py": "approve_expense_by_id",
        "reimbursement_routes.py": "approve_reimbursement",
        "sales_invoice_routes.py": "approve_sales_invoice",
    }
    for berkas in peta:
        s = open(os.path.join(AKAR, "routes", berkas)).read()
        assert 'authenticationLevel' in s, f"{berkas}: level tidak diteruskan"
