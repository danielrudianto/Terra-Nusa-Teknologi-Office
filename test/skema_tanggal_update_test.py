"""
Bidang `date` pada skema *Update boleh menerima tanggal.

KEKELIRUAN YANG DIJAGA

Sebuah bidang bernama `date` yang bertipe `date` DAN bernilai bawaan —
`date: Optional[date] = None` — membuat `date = None` masuk ke ruang nama
kelasnya dan MENIMPA tipe `datetime.date`. Pydantic lalu membaca tipenya
sebagai `Optional[None]` dan menolak SETIAP tanggal:

    Input should be None [type=none_required, input_value='2026-08-24']

Terjadi di tiga skema sekaligus — PaymentPlanUpdate, ContractUpdate,
TenderUpdate — sehingga menggeser tanggal rencana pengeluaran di kalender,
mengubah tanggal kontrak, dan mengubah tanggal tender semuanya gagal dengan
galat yang sama. Tidak ada satu pun yang tampak di layar sebelum tombolnya
ditekan.

Skema *Base lolos hanya karena bidangnya tak bernilai bawaan; begitu ada
default, tabrakannya muncul. Uji ini menahannya agar tidak kembali.
"""

import datetime

import pytest

from schemas.payment_plan_schema import PaymentPlanUpdate
from schemas.project_schema import ContractUpdate
from schemas.tender_schema import TenderUpdate

SKEMA_UPDATE = [PaymentPlanUpdate, ContractUpdate, TenderUpdate]


@pytest.mark.parametrize("skema", SKEMA_UPDATE)
def test_date_menerima_tanggal(skema):
    m = skema(date="2026-08-24")
    assert m.model_dump(exclude_unset=True)["date"] == datetime.date(2026, 8, 24)


@pytest.mark.parametrize("skema", SKEMA_UPDATE)
def test_tipe_date_bukan_none(skema):
    # Bila tabrakan nama kembali, anotasinya menjadi NoneType dan uji ini
    # gagal lebih dini daripada permintaan sungguhan di lapangan.
    ann = skema.model_fields["date"].annotation
    assert datetime.date in getattr(ann, "__args__", (ann,)), (
        f"{skema.__name__}.date beranotasi {ann}, bukan Optional[date]"
    )


@pytest.mark.parametrize("skema", SKEMA_UPDATE)
def test_date_boleh_kosong(skema):
    # Tetap opsional: sebagian pembaruan tidak menyentuh tanggal sama sekali.
    m = skema()
    assert "date" not in m.model_dump(exclude_unset=True)
