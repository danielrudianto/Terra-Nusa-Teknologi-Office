"""
Tanggal terakhir pada slip gaji menonaktifkan karyawannya.

SEBELUMNYA: `lastDate` diisi di formulir, divalidasi, DIKIRIM ke server — dan
tidak pernah dibaca. Rutenya menerima `dict` mentah, jadi tidak ada skema yang
membuangnya; controllernya saja yang tidak pernah menyentuhnya.

Yang mengisinya melihat formulirnya menerima, slipnya tersimpan rapi, dan
karyawannya tetap aktif. Tanpa satu pun galat. Orang yang sudah berhenti tetap
muncul di daftar karyawan aktif dan di pemilih PIC berbulan-bulan — sampai ada
yang kebetulan menyadarinya.

Yang dijaga di sini:

  * tanggalnya benar-benar diterapkan;
  * ALASANNYA tercatat di jejak audit — menyebut slip mana;
  * `None` TIDAK mengaktifkan kembali siapa pun;
  * menyimpan ulang slip yang sama tidak melahirkan baris audit kembar;
  * gagal menonaktifkan tidak menggagalkan slipnya, tetapi juga TIDAK ditelan
    diam-diam.
"""

from datetime import date
from unittest.mock import patch

from controllers.salary_slip_controller import SalarySlipController


class _Audit:
    def __init__(self):
        self.baris = []

    async def record(self, **kw):
        self.baris.append(kw)


def _pasang(monkeypatch, hasil_set):
    audit = _Audit()

    async def set_palsu(employee_id, tanggal):
        return hasil_set

    monkeypatch.setattr(
        "controllers.salary_slip_controller.Employee.set_tanggal_berhenti",
        set_palsu,
    )
    monkeypatch.setattr(
        "controllers.salary_slip_controller.AuditLogRepository.record",
        audit.record,
    )
    return audit


async def test_tanggal_diterapkan_dan_alasannya_tercatat(monkeypatch):
    """
    Jejak auditnya harus menyebut SLIP MANA yang menyebabkannya.

    Tanpa itu, yang membaca setahun kemudian menemukan tanggal berhenti yang
    muncul entah dari mana — dan satu-satunya cara memastikannya adalah
    bertanya kepada orang yang mungkin sudah tidak di sini juga.
    """
    audit = _pasang(monkeypatch, {"tidak_berubah": False, "sebelumnya": None})

    peringatan = await SalarySlipController._terapkan_tanggal_berhenti(
        employee_id=7, last_date=date(2026, 9, 30), slip_id=123, month=9, year=2026
    )

    assert peringatan is None
    assert len(audit.baris) == 1
    b = audit.baris[0]
    assert b["entity"] == "employees"
    assert b["entityID"] == 7
    assert "123" in b["note"], "catatan tidak menyebut slipnya"
    assert "September" in b["note"], "catatan tidak menyebut periodenya"
    assert b["changes"]["endDate"]["menjadi"] == "2026-09-30"


async def test_tanpa_tanggal_tidak_mengerjakan_apa_pun(monkeypatch):
    """
    `lastDate` kosong berarti "tidak ada yang perlu dikerjakan".

    BUKAN "aktifkan kembali". Mengaktifkan kembali karyawan adalah keputusan
    tersendiri; membiarkannya terjadi sebagai efek samping dari slip yang
    disunting berarti orang yang sudah berhenti bisa hidup lagi tanpa ada yang
    memutuskannya.
    """
    audit = _pasang(monkeypatch, {"tidak_berubah": False, "sebelumnya": None})

    for kosong in (None, "", 0):
        assert (
            await SalarySlipController._terapkan_tanggal_berhenti(
                7, kosong, 1, 9, 2026
            )
            is None
        )
    assert audit.baris == [], "tidak boleh ada audit tanpa perubahan"


async def test_menyimpan_ulang_tidak_melahirkan_audit_kembar(monkeypatch):
    """
    Slip yang sama disimpan dua kali tidak boleh menambah baris audit.

    Jejak audit yang penuh baris kembar membuat yang menelusurinya berhenti
    membacanya — dan baris yang sungguhan ikut tenggelam.
    """
    audit = _pasang(
        monkeypatch, {"tidak_berubah": True, "sebelumnya": date(2026, 9, 30)}
    )

    peringatan = await SalarySlipController._terapkan_tanggal_berhenti(
        7, date(2026, 9, 30), 123, 9, 2026
    )

    assert peringatan is None
    assert audit.baris == []


async def test_gagal_menonaktifkan_tidak_ditelan_diam_diam(monkeypatch):
    """
    Slipnya tetap tersimpan, tetapi kegagalannya WAJIB disebutkan.

    Membatalkan slip yang sudah tersimpan meninggalkan keadaan separuh jadi.
    Tetapi menelan kegagalannya lebih buruk: yang mengira karyawannya sudah
    nonaktif akan berhenti memeriksanya.
    """
    audit = _pasang(monkeypatch, {"error": "Internal server error.", "status": 500})

    peringatan = await SalarySlipController._terapkan_tanggal_berhenti(
        7, date(2026, 9, 30), 123, 9, 2026
    )

    assert peringatan, "kegagalan tidak dilaporkan ke layar"
    assert "manual" in peringatan.lower(), "tidak menyebut apa yang harus dikerjakan"
    assert audit.baris == [], "tidak boleh mencatat audit atas perubahan yang gagal"


async def test_perubahan_menyebut_nilai_sebelumnya(monkeypatch):
    """
    Karyawan yang tanggal berhentinya DIUBAH — audit menyebut dari-ke.

    "Diubah" tanpa nilai lamanya tidak dapat ditelusuri: yang membacanya tidak
    tahu apakah tanggalnya dimajukan, dimundurkan, atau baru pertama diisi.
    """
    audit = _pasang(
        monkeypatch, {"tidak_berubah": False, "sebelumnya": date(2026, 8, 31)}
    )

    await SalarySlipController._terapkan_tanggal_berhenti(
        7, date(2026, 9, 30), 123, 9, 2026
    )

    perubahan = audit.baris[0]["changes"]["endDate"]
    assert perubahan["dari"] == "2026-08-31"
    assert perubahan["menjadi"] == "2026-09-30"
