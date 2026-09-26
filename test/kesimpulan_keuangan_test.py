"""
KESIMPULAN dari kesebelas rasio.

Halaman ini sudah menjawab "berapa" dan "apa artinya". Kesimpulan menjawab
yang ketiga: dari sebelas angka, MANA yang harus dikerjakan lebih dulu.

Tiga kekeliruan dijaga di sini, dan ketiganya menghasilkan kesimpulan yang
tetap terbaca masuk akal — tidak satu pun melempar galat.

1. RASIO YANG DIJATUHKAN DIAM-DIAM. Pernah terjadi dan tertangkap saat
   menjalankannya terhadap basis data sungguhan: `rasio` tidak memuat quick
   ratio maupun D/E, keduanya masuk lewat jalan lain. Diserahkan `rasio`,
   kesimpulan menjatuhkan quick ratio — rasio berbobot TERTINGGI — sehingga
   "tidak mampu membayar yang jatuh tempo" tidak akan pernah muncul sebagai
   butir mendesak. Daftarnya hanya lebih pendek, dan yang membacanya
   menyimpulkan tidak ada masalah likuiditas.

2. PENGURUTAN YANG DIMENANGKAN SATUAN. DSO diukur dalam HARI (120 lawan
   batas 95); piutang tua dalam PECAHAN (0,30 lawan batas 0,15). Tanpa
   normalisasi, selisih 25 selalu mengalahkan selisih 0,15 dan DSO akan
   berada di puncak daftar apa pun keadaannya — termasuk ketika yang
   sebenarnya mendesak adalah hal lain.

3. KALIMAT LABA YANG BOCOR KE LEVEL 4. Blok marjin sengaja tidak digambar
   untuk level di bawah 5. Kalimat "marjin bersih tipis" menyatakan arah laba
   perusahaan tanpa menyebut angkanya — dan gerbangnya harus di SERVER,
   sebab yang disaring di peramban tetap terkirim ke sana.
"""

import pytest

from controllers.kesimpulan_keuangan import (
    BOBOT,
    MAKS_MENDESAK,
    RASIO_LABA,
    susun,
)
from repository.finance_status_repository import AMBANG_BAWAAN, ARAH
from controllers.finance_status_controller import posisi_terhadap_pita


def _pita(kode):
    p = dict(AMBANG_BAWAAN[kode])
    p["arah"] = ARAH[kode]
    return p


def _nilai_seluruhnya(**ubah):
    """Kesebelas rasio, seluruhnya DI DALAM acuan kecuali yang diubah."""
    dasar = {
        "quickRatio": 1.3,
        "debtToEquity": 1.0,
        "dso": 70.0,
        "dpo": 60.0,
        "siklusModalKerja": 10.0,
        "piutangTua": 0.05,
        "konsentrasiPiutang": 0.20,
        "marjinKotor": 0.18,
        "marjinBersih": 0.06,
        "rasioOverhead": 0.12,
        "roe": 0.15,
    }
    dasar.update(ubah)
    return dasar


def _susun(nilai=None, *, ekuitas=1_000.0, pinjaman=0.0, boleh_laba=True):
    nilai = nilai if nilai is not None else _nilai_seluruhnya()
    ambang = {k: _pita(k) for k in AMBANG_BAWAAN}
    penilaian = {
        k: posisi_terhadap_pita(v, ambang.get(k)) for k, v in nilai.items()
    }
    return susun(
        nilai,
        penilaian,
        ambang,
        ekuitas=ekuitas,
        pinjaman=pinjaman,
        boleh_laba=boleh_laba,
    )


# --------------------------------------------------------------------------
# Tidak ada rasio yang hilang
# --------------------------------------------------------------------------


