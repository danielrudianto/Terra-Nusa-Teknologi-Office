"""
Mobilisasi sebagai BARIS SUNGGUHAN pada purchase_order_items.

Sebelumnya mobilisasi dan demobilisasi adalah dua kolom uang yang menempel
pada baris alatnya — `remarks_4` dan `remarks_5`. Baris "Mobilisasi Crane 25T
sesuai pada nomor 1" yang tercetak pada SPK tidak pernah ada di basis data; ia
dikarang saat mencetak.

Akibatnya certificate of payment tidak dapat menyentuhnya sama sekali. CoP
menyertifikasi per `purchase_order_items.id`, dan mobilisasi tidak punya `id`.
Karena `purchase_orders.dpp` SUDAH memuat mobilisasi, SPK sewa Rp 100 juta
yang Rp 30 juta di antaranya mobilisasi hanya dapat disertifikasi sampai
Rp 70 juta — selamanya, bukan karena pagunya habis melainkan karena barisnya
tidak pernah ada. Sisanya tercetak pada dokumen yang ditandatangani kedua
pihak, dan vendor menagihkannya.

Yang dijaga berkas ini adalah hal-hal yang membuat perpindahan itu aman, dan
tetap aman sesudahnya.
"""

import os
import re
from glob import glob

import pytest

from repository.purchase_order_item_repository import (
    JENIS_ANAK,
    PurchaseOrderItemRepository,
    _clean_item,
)
from models.purchase_order_item_model import urut_baris

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _isi(jalur: str) -> str:
    return open(jalur, encoding="utf-8").read()


# ----------------------------------------------------------------------
# Jenis baris
# ----------------------------------------------------------------------


def test_jenis_baris_asing_dibuang():
    """
    `itemKind` di luar daftar tidak boleh tersimpan apa adanya.

    Kolom ini menentukan apakah sebuah baris digabungkan kembali ke formulir
    induknya saat disunting. Nilai asing membuat barisnya menggantung: bukan
    baris biasa (karena `itemKind` terisi), bukan pula anak yang dikenali —
    dan ia hilang dari formulir tanpa hilang dari dokumen. Yang menyimpan
    ulang dokumen itu menerbitkannya tanpa baris tersebut.
    """
    assert _clean_item({"itemKind": "mobilisasi"}, 1)["itemKind"] == "mobilisasi"
    assert _clean_item({"itemKind": "MOBILISASI"}, 1)["itemKind"] == "mobilisasi"
    assert _clean_item({"itemKind": "mobilsasi"}, 1)["itemKind"] is None
    assert _clean_item({"itemKind": ""}, 1)["itemKind"] is None
    assert _clean_item({}, 1)["itemKind"] is None


def test_daftar_jenis_sama_dengan_layar():
    """
    Server dan layar harus mengenali daftar yang sama persis.

    Layar menyatakannya sebagai `JenisBarisAnak` di `purchase-order-b.helper`.
    Bila keduanya berselisih, baris yang dikirim layar diterima sebagai baris
    BIASA — tersimpan, tercetak, tetapi tidak pernah kembali ke formulir.
    """
    helper = os.path.join(
        AKAR, "..", "tnt-fe", "src", "app", "helpers", "purchase-order-b.helper.ts"
    )
    if not os.path.exists(helper):  # repo backend berdiri sendiri
        pytest.skip("repo frontend tidak ada di samping repo ini")

    m = re.search(r"export type JenisBarisAnak =\s*([^;]+);", _isi(helper))
    assert m, "`JenisBarisAnak` tidak ditemukan di helper layar"
    di_layar = tuple(re.findall(r"'([a-z]+)'", m.group(1)))
    assert di_layar == JENIS_ANAK


# ----------------------------------------------------------------------
# Tautan ke induk
# ----------------------------------------------------------------------


