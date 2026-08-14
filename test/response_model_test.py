"""
`response_model` membuang bidang tanpa memberi tahu.

Bila sebuah rute menyatakan `response_model=SkemaTertentu`, FastAPI hanya
meloloskan bidang yang dideklarasikan skema itu. Bidang lain dibuang diam-
diam: tanpa galat, tanpa peringatan, tanpa jejak di log.

Sudah dua kali menjatuhkan hal yang sudah dikerjakan:
  1. `purchase_order_id` pada daftar pembelian — kuerinya menyambungkan
     dokumennya dengan benar, tetapi setiap baris tetap ditandai "dokumen
     belum tersedia" karena id-nya tidak pernah sampai ke layar.
  2. `approvedByName` dan `approvedByPosition` pada purchase order — blok
     tanda tangan selalu kosong walaupun dokumennya sudah disetujui.

Keduanya baru ketahuan dari layar, bukan dari kode.
"""

import os
import re
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bidang_skema(nama_kelas: str) -> set[str] | None:
    """Bidang yang dideklarasikan sebuah kelas skema, termasuk induknya."""
    for p in glob(os.path.join(AKAR, "schemas", "*.py")):
        s = open(p).read()
        m = re.search(
            rf"class {nama_kelas}\(([^)]*)\):([\s\S]*?)(?=\nclass |\Z)", s
        )
        if not m:
            continue
        bidang = set(re.findall(r"^\s{4}(\w+)\s*:", m.group(2), re.M))
        # Bidang induk ikut berlaku.
        for induk in re.findall(r"\w+", m.group(1)):
            if induk not in ("BaseModel",):
                anak = _bidang_skema(induk)
                if anak:
                    bidang |= anak
        return bidang
    return None


def test_kolom_ber_label_tidak_terbuang_response_model():
    """
    Setiap kolom yang sengaja diberi nama lain di kueri harus dikenal
    skemanya, bila rutenya memakai `response_model`.

    Kolom diberi `label()` justru karena ada yang membutuhkannya di layar;
    yang tidak dikenal skema berarti dikerjakan tetapi tidak pernah sampai.
    """
    # Pasangan yang diperiksa: skema jawaban -> repository yang mengisinya.
    PASANGAN = [
        ("PurchaseResponse", "purchase_repository.py"),
        ("PurchaseOrderResponse", "purchase_order_repository.py"),
    ]
    #: Label yang memang hanya dipakai di dalam repository — dirakit menjadi
    #: bidang lain sebelum dikirim, sehingga tidak perlu ada di skema.
    INTERNAL = {
        "supplier_id", "supplier_address", "supplier_city",
        "supplier_npwp", "supplier_province",
        "purchase_id", "usage_count", "total_paid", "remaining",
        "createdByName", "item_description", "equipment_name",
        # Dirakit menjadi objek `supplier` sebelum dikirim (baris ~150
        # `purchase_repository.py`), sehingga tidak dikirim sendiri-sendiri.
        "supplier_name", "supplier_prefix",
    }

    pelanggaran = []
    for kelas, repo in PASANGAN:
        bidang = _bidang_skema(kelas)
        assert bidang is not None, f"skema {kelas} tidak ditemukan"
        s = open(os.path.join(AKAR, "repository", repo)).read()
        for m in re.finditer(r'\.label\(\s*["\'](\w+)["\']\s*\)', s):
            k = m.group(1)
            if k in INTERNAL or k in bidang:
                continue
            pelanggaran.append(f"{repo}: {k} tidak ada di {kelas}")

    assert not pelanggaran, "; ".join(pelanggaran)


def test_purchase_order_id_dikenal():
    """Tautan ke dokumen purchase order pada daftar pembelian."""
    assert "purchase_order_id" in (_bidang_skema("PurchaseResponse") or set())


def test_penyetuju_dikenal():
    """Nama dan jabatan penyetuju untuk blok tanda tangan dokumen."""
    b = _bidang_skema("PurchaseOrderResponse") or set()
    assert "approvedByName" in b
    assert "approvedByPosition" in b