def test_SETIAP_rasio_yang_dinilai_muncul_sebagai_mendesak_atau_aman():
    """
    PENJAGA UTAMANYA.

    Rasio yang dijatuhkan tidak menghasilkan galat — daftarnya hanya lebih
    pendek. Dan yang paling mungkin terjatuh justru quick ratio, karena ia
    datang dari jalan yang berbeda dengan rasio lainnya.
    """
    nilai = _nilai_seluruhnya()
    h = _susun(nilai)

    disebut = {x["kode"] for x in h["mendesak"]} | set(h["aman"])
    # `mendesak` dipotong tiga; yang dibandingkan keseluruhannya.
    hilang = set(nilai) - disebut - {"__"}
    assert h["jumlahDinilai"] == len(nilai)
    assert h["jumlahMendesak"] + len(h["aman"]) == len(nilai), (
        f"ada rasio yang tidak terhitung sama sekali: {hilang}"
    )


def test_quick_ratio_TIDAK_boleh_terjatuh():
    """
    Disebut tersendiri karena inilah yang benar-benar pernah terjadi.

    Bobotnya tertinggi di antara semuanya: kalau ia hilang, butir paling
    berakibat yang hilang.
    """
    h = _susun(_nilai_seluruhnya(quickRatio=0.6))
    assert "quickRatio" in {x["kode"] for x in h["mendesak"]}
    assert BOBOT["quickRatio"] == max(BOBOT.values())


def test_rasio_yang_nilainya_TIDAK_ADA_tidak_dihitung_maupun_dikarang():
    nilai = _nilai_seluruhnya()
    del nilai["roe"]
    nilai["marjinBersih"] = None
    h = _susun(nilai)
    disebut = {x["kode"] for x in h["mendesak"]} | set(h["aman"])
    assert "roe" not in disebut
    assert "marjinBersih" not in disebut


# --------------------------------------------------------------------------
# Pengurutan
# --------------------------------------------------------------------------


def test_jaraknya_DINORMALKAN_sehingga_satuan_tidak_menentukan_pemenang():
    """
    DSO 120 lawan batas 95 = lewat 26%.
    Piutang tua 0,45 lawan batas 0,15 = lewat 200%.

    Tanpa normalisasi, selisih 25 (hari) mengalahkan selisih 0,30 (pecahan)
    dan DSO menang — padahal piutang yang hampir separuhnya sudah lewat 90
    hari jauh lebih berakibat.
    """
    h = _susun(_nilai_seluruhnya(dso=120.0, piutangTua=0.45))
    urutan = [x["kode"] for x in h["mendesak"]]
    assert urutan[0] == "piutangTua", urutan


def test_bobot_ikut_menentukan_bukan_jarak_saja():
    """
    Jarak yang SAMA pada dua rasio harus dimenangkan yang lebih berakibat.

    Piutang tua dan DSO sama-sama lewat 100% dari batasnya; piutang tua
    berbobot lebih tinggi karena uang yang sudah menua adalah uang yang makin
    lama makin tidak akan datang, sementara DSO yang tinggi masih dapat
    ditagih.
    """
    h = _susun(_nilai_seluruhnya(piutangTua=0.30, dso=190.0))
    urutan = [x["kode"] for x in h["mendesak"]]
    assert urutan.index("piutangTua") < urutan.index("dso")
    assert BOBOT["piutangTua"] > BOBOT["dso"]


def test_paling_banyak_tiga_disebut_tetapi_jumlah_sebenarnya_dilaporkan():
    """
    Daftar yang memuat segalanya tidak memberi prioritas — tetapi
    menyembunyikan berapa banyak sisanya membuat tiga itu terbaca sebagai
    seluruhnya.
    """
    h = _susun(
        _nilai_seluruhnya(
            quickRatio=0.5,
            dso=200.0,
            piutangTua=0.60,
            konsentrasiPiutang=0.90,
            debtToEquity=6.0,
        )
    )
    assert len(h["mendesak"]) == MAKS_MENDESAK
    assert h["jumlahMendesak"] >= 5


def test_seluruhnya_di_dalam_acuan_tidak_mengarang_yang_mendesak():
    h = _susun()
    assert h["mendesak"] == []
    assert h["jumlahMendesak"] == 0
    assert len(h["aman"]) == 11


# --------------------------------------------------------------------------
# Gerbang laba
# --------------------------------------------------------------------------


