"""
PDF laba rugi: angka yang SAMA dengan layar, penjagaan yang SAMA dengan layar.

KENAPA PENGUJIAN INI ADA

Laporan yang dicetak dibawa ke akuntan untuk dicocokkan dengan layarnya.
Kegagalan yang ditakutkan di sini tidak satu pun melempar galat:

  1. PDF menyusun angkanya sendiri, lalu suatu hari berbeda seujung dengan
     layar. Tidak ada yang tahu mana yang benar; yang membandingkannya
     hanya kehilangan kepercayaan pada keduanya.
  2. Rincian yang dilipat di layar ikut terlipat di kertas. Laporan yang
     hanya memuat total tidak dapat dicocokkan dengan pembukuan siapa pun.
  3. Rute PDF menyalin syarat akses rute layar, lalu salah satunya
     dilonggarkan. Laporan yang ditolak di layar tetap dapat diunduh utuh.
  4. Persen pada bulan tanpa penjualan dicetak "0,0%" — menyatakan hitungan
     yang tidak pernah dilakukan.

Yang terakhir diperiksa lewat TEKS PDF sungguhan (`pdftotext`), bukan lewat
data yang diberikan ke templat: templat yang salah menulis kolom tetap
menerima data yang benar.
"""

import shutil
import subprocess

import pytest

from services.pdf_service import (
    LabaRugiDocumentService,
    _gabung_rincian,
    baris_laba_rugi,
    persen_lr,
)


def _g(total, rinci):
    return {"total": total, "rincian": rinci}


def _r(slug, label, nilai):
    return {"kategori": slug, "label": label, "nilai": nilai}


def _contoh(pendapatan_bulan=1_000_000.0):
    return {
        "month": 9,
        "year": 2026,
        "bulan": {
            "pendapatan": pendapatan_bulan,
            "hpp": _g(600_000.0, [_r("materialProyek", "Material proyek", 600_000.0)]),
            "labaKotor": pendapatan_bulan - 600_000.0,
            "bebanUsaha": _g(100_000.0, [_r("bebanGaji", "Beban gaji", 100_000.0)]),
            "labaUsaha": pendapatan_bulan - 700_000.0,
            "bebanLain": _g(0.0, []),
            "labaSebelumPajak": pendapatan_bulan - 700_000.0,
        },
        "ytd": {
            "pendapatan": 9_000_000.0,
            "hpp": _g(
                5_000_000.0,
                [
                    _r("materialProyek", "Material proyek", 4_000_000.0),
                    # Ada di YTD, TIDAK ada di bulan ini.
                    _r("sewaAlatProyek", "Sewa alat proyek", 1_000_000.0),
                ],
            ),
            "labaKotor": 4_000_000.0,
            "bebanUsaha": _g(900_000.0, [_r("bebanGaji", "Beban gaji", 900_000.0)]),
            "labaUsaha": 3_100_000.0,
            "bebanLain": _g(50_000.0, [_r("bunga", "Bunga", 50_000.0)]),
            "labaSebelumPajak": 3_050_000.0,
        },
    }


# ---------------------------------------------------------------------
# Persen — aturan yang sama dengan `persen()` di layar.
# ---------------------------------------------------------------------


def test_persen_satu_desimal_koma():
    assert persen_lr(657_000, 1_000_000) == "65,7%"


def test_persen_pendapatan_nol_adalah_tanda_pisah_bukan_nol():
    assert persen_lr(500, 0) == "—"
    assert persen_lr(500, None) == "—"


def test_persen_nol_sungguhan_tetap_nol():
    # Pendapatan ada, nilainya nol: itu hitungan yang dilakukan.
    assert persen_lr(0, 1_000_000) == "0,0%"


def test_persen_negatif_tetap_negatif():
    assert persen_lr(-250_000, 1_000_000) == "-25,0%"


def test_persen_ribuan_memakai_titik():
    assert persen_lr(12_345, 1) == "1.234.500,0%"


# ---------------------------------------------------------------------
# Rincian gabungan — cermin `rinci()` di layar.
# ---------------------------------------------------------------------


def test_kategori_hanya_di_ytd_tetap_tercetak_dengan_nol_bulanan():
    h = _contoh()
    rinci = _gabung_rincian(h["bulan"], h["ytd"], "hpp")
    sewa = [r for r in rinci if r["kategori"] == "sewaAlatProyek"]
    assert sewa, "kategori YTD yang belum muncul bulan ini hilang dari cetakan"
    assert sewa[0]["bulan"] == 0.0
    assert sewa[0]["ytd"] == 1_000_000.0