async def test_parent_index_diterjemahkan_menjadi_id_induk(monkeypatch):
    """
    Layar menunjuk induk lewat POSISI; server yang menjadikannya `id`.

    Pada dokumen baru induknya belum punya `id` sampai ia tersimpan, sehingga
    layar tidak mungkin mengirim `parentItemID`. Yang ia tahu hanya posisi
    induknya di dalam daftar yang sedang dikirim.
    """
    tersimpan = []
    berikutnya = iter(range(101, 200))

    async def execute_palsu(query):
        nilai = dict(query.compile().params)
        tersimpan.append(nilai)
        return next(berikutnya)

    monkeypatch.setattr(
        "repository.purchase_order_item_repository.database.execute", execute_palsu
    )

    await PurchaseOrderItemRepository.insert_many(
        7,
        [
            {"task": "Crane 25T", "quantity": 2, "price": 20_000_000, "unit": "bulan"},
            {
                "task": "Mobilisasi",
                "quantity": 1,
                "price": 15_000_000,
                "unit": "LS",
                "itemKind": "mobilisasi",
                "parentIndex": 0,
            },
        ],
    )

    # Baris biasa tidak menyebut kolomnya sama sekali; bawaan basis
    # datanya NULL.
    assert tersimpan[0].get("parentItemID") is None
    # `id` induknya, bukan posisinya.
    assert tersimpan[1]["parentItemID"] == 101
    assert tersimpan[1]["itemKind"] == "mobilisasi"


async def test_parent_index_pada_baris_biasa_diabaikan(monkeypatch):
    """
    Baris tanpa `itemKind` tidak boleh menautkan diri ke induk mana pun.

    Tautan itu membawa akibat yang tidak terlihat: `ON DELETE CASCADE` di
    basis data membuat baris tersebut ikut terhapus diam-diam ketika baris
    yang ditunjuknya dihapus — padahal ia baris pekerjaan yang berdiri
    sendiri, dan nilainya ikut lenyap dari dokumen.
    """
    tersimpan = []
    berikutnya = iter(range(201, 300))

    async def execute_palsu(query):
        tersimpan.append(dict(query.compile().params))
        return next(berikutnya)

    monkeypatch.setattr(
        "repository.purchase_order_item_repository.database.execute", execute_palsu
    )

    await PurchaseOrderItemRepository.insert_many(
        9,
        [
            {"task": "Crane 25T", "quantity": 1, "price": 1, "unit": "bulan"},
            {"task": "Genset", "quantity": 1, "price": 1, "unit": "bulan",
             "parentIndex": 0},
        ],
    )

    assert tersimpan[1].get("parentItemID") is None


# ----------------------------------------------------------------------
# Urutan cetak
# ----------------------------------------------------------------------


def test_urutan_menaruh_anak_tepat_di_bawah_induknya():
    """
    Baris anak lahir BELAKANGAN daripada seluruh baris alat.

    Pada dokumen yang dipindahkan dari bentuk lama, `id` baris mobilisasi
    jauh lebih besar daripada `id` alat mana pun. Diurutkan menurut `id`
    saja, seluruh mobilisasi menumpuk di akhir dokumen — dan cetak ulang SPK
    yang sudah ditandatangani berubah susunannya.
    """
    ungkapan = urut_baris("i")

    baris = [
        {"id": 1, "parentItemID": None},   # Crane 25T
        {"id": 2, "parentItemID": None},   # Genset
        {"id": 50, "parentItemID": 1},     # Mobilisasi Crane, dipindahkan
        {"id": 51, "parentItemID": 1},     # Demobilisasi Crane
    ]

    def kunci(b):
        return (
            b["parentItemID"] or b["id"],
            1 if b["parentItemID"] is not None else 0,
            b["id"],
        )

    assert [b["id"] for b in sorted(baris, key=kunci)] == [1, 50, 51, 2]
    # Ungkapan SQL-nya menyusun ketiga tingkat yang sama.
    assert "COALESCE(i.parentItemID, i.id)" in ungkapan
    assert "(i.parentItemID IS NOT NULL)" in ungkapan
    assert ungkapan.rstrip().endswith("i.id ASC")