def test_level_di_bawah_5_tidak_menerima_SATU_KALIMAT_PUN_soal_laba():
    """
    Digerbang di SERVER. Yang disaring di peramban tetap terkirim ke sana dan
    tinggal dibuka di alat pengembang — dan yang bocor bukan angkanya
    melainkan pernyataan tentang arah laba perusahaan.
    """
    h = _susun(
        _nilai_seluruhnya(marjinBersih=0.01, rasioOverhead=0.40, roe=0.01),
        boleh_laba=False,
    )
    disebut = {x["kode"] for x in h["mendesak"]} | set(h["aman"])
    assert not (disebut & RASIO_LABA), disebut & RASIO_LABA

    kombinasi = {x["kode"] for x in h["kombinasi"]}
    assert "kantorYangMemakan" not in kombinasi
    assert "untungDiKertas" not in kombinasi
    assert "roeTerangkatUtang" not in kombinasi

    # Dan dikatakan, bukan dihilangkan diam-diam.
    assert "marjinTidakIkutDinilai" in h["takTerlihat"]


def test_level_5_menerima_seluruhnya():
    h = _susun(_nilai_seluruhnya(marjinBersih=0.01), boleh_laba=True)
    disebut = {x["kode"] for x in h["mendesak"]} | set(h["aman"])
    assert RASIO_LABA <= disebut
    assert "marjinTidakIkutDinilai" not in h["takTerlihat"]


# --------------------------------------------------------------------------
# Kombinasi — nilai sebenarnya dari kesimpulan ini
# --------------------------------------------------------------------------


def test_untung_di_kertas_belum_di_kas():
    """
    Marjin bersih aman, siklus modal kerja panjang. Labanya nyata; uangnya
    belum ada di rekening, dan yang menalanginya perusahaan sendiri. Tidak
    satu pun dari kedua rasio itu mengatakannya sendirian.
    """
    h = _susun(_nilai_seluruhnya(marjinBersih=0.08, siklusModalKerja=90.0))
    assert "untungDiKertas" in {x["kode"] for x in h["kombinasi"]}


def test_roe_tinggi_bersama_utang_tinggi_disebut_terangkat_utang():
    """
    ROE membagi laba dengan EKUITAS. Ekuitas yang tipis karena utang besar
    menaikkan ROE tanpa satu rupiah pun laba tambahan — dan dibaca
    sendirian, ROE tinggi terbaca sebagai prestasi.
    """
    h = _susun(_nilai_seluruhnya(roe=0.45, debtToEquity=3.0))
    assert "roeTerangkatUtang" in {x["kode"] for x in h["kombinasi"]}


def test_roe_tinggi_dengan_utang_wajar_TIDAK_dituduh():
    """Sisi sebaliknya: aturan yang menyala di mana-mana tidak berarti apa pun."""
    h = _susun(_nilai_seluruhnya(roe=0.45, debtToEquity=0.8))
    assert "roeTerangkatUtang" not in {x["kode"] for x in h["kombinasi"]}


def test_piutang_tua_yang_tersamar_oleh_faktur_baru():
    """
    DSO adalah RATA-RATA. Faktur baru yang deras menariknya turun sementara
    yang tua tetap di tempatnya — jadi DSO wajar bersama piutang tua besar
    berarti rata-ratanya menyembunyikan tumpukan itu, bukan meniadakannya.
    """
    h = _susun(_nilai_seluruhnya(piutangTua=0.35, dso=70.0))
    assert "piutangTuaTersamar" in {x["kode"] for x in h["kombinasi"]}


def test_satu_klien_menentukan_kas():
    h = _susun(_nilai_seluruhnya(konsentrasiPiutang=0.70, dso=130.0))
    assert "satuKlienMenentukan" in {x["kode"] for x in h["kombinasi"]}