def test_kategori_hanya_di_bulan_tetap_tercetak_dengan_nol_ytd():
    bulan = {"hpp": _g(5.0, [_r("baru", "Baru", 5.0)])}
    ytd = {"hpp": _g(0.0, [])}
    rinci = _gabung_rincian(bulan, ytd, "hpp")
    assert rinci == [
        {"kategori": "baru", "label": "Baru", "bulan": 5.0, "ytd": 0.0}
    ]


def test_rincian_urut_ytd_terbesar_di_atas():
    h = _contoh()
    rinci = _gabung_rincian(h["bulan"], h["ytd"], "hpp")
    assert [r["kategori"] for r in rinci] == ["materialProyek", "sewaAlatProyek"]


def test_kategori_yang_sama_tidak_tercetak_dua_kali():
    h = _contoh()
    rinci = _gabung_rincian(h["bulan"], h["ytd"], "hpp")
    slug = [r["kategori"] for r in rinci]
    assert len(slug) == len(set(slug))


# ---------------------------------------------------------------------
# Baris cetak — seluruh kelompok TERBUKA, total dari server.
# ---------------------------------------------------------------------


def test_urutan_baris_mengikuti_layar():
    jenis_label = [(b["jenis"], b["label"]) for b in baris_laba_rugi(_contoh())]
    kerangka = [x for x in jenis_label if x[0] != "rinci"]
    assert kerangka == [
        ("pokok", "Pendapatan"),
        ("grup", "Harga Pokok Penjualan"),
        ("subtotal", "Laba Kotor"),
        ("grup", "Beban Usaha"),
        ("subtotal", "Laba Usaha"),
        ("grup", "Beban Lain-lain"),
        ("total", "Laba Sebelum Pajak"),
    ]


def test_rincian_semua_kelompok_ikut_tercetak():
    """Layar melipat Beban Lain-lain secara bawaan; kertas tidak boleh."""
    label = [b["label"] for b in baris_laba_rugi(_contoh()) if b["jenis"] == "rinci"]
    assert "Material proyek" in label
    assert "Sewa alat proyek" in label
    assert "Beban gaji" in label
    assert "Bunga" in label


def test_total_diambil_dari_server_bukan_dihitung_ulang():
    """
    Total kelompok = angka server, bahkan bila rinciannya tidak berjumlah
    sama. Menghitung ulang di sini menciptakan penyusun angka kedua — dan
    begitu keduanya berbeda, PDF dan layar menyebut dua laba.
    """
    h = _contoh()
    h["ytd"]["hpp"]["total"] = 5_000_001.0  # sengaja tidak sama dengan rinciannya
    grup = [b for b in baris_laba_rugi(h) if b["label"] == "Harga Pokok Penjualan"][0]
    assert grup["ytd"] == 5_000_001.0


def test_kelompok_beban_bertanda_kurang_dan_laba_tidak():
    baris = {b["label"]: b for b in baris_laba_rugi(_contoh())}
    assert baris["Harga Pokok Penjualan"]["kurang"] is True
    assert baris["Beban Usaha"]["kurang"] is True
    assert baris["Beban Lain-lain"]["kurang"] is True
    assert baris["Laba Kotor"]["kurang"] is False
    assert baris["Laba Sebelum Pajak"]["kurang"] is False
    assert baris["Pendapatan"]["kurang"] is False


def test_bulan_tanpa_penjualan_persennya_tanda_pisah():
    baris = baris_laba_rugi(_contoh(pendapatan_bulan=0.0))
    assert all(b["persenBulan"] == "—" for b in baris)
    # YTD tetap dihitung: pendapatan tahunannya ada.
    assert any(b["persenYtd"] != "—" for b in baris)


def test_data_cetak_menyebut_periode_indonesia():
    d = LabaRugiDocumentService.data_cetak(_contoh(), "Daniel")
    assert d["periode"] == "September 2026"
    assert d["periodeYtd"].startswith("Januari")
    assert d["dicetakOleh"] == "Daniel"


# ---------------------------------------------------------------------
# PDF sungguhan — teks yang benar-benar tercetak.
# ---------------------------------------------------------------------

butuh_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="pdftotext tidak terpasang"
)


