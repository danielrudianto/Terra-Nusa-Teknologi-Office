"""
Label kueri purchase order harus ada di skema jawabannya.

FastAPI menyaring jawaban terhadap `response_model` dan MEMBUANG kunci yang
tidak tercantum di sana — tanpa galat, tanpa peringatan, tanpa satu pun baris
di log. Kolom yang diberi label `supplier_name` sementara skemanya menyebut
`supplierName` karena itu tidak pernah sampai ke layar, dan yang membukanya
menyimpulkan datanya yang hilang.

Sudah terjadi dua kali: sekali pada daftar purchase order, dan sekali lagi
pada `/rantai` — yang akhirnya diberi keterangan "tanpa response_model:
penyaring bidang pernah membuang justru yang diperlukan".

Diperiksa dari SUMBERNYA, bukan dengan menjalankan kuerinya: yang dijaga di
sini adalah penamaan, dan penamaan sudah dapat dibaca tanpa basis data.
"""

import inspect
import re

from repository.purchase_order_repository import PurchaseOrderRepository
from schemas.purchase_order_schema import PurchaseOrderResponse

#: Metode yang jawabannya disaring `PurchaseOrderResponse`.
METODE_DISARING = ("get_by_id", "get_all")


def _label(nama_metode: str) -> set[str]:
    fungsi = getattr(PurchaseOrderRepository, nama_metode)
    sumber = inspect.getsource(fungsi)
    return set(re.findall(r"""\.label\(\s*['"](\w+)['"]""", sumber))


def test_ada_label_yang_diperiksa():
    """
    Penjaga bagi penjaganya.

    Bila pola pencariannya kelak tidak lagi cocok — kuerinya ditulis ulang,
    labelnya dipindah ke variabel — pengujian di bawah akan lulus atas
    himpunan kosong dan tidak memeriksa apa pun.
    """
    for metode in METODE_DISARING:
        assert _label(metode), metode


def test_seluruh_label_dikenali_skema():
    bidang = set(PurchaseOrderResponse.model_fields)
    for metode in METODE_DISARING:
        asing = _label(metode) - bidang
        assert not asing, f"{metode}: {sorted(asing)} tidak ada di PurchaseOrderResponse"


def test_nama_pemasok_ikut_terkirim():
    """
    Yang paling sering hilang, dan yang paling terasa: daftar purchase order
    menampilkan nama pemasok pada setiap barisnya.

    Nama labelnya BERBEDA antara kedua metode, dan itu memang begitu:
    `get_all` memakai snake_case karena skemanya menyebut `supplier_name`
    tersendiri untuk hasil join daftar, sedangkan `get_by_id` memakai
    camelCase. Yang dijaga di sini bukan keseragaman namanya, melainkan bahwa
    nama pemasok memang ikut diambil — dengan nama apa pun yang dikenali
    skemanya.
    """
    bidang = set(PurchaseOrderResponse.model_fields)
    for metode in METODE_DISARING:
        label = _label(metode)
        pemasok = {x for x in label if "supplier" in x.lower()}
        assert pemasok, metode
        assert pemasok <= bidang, f"{metode}: {sorted(pemasok - bidang)}"