def test_dibiayai_pemasok_hanya_bila_likuiditasnya_memang_kurang():
    """
    DPO jauh di atas DSO TERLIHAT baik pada rasionya. Bersama quick ratio di
    bawah acuan artinya berbalik: bukan pilihan, melainkan karena kasnya
    tidak cukup membayar tepat waktu.
    """
    kurang = _susun(_nilai_seluruhnya(dpo=120.0, dso=60.0, quickRatio=0.7))
    assert "dibiayaiPemasok" in {x["kode"] for x in kurang["kombinasi"]}

    cukup = _susun(_nilai_seluruhnya(dpo=120.0, dso=60.0, quickRatio=1.3))
    assert "dibiayaiPemasok" not in {x["kode"] for x in cukup["kombinasi"]}


def test_likuiditas_yang_belum_memuat_angsuran_disebut_saat_ada_pinjaman():
    """
    Quick ratio tidak memuat pinjaman di penyebutnya karena `loans` tidak
    menyimpan tenor. Quick ratio yang aman karena itu dapat aman semu — dan
    itu harus disebut justru ketika angkanya terlihat baik.
    """
    ada = _susun(pinjaman=2_000_000_000.0)
    assert "likuiditasBelumMemuatAngsuran" in {
        x["kode"] for x in ada["kombinasi"]
    }

    tanpa = _susun(pinjaman=0.0)
    assert "likuiditasBelumMemuatAngsuran" not in {
        x["kode"] for x in tanpa["kombinasi"]
    }


# --------------------------------------------------------------------------
# Kalimat pokok & batasan
# --------------------------------------------------------------------------


def test_ekuitas_minus_mengalahkan_segalanya():
    """
    Pada ekuitas minus, D/E dan ROE tidak bermakna, dan yang perlu
    dibicarakan bukan rasio mana pun melainkan bahwa kewajiban sudah
    melampaui aset.
    """
    h = _susun(_nilai_seluruhnya(dso=200.0), ekuitas=-500.0)
    assert h["pokok"]["kode"] == "ekuitasMinus"


def test_pokok_menyebut_yang_teratas_bukan_sekadar_jumlahnya():
    h = _susun(_nilai_seluruhnya(quickRatio=0.4))
    assert h["pokok"]["kode"] == "adaYangDiLuarAcuan"
    assert h["pokok"]["angka"]["teratas"] == "quickRatio"


def test_semua_aman_tetap_membedakan_ada_catatan_dan_tidak():
    bersih = _susun(pinjaman=0.0)
    assert bersih["pokok"]["kode"] == "semuaDidalamAcuan"

    bercatatan = _susun(pinjaman=1_000.0)
    assert bercatatan["pokok"]["kode"] == "semuaDidalamTapiAdaCatatan"


def test_yang_tidak_terlihat_SELALU_disebut():
    """
    Kesimpulan yang kadang menyebut batasnya dan kadang tidak akan dibaca
    sebagai "kali ini tidak ada batasnya".
    """
    for pinjaman in (0.0, 5_000.0):
        for laba in (True, False):
            h = _susun(pinjaman=pinjaman, boleh_laba=laba)
            assert h["takTerlihat"], (pinjaman, laba)
            assert "ekuitasDiturunkanBukanDicatat" in h["takTerlihat"]


def test_TIDAK_ADA_skor_gabungan_di_dalam_jawabannya():
    """
    Disengaja, dan dijaga.

    Kesebelas rasio berbeda skala dan berbeda keandalan — ekuitas diturunkan
    bukan dicatat, quick ratio tidak memuat pinjaman, overhead punya catatan
    sendiri. Dirata-rata menjadi satu angka, seluruh peringatan itu hilang
    dan yang tersisa kesan presisi yang tidak punya dasar. Lebih buruk:
    begitu ada angka besar di atas, orang berhenti membaca komponennya —
    dan komponennyalah satu-satunya yang dapat ditindaklanjuti.

    `skor` per BUTIR boleh ada; ia alat pengurut, dan selalu berdampingan
    dengan jarak serta bobot yang menghasilkannya sehingga dapat dibantah.
    Yang tidak boleh ada adalah satu angka untuk seluruh perusahaan.
    """
    h = _susun()
    assert "skor" not in h
    assert "nilaiKeseluruhan" not in h
    assert "sehat" not in h
    for butir in h["mendesak"]:
        assert {"jarakDariPita", "bobot", "skor"} <= set(butir)