def _teks_pdf(isi: bytes, tmp_path) -> str:
    f = tmp_path / "lr.pdf"
    f.write_bytes(isi)
    return subprocess.run(
        ["pdftotext", "-layout", str(f), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@butuh_pdftotext
def test_pdf_memuat_angka_yang_sama_dengan_data(tmp_path):
    teks = _teks_pdf(LabaRugiDocumentService.render(_contoh(), "Daniel"), tmp_path)
    for angka in (
        "1.000.000,00",   # pendapatan bulan
        "9.000.000,00",   # pendapatan YTD
        "3.050.000,00",   # laba sebelum pajak YTD
        "1.000.000,00",   # sewa alat YTD (tidak ada di bulan ini)
        "50.000,00",      # bunga YTD — kelompok yang dilipat di layar
    ):
        assert angka in teks, f"{angka} tidak tercetak"
    assert "Laporan Laba Rugi" in teks
    assert "September 2026" in teks


@butuh_pdftotext
def test_pdf_bulan_tanpa_penjualan_tidak_mencetak_nol_persen_palsu(tmp_path):
    teks = _teks_pdf(
        LabaRugiDocumentService.render(_contoh(pendapatan_bulan=0.0)), tmp_path
    )
    # Baris TABEL-nya (ber-%), bukan catatan kaki yang juga menyebut "Pendapatan".
    baris_pendapatan = [
        b for b in teks.splitlines() if "Pendapatan" in b and "%" in b
    ][0]
    # Dibandingkan per TOKEN, bukan per untai: kolom YTD di baris yang sama
    # berisi "100,0%", dan "0,0%" adalah potongan darinya. Pemeriksaan untai
    # sempat gagal karena itu — gagal yang benar tentang hal yang salah.
    token = baris_pendapatan.split()
    assert "0,0%" not in token, token
    assert "\u2014" in token, token
    assert "100,0%" in token, "kolom YTD seharusnya tetap dihitung"


# ---------------------------------------------------------------------
# Penjagaan — satu syarat untuk layar dan PDF.
# ---------------------------------------------------------------------

MODUL_RUTE = "routes.report_routes"


@pytest.mark.asyncio
async def test_pdf_ditolak_untuk_yang_ditolak_layar(monkeypatch):
    import routes.report_routes as rr
    from fastapi import HTTPException

    dirender = []

    async def tidak_boleh(*a, **k):
        return False

    async def catat(*a, **k):
        return None

    async def data(*a, **k):
        return _contoh()

    monkeypatch.setattr(rr, "is_allowed", tidak_boleh)
    monkeypatch.setattr(rr.AuditLogRepository, "catat_akses_laporan", catat)
    monkeypatch.setattr(rr.LabaRugiRepository, "laba_rugi", data)

    import services.pdf_service as ps

    monkeypatch.setattr(
        ps.LabaRugiDocumentService,
        "render",
        staticmethod(lambda *a, **k: dirender.append(1) or b"%PDF"),
    )

    pengguna = {"authenticationLevel": 3, "name": "Orang lain"}
    with pytest.raises(HTTPException) as e:
        await rr.laba_rugi_pdf(pengguna, 9, 2026)
    assert e.value.status_code == 403
    assert not dirender, "PDF tetap dirender untuk yang tidak berhak"


@pytest.mark.asyncio
async def test_pdf_diizinkan_lewat_izin_modul_seperti_layar(monkeypatch):
    """Konsultan (level 3, `laba_rugi:read`) boleh — sama dengan layarnya."""
    import routes.report_routes as rr
    import services.pdf_service as ps

    async def boleh(*a, **k):
        return True

    jejak = []

    async def catat(modul, ket):
        jejak.append(ket)

    async def data(*a, **k):
        return _contoh()

    monkeypatch.setattr(rr, "is_allowed", boleh)
    monkeypatch.setattr(rr.AuditLogRepository, "catat_akses_laporan", catat)
    monkeypatch.setattr(rr.LabaRugiRepository, "laba_rugi", data)
    monkeypatch.setattr(
        ps.LabaRugiDocumentService, "render", staticmethod(lambda *a, **k: b"%PDF-1.7")
    )

    r = await rr.laba_rugi_pdf({"authenticationLevel": 3, "name": "Konsultan"}, 9, 2026)
    assert r.media_type == "application/pdf"
    assert "Laba-Rugi-2026-09.pdf" in r.headers["content-disposition"]
    assert jejak and "(PDF)" in jejak[0], "unduhan PDF tidak dibedakan di jejak audit"


@pytest.mark.asyncio
async def test_layar_tidak_ikut_ditandai_pdf(monkeypatch):
    import routes.report_routes as rr

    async def boleh(*a, **k):
        return True

    jejak = []

    async def catat(modul, ket):
        jejak.append(ket)

    async def data(*a, **k):
        return _contoh()

    monkeypatch.setattr(rr, "is_allowed", boleh)
    monkeypatch.setattr(rr.AuditLogRepository, "catat_akses_laporan", catat)
    monkeypatch.setattr(rr.LabaRugiRepository, "laba_rugi", data)

    await rr.laba_rugi({"authenticationLevel": 5}, 9, 2026)
    assert jejak and "(PDF)" not in jejak[0]