def test_setiap_kueri_berurut_atas_baris_spk_memakai_urut_baris():
    """
    Yang mengurutkan baris SPK sendiri akan berselisih dengan yang lain.

    Urutan baris bukan soal kerapian: ia susunan SPK yang ditandatangani.
    Satu kueri yang tertinggal memakai `ORDER BY id` tidak menghasilkan galat
    apa pun — hanya dokumen yang susunannya berbeda dari dokumen yang sama
    di layar sebelah.
    """
    pelanggar = []
    for p in sorted(glob(os.path.join(AKAR, "repository", "*.py"))):
        s = _isi(p)
        for m in re.finditer(r"FROM purchase_order_items\b", s):
            blok = s[m.start(): m.start() + 1500]
            urut = blok.find("ORDER BY")
            if urut < 0:
                continue  # subkueri / agregat: urutannya tidak berarti
            # Ungkapan urutannya dirangkai DI LUAR untai SQL-nya, sehingga
            # yang dicari ada sesudah `ORDER BY`, bukan di dalam untainya.
            sesudah = blok[urut: urut + 250]
            if "urut_baris" not in sesudah and "{urut}" not in sesudah:
                baris = s[: m.start()].count("\n") + 1
                pelanggar.append(f"{os.path.basename(p)}:{baris}")

    assert not pelanggar, (
        f"kueri berurut atas baris SPK tanpa `urut_baris` di {pelanggar}; "
        "baris mobilisasi akan menumpuk di akhir dokumen"
    )


# ----------------------------------------------------------------------
# Migrasi
# ----------------------------------------------------------------------


def test_migrasi_disaring_per_jenis_po():
    """
    `remarks_4` BERBEDA ARTI menurut jenis PO — dan ini ranjaunya.

    Pada PO-B ia nilai mobilisasi. Pada PO-A ia NAMA SUPIR atau nomor
    rujukan; `remarks_5` di sana nama penanggung jawab.

    Migrasi yang tidak menyaring jenisnya akan mengubah nama supir menjadi
    baris pekerjaan dan menghapus namanya dari dokumen angkutan — perubahan
    yang tidak menimbulkan galat dan baru ketahuan saat dokumennya dibuka
    kembali berbulan-bulan kemudian.
    """
    # Baris KOMENTAR tidak dihitung. Berkas itu menerangkan panjang-lebar
    # mengapa penyaringnya ada — dan penjelasan itu sendiri memuat kalimat
    # yang dicari, sehingga penjaga yang membaca seluruh berkas akan tetap
    # hijau walaupun penyaringnya dibuang dari kueri yang sesungguhnya.
    s = "\n".join(
        b
        for b in _isi(os.path.join(AKAR, "sql", "mobilisasi-jadi-baris.sql")).split("\n")
        if not b.lstrip().startswith("--")
    )

    assert "purchaseType = 'B'" in s, (
        "migrasi tidak menyaring jenis PO; nama supir pada PO-A akan ikut "
        "dipindahkan menjadi baris pekerjaan"
    )
    # Penjaga kedua: isinya harus angka, sehingga teks tetap tidak terbawa
    # seandainya ada jenis PO lain yang bernilai 'B'.
    assert "REGEXP" in s

    # Nilai NOL tidak dipindahkan: SPK tanpa mobilisasi menyimpan "0" di
    # `remarks_4`, dan cara lama memang melewatinya. Memindahkannya akan
    # menumbuhkan baris "Mobilisasi Rp 0" pada dokumen yang tidak memuatnya.
    assert "> 0" in s


def test_migrasi_mengosongkan_kolom_lamanya():
    """
    `remarks_4`/`remarks_5` WAJIB dikosongkan sesudah dipindahkan.

    Peramban yang masih memegang bundel layar lama akan tetap memekarkan
    mobilisasi dari kolom itu — atas baris yang kini SUDAH punya baris
    anaknya sendiri. Hasilnya dokumen yang memuat mobilisasi dua kali, dengan
    total yang lebih besar daripada nilai dokumennya.
    """
    s = _isi(os.path.join(AKAR, "sql", "mobilisasi-jadi-baris.sql"))
    assert re.search(r"SET\s+i\.remarks_4\s*=\s*NULL", s)
    assert re.search(r"i\.remarks_5\s*=\s*NULL", s)


def test_penghapusan_induk_membawa_serta_anaknya():
    """
    Baris mobilisasi tidak punya arti sendiri.

    Alat yang dihapus dari SPK harus membawa serta biaya mobilisasinya. Yang
    tertinggal tanpa itu adalah baris bernama "Mobilisasi" yang tidak
    menunjuk apa pun — dan tetap ikut menjumlah nilai dokumen.
    """
    s = _isi(os.path.join(AKAR, "sql", "mobilisasi-jadi-baris.sql"))
    assert "ON DELETE CASCADE" in s
