"""Deret saldo harian untuk garis tren Posisi Kas."""

from datetime import date

from models.dashboard_model import susun_tren


def test_hari_kosong_mewarisi_saldo_dan_baris_terakhir_menang():
    mulai = date(2026, 9, 1)
    titik = susun_tren(
        [1, 2],
        {1: 100.0, 2: 50.0},                      # saldo sebelum 1 Sep
        [
            (1, date(2026, 9, 2), 120.0),
            (1, date(2026, 9, 2), 90.0),          # baris terakhir hari itu
            (2, date(2026, 9, 3), 70.0),
        ],
        mulai,
        4,
    )
    assert [t["saldo"] for t in titik] == [150.0, 140.0, 160.0, 160.0]
    assert titik[0]["tanggal"] == "2026-09-01" and titik[-1]["tanggal"] == "2026-09-04"


def test_rekening_tanpa_mutasi_bernilai_nol():
    titik = susun_tren([7], {}, [], date(2026, 9, 1), 2)
    assert [t["saldo"] for t in titik] == [0.0, 0.0]
